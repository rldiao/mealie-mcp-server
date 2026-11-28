import json


def format_error_response(error_message: str) -> str:
    """Format error responses consistently as JSON strings."""
    error_response = {"success": False, "error": error_message}
    return json.dumps(error_response)


def format_api_params(params: dict) -> dict:
    """Formats list and None values in a dictionary for API parameters."""
    output = {}
    for k, v in params.items():
        if v is None:
            continue
        output[k] = v
    return output
