import json
import azure.functions as func
from http_utils import apply_cors, preflight_response


def main(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return preflight_response()
    payload = {"status": "ok"}
    return apply_cors(func.HttpResponse(json.dumps(payload), status_code=200, mimetype="application/json"))
