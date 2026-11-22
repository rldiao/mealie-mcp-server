"""Per-user Mealie clients obtained through Mealie's trusted reverse-proxy sign-in."""

import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

from . import MealieFetcher
from .client import MealieApiError, check_mealie_health, log_failure

EXCHANGE_OPERATION = "Exchanging Mealie reverse-proxy token"
ACCOUNT_UNAVAILABLE = "Mealie account not found; sign in to Mealie once in a browser first"


@dataclass(frozen=True)
class ReverseProxyConfig:
    secret: str = field(repr=False)
    user_header: str = "X-Forwarded-User"
    secret_header: str = "X-Mealie-Reverse-Proxy-Secret"


@dataclass(frozen=True)
class MealieToken:
    access_token: str = field(repr=False)
    expires_at: float


class MealieAccountUnavailable(ValueError):
    """The user has no Mealie account yet (a ValueError so tools show its message)."""

    def __init__(self) -> None:
        super().__init__(ACCOUNT_UNAVAILABLE)


class MealieUsernameNotAscii(ValueError):
    """The username cannot be sent as an HTTP header (message never names it)."""

    def __init__(self) -> None:
        super().__init__("Mealie reverse-proxy sign-in requires an ASCII username")


class ReverseProxyFetcher(MealieFetcher):
    """A Mealie client acting as one user, renewing its token once on a 401."""

    def __init__(
        self, base_url: str, username: str, exchange: Callable[[str], MealieToken]
    ):
        self._username = username
        self._exchange = exchange
        token = exchange(username)
        super().__init__(base_url, token.access_token, check_health=False)
        self.expires_at = token.expires_at

    def _handle_request(self, method: str, url: str, **kwargs) -> Any:
        try:
            return super()._handle_request(method, url, **kwargs)
        except MealieApiError as error:
            if error.status_code != 401:
                raise
        token = self._exchange(self._username)
        self._client.headers["Authorization"] = f"Bearer {token.access_token}"
        self.expires_at = token.expires_at
        return super()._handle_request(method, url, **kwargs)


class ReverseProxyClientPool:
    """Bounded LRU cache of per-user fetchers; the lock also covers each exchange."""

    def __init__(
        self,
        base_url: str,
        config: ReverseProxyConfig,
        *,
        max_clients: int = 256,
        expiry_margin: float = 300.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._base_url = base_url
        self._config = config
        self._max_clients = max_clients
        self._expiry_margin = expiry_margin
        self._clock = clock
        self._lock = threading.Lock()
        self._clients: OrderedDict[str, ReverseProxyFetcher] = OrderedDict()
        self._closed = False
        throwaway = httpx.Client(base_url=base_url, timeout=30.0)
        try:
            check_mealie_health(throwaway)
        finally:
            throwaway.close()

    def get(self, username: str) -> MealieFetcher:
        key = username.strip().lower()
        with self._lock:
            if self._closed:
                raise RuntimeError("Mealie client pool is closed")
            fetcher = self._clients.get(key)
            if fetcher is not None:
                if self._clock() < fetcher.expires_at:
                    self._clients.move_to_end(key)
                    return fetcher
                del self._clients[key]
                fetcher.close()
            fetcher = ReverseProxyFetcher(self._base_url, key, self._exchange)
            self._clients[key] = fetcher
            while len(self._clients) > self._max_clients:
                _, oldest = self._clients.popitem(last=False)
                oldest.close()
            return fetcher

    def close(self) -> None:
        with self._lock:
            self._closed = True
            clients = list(self._clients.values())
            self._clients.clear()
        for fetcher in clients:
            fetcher.close()

    def _exchange(self, username: str) -> MealieToken:
        # A fresh client per exchange: Mealie answers with a session cookie that a
        # shared client would send on the next exchange, for another user.
        if not username.isascii():
            raise MealieUsernameNotAscii()
        http = httpx.Client(base_url=self._base_url, timeout=30.0)
        try:
            response = http.get(
                "/api/auth/reverse-proxy",
                headers={
                    self._config.user_header: username,
                    self._config.secret_header: self._config.secret,
                },
            )
            response.raise_for_status()
            try:
                body = response.json()
            except ValueError:
                body = None
            token = body.get("access_token") if isinstance(body, dict) else None
            expires_in = body.get("expires_in") if isinstance(body, dict) else None
            if (
                not isinstance(token, str)
                or not token
                or isinstance(expires_in, bool)
                or not isinstance(expires_in, int)
                or expires_in <= 0
            ):
                raise ValueError("Mealie reverse-proxy sign-in returned an unexpected response")
            margin = min(self._expiry_margin, expires_in / 2)
            return MealieToken(token, self._clock() + expires_in - margin)
        except httpx.HTTPStatusError as error:
            log_failure(EXCHANGE_OPERATION, error)
            status = error.response.status_code
            if status == 401:
                raise MealieAccountUnavailable() from None
            raise MealieApiError(status, "Mealie reverse-proxy sign-in failed") from None
        except httpx.TimeoutException as error:
            log_failure(EXCHANGE_OPERATION, error)
            raise TimeoutError("Mealie reverse-proxy sign-in timed out") from None
        except httpx.RequestError as error:
            log_failure(EXCHANGE_OPERATION, error)
            raise ConnectionError("Could not connect to Mealie for reverse-proxy sign-in") from None
        except ValueError as error:
            log_failure(EXCHANGE_OPERATION, error)
            raise
        finally:
            http.close()
