import os
from typing import Optional
from azure.functions import HttpResponse

_CORS_ALLOW_ORIGIN = os.environ.get("CORS_ALLOW_ORIGIN", "*")
_CORS_ALLOW_METHODS = os.environ.get(
    "CORS_ALLOW_METHODS",
    "GET,POST,PUT,PATCH,DELETE,OPTIONS"
)
_CORS_ALLOW_HEADERS = os.environ.get(
    "CORS_ALLOW_HEADERS",
    "Authorization,Content-Type"
)
_CORS_ALLOW_CREDENTIALS = os.environ.get("CORS_ALLOW_CREDENTIALS", "true")


def apply_cors(response: Optional[HttpResponse]) -> Optional[HttpResponse]:
    """Attach standard CORS headers to every HTTP response."""
    if response is None:
        return None
    response.headers["Access-Control-Allow-Origin"] = _CORS_ALLOW_ORIGIN
    response.headers["Access-Control-Allow-Methods"] = _CORS_ALLOW_METHODS
    response.headers["Access-Control-Allow-Headers"] = _CORS_ALLOW_HEADERS
    if _CORS_ALLOW_CREDENTIALS.lower() == "true" and _CORS_ALLOW_ORIGIN != "*":
        response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


def preflight_response() -> HttpResponse:
    """Return an empty 204 response for preflight OPTIONS requests."""
    return apply_cors(HttpResponse(status_code=204))
