import json

import azure.functions as func

from http_utils import apply_cors, preflight_response
from logging_utils import ensure_request_logger


def main(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return preflight_response()
    log = ensure_request_logger(req, name=__name__)
    log.debug("Health check ping received")
    payload = {"status": "ok"}
    return apply_cors(func.HttpResponse(json.dumps(payload), status_code=200, mimetype="application/json"))
