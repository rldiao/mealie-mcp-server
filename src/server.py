import logging
import os
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from typing import Any, Literal

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from mealie import MealieFetcher
from prompts import register_prompts
from tools import register_ai_import_tools, register_all_tools

logger = logging.getLogger("mealie-mcp")
Transport = Literal["stdio", "sse", "streamable-http"]


@dataclass(frozen=True)
class ServerConfig:
    base_url: str = field(repr=False)
    api_key: str = field(repr=False)
    transport: Transport = "stdio"
    host: str = "127.0.0.1"
    port: int = 8765
    log_level: str = "INFO"
    enable_ai_import: bool = False

    @classmethod
    def from_environment(cls) -> "ServerConfig":
        load_dotenv()
        ai_import = os.getenv("MEALIE_ENABLE_AI_IMPORT", "false").strip().lower()
        if ai_import not in ("true", "false"):
            raise ValueError("MEALIE_ENABLE_AI_IMPORT must be true or false")
        base_url = os.getenv("MEALIE_BASE_URL")
        api_key = os.getenv("MEALIE_API_KEY")
        if not base_url or not api_key:
            raise ValueError(
                "MEALIE_BASE_URL and MEALIE_API_KEY must be set in environment variables."
            )
        transport = os.getenv("MCP_TRANSPORT", "stdio")
        if transport not in ("stdio", "sse", "streamable-http"):
            raise ValueError("MCP_TRANSPORT must be stdio, sse, or streamable-http")
        try:
            port = int(os.getenv("MCP_PORT", "8765"))
        except ValueError:
            raise ValueError("MCP_PORT must be an integer between 1 and 65535") from None
        if not 1 <= port <= 65535:
            raise ValueError("MCP_PORT must be an integer between 1 and 65535")
        level = logging.getLevelNamesMapping().get(
            os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO
        )
        log_level = logging.getLevelName(level)
        if log_level not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            log_level = "INFO"
        return cls(
            base_url=base_url,
            api_key=api_key,
            transport=transport,
            host=os.getenv("MCP_HOST", "127.0.0.1"),
            port=port,
            log_level=log_level,
            enable_ai_import=ai_import == "true",
        )


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )
    logger.setLevel(level)


class _ClientProvider:
    def __init__(self, config: ServerConfig | None):
        self.config = config
        self._client: MealieFetcher | None = None
        self._users = 0

    def configuration(self) -> ServerConfig:
        if self.config is None:
            self.config = ServerConfig.from_environment()
        return self.config

    def __getattr__(self, name: str) -> Any:
        if self._client is None:
            raise RuntimeError("Mealie tools require an active server lifespan")
        return getattr(self._client, name)

    @contextmanager
    def acquire(self) -> Iterator[MealieFetcher]:
        if self._client is None:
            config = self.configuration()
            _configure_logging(config.log_level)
            self._client = MealieFetcher(config.base_url, config.api_key)
        self._users += 1
        try:
            yield self._client
        finally:
            self._users -= 1
            if self._users == 0:
                client, self._client = self._client, None
                client.close()

    @asynccontextmanager
    async def lifespan(self) -> AsyncIterator[MealieFetcher]:
        with self.acquire() as client:
            yield client


class _MealieServer(FastMCP):
    def __init__(self, config: ServerConfig | None):
        self.client_provider = _ClientProvider(config)
        self._ai_import_registered = False

        @asynccontextmanager
        async def lifespan(_: FastMCP) -> AsyncIterator[dict[str, MealieFetcher]]:
            self._configure_optional_tools()
            async with self.client_provider.lifespan() as client:
                yield {"mealie": client}

        super().__init__(
            "mealie",
            host=config.host if config else "127.0.0.1",
            port=config.port if config else 8765,
            log_level=config.log_level if config else "INFO",
            lifespan=lifespan,
        )

    def _configure_optional_tools(self) -> None:
        config = self.client_provider.configuration()
        if config.enable_ai_import and not self._ai_import_registered:
            register_ai_import_tools(self, self.client_provider)
            self._ai_import_registered = True

    def run(self, transport: Transport = "stdio", mount_path: str | None = None) -> None:
        config = self.client_provider.configuration()
        self._configure_optional_tools()
        self.settings.host = config.host
        self.settings.port = config.port
        self.settings.log_level = config.log_level
        _configure_logging(config.log_level)
        # Uvicorn consumes ASGI startup exceptions; fail before entering it so
        # unsuccessful health checks also produce a failing console exit status.
        with self.client_provider.acquire():
            super().run(transport=transport, mount_path=mount_path)

    def _application_lifespan(self, app):
        original_lifespan = app.router.lifespan_context

        @asynccontextmanager
        async def lifespan(application):
            self._configure_optional_tools()
            # SDK lifespans are per MCP session. HTTP also needs an outer owner
            # to check health at startup and keep the client alive between sessions.
            async with self.client_provider.lifespan():
                async with original_lifespan(application) as state:
                    yield state

        app.router.lifespan_context = lifespan
        return app

    def streamable_http_app(self):
        return self._application_lifespan(super().streamable_http_app())

    def sse_app(self, mount_path: str | None = None):
        return self._application_lifespan(super().sse_app(mount_path))


def create_server(config: ServerConfig | None = None) -> FastMCP:
    """Build a discoverable server without reading configuration or opening HTTP."""
    server = _MealieServer(config)
    register_prompts(server)
    register_all_tools(server, server.client_provider)
    if config is not None:
        server._configure_optional_tools()
    return server


# The SDK's `mcp dev` command discovers this instance without needing credentials.
mcp = create_server()


def main() -> None:
    try:
        config = ServerConfig.from_environment()
        _configure_logging(config.log_level)
        server = create_server(config)
        logger.info({"operation": "Starting Mealie MCP server"})
        server.run(transport=config.transport)
    except Exception as error:
        logger.critical(
            {"operation": "Running Mealie MCP server", "error_type": type(error).__name__}
        )
        raise


if __name__ == "__main__":
    main()
