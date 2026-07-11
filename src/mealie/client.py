import json
import logging
import traceback
from typing import Any, Dict

import httpx
from httpx import ConnectError, HTTPStatusError, ReadTimeout

logger = logging.getLogger("mealie-mcp")


class MealieApiError(Exception):
    """Custom exception for Mealie API errors with status code and response details."""

    def __init__(self, status_code: int, message: str, response_text: str = None):
        self.status_code = status_code
        self.message = message
        self.response_text = response_text
        super().__init__(f"{message} (Status Code: {status_code})")


class MealieClient:

    def __init__(self, base_url: str, api_key: str):
        if not base_url:
            raise ValueError("Base URL cannot be empty")
        if not api_key:
            raise ValueError("API key cannot be empty")

        logger.debug({"message": "Initializing MealieClient", "base_url": base_url})
        try:
            self._client = httpx.Client(
                base_url=base_url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    # Don't set Content-Type here - let httpx set it per request
                    # This allows multipart/form-data uploads to work correctly
                },
                timeout=30.0,  # Set a reasonable timeout for requests
            )
            # Test connection
            logger.debug({"message": "Testing connection to Mealie API"})
            response = self._client.get("/api/app/about")
            response.raise_for_status()
            logger.info({"message": "Successfully connected to Mealie API"})
        except ConnectError as e:
            error_msg = f"Failed to connect to Mealie API at {base_url}: {str(e)}"
            logger.error({"message": error_msg})
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
            raise ConnectionError(error_msg) from e
        except Exception as e:
            error_msg = f"Error initializing Mealie client: {str(e)}"
            logger.error({"message": error_msg})
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
            raise

    def _handle_request(self, method: str, url: str, **kwargs) -> Dict[str, Any] | str:
        """Common request handler with error handling for all API calls.

        Supports:
        - JSON requests via json= parameter
        - Multipart uploads via files= parameter
        - Form data via data= parameter
        """
        try:
            logger.debug(
                {
                    "message": "Making API request",
                    "method": method,
                    "url": url,
                    "has_files": "files" in kwargs,
                }
            )
            if "files" in kwargs:
                logger.debug({"message": "Request has file upload"})

            # For JSON requests, explicitly set Content-Type
            # For multipart requests (files), httpx will set the correct Content-Type with boundary
            if "json" in kwargs and "files" not in kwargs:
                if "headers" not in kwargs:
                    kwargs["headers"] = {}
                kwargs["headers"]["Content-Type"] = "application/json"

            response = self._client.request(method, url, **kwargs)
            response.raise_for_status()  # Raise an exception for 4XX/5XX responses

            logger.debug(
                {"message": "Request successful", "status_code": response.status_code}
            )

            # Handle empty responses (common for DELETE operations)
            if response.status_code == 204 or (not response.content or len(response.content) == 0):
                logger.debug({"message": "Response has no content (likely successful DELETE)"})
                return {"success": True, "message": "Operation completed successfully"}

            # Log the response content at debug level
            try:
                response_data = response.json()
                # Normalize JSON null to success dict (common for DELETE operations)
                if response_data is None:
                    logger.debug(
                        {"message": "Response content is null; normalizing to success payload"}
                    )
                    return {"success": True, "message": "Operation completed successfully"}

                logger.debug({"message": "Response content", "data": response_data})
                return response_data
            except json.JSONDecodeError:
                # If we can't decode JSON but got a successful response, treat as success
                if response.status_code >= 200 and response.status_code < 300:
                    logger.debug(
                        {"message": "Response content (non-JSON but successful)", "content": response.text}
                    )
                    if not response.text or response.text.strip() == "":
                        return {"success": True, "message": "Operation completed successfully"}
                    return response.text
                else:
                    return response.text

        except HTTPStatusError as e:
            status_code = e.response.status_code
            error_detail = f"HTTP Error {status_code}"

            # Try to parse error details from response
            try:
                error_detail = e.response.json()
            except Exception:
                error_detail = e.response.text

            error_msg = f"API error for {method} {url}: {error_detail}"
            logger.error(
                {
                    "message": "API request failed",
                    "method": method,
                    "url": url,
                    "status_code": status_code,
                    "error_detail": error_detail,
                }
            )
            raise MealieApiError(status_code, error_msg, e.response.text) from e

        except ReadTimeout:
            error_msg = f"Request timeout for {method} {url}"
            logger.error({"message": error_msg, "method": method, "url": url})
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
            raise TimeoutError(error_msg)

        except ConnectError as e:
            error_msg = f"Connection error for {method} {url}: {str(e)}"
            logger.error(
                {"message": error_msg, "method": method, "url": url, "error": str(e)}
            )
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
            raise ConnectionError(error_msg) from e

        except Exception as e:
            error_msg = f"Unexpected error for {method} {url}: {str(e)}"
            logger.error(
                {"message": error_msg, "method": method, "url": url, "error": str(e)}
            )
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
            raise

    def close(self) -> None:
        """Release the underlying HTTP connection pool."""
        self._client.close()
