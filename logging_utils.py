import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional

_LOGGER_ROOT = "splitpal"
_DEFAULT_FORMAT = os.getenv(
    "SPLITPAL_LOG_FORMAT",
    "%(asctime)s %(levelname)s %(name)s %(message)s user_id=%(user_id)s user_email=%(user_email)s request_method=%(request_method)s request_path=%(request_path)s",
)
_DEFAULT_DATEFMT = os.getenv("SPLITPAL_LOG_DATEFMT", "%Y-%m-%dT%H:%M:%S%z")
_DEFAULT_LEVEL = os.getenv("SPLITPAL_LOG_LEVEL", "INFO").upper()
_LOG_FILE = os.getenv("SPLITPAL_LOG_FILE", os.path.join("logs", "splitpal.log"))
_LOG_MAX_BYTES = int(os.getenv("SPLITPAL_LOG_MAX_BYTES", str(5 * 1024 * 1024)))
_LOG_BACKUP_COUNT = int(os.getenv("SPLITPAL_LOG_BACKUP_COUNT", "5"))


class _UserAwareFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        for attr, default in (
            ("user_id", "-"),
            ("user_email", "-"),
            ("request_method", "-"),
            ("request_path", "-"),
        ):
            if not hasattr(record, attr) or getattr(record, attr) in (None, ""):
                setattr(record, attr, default)
        return super().format(record)


def _configure_root_logger() -> None:
    level = getattr(logging, _DEFAULT_LEVEL, logging.INFO)
    root_logger = logging.getLogger(_LOGGER_ROOT)
    if not root_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(_UserAwareFormatter(_DEFAULT_FORMAT, _DEFAULT_DATEFMT))
        root_logger.addHandler(handler)
        file_handler = _create_file_handler()
        if file_handler is not None:
            root_logger.addHandler(file_handler)
    root_logger.setLevel(level)
    root_logger.propagate = False


def _create_file_handler() -> Optional[logging.Handler]:
    if not _LOG_FILE or not _LOG_FILE.strip():
        return None
    try:
        log_path = Path(_LOG_FILE)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            str(log_path),
            maxBytes=max(_LOG_MAX_BYTES, 0),
            backupCount=max(_LOG_BACKUP_COUNT, 0),
            encoding="utf-8",
        )
        handler.setFormatter(_UserAwareFormatter(_DEFAULT_FORMAT, _DEFAULT_DATEFMT))
        return handler
    except Exception:
        return None


class RequestLoggerAdapter(logging.LoggerAdapter):
    def process(self, msg: Any, kwargs: Dict[str, Any]) -> Any:
        extra = dict(self.extra)
        supplied = kwargs.get("extra")
        if supplied:
            extra.update(supplied)
        kwargs["extra"] = extra
        return msg, kwargs


def get_logger(name: str) -> logging.Logger:
    _configure_root_logger()
    logger_name = f"{_LOGGER_ROOT}.{name}" if name else _LOGGER_ROOT
    return logging.getLogger(logger_name)


def _user_context(
    user: Optional[Any] = None,
    *,
    user_id: Optional[Any] = None,
    user_email: Optional[str] = None,
) -> Dict[str, str]:
    resolved_id = None
    if user_id is not None:
        resolved_id = user_id
    elif user is not None and getattr(user, "id", None) is not None:
        resolved_id = getattr(user, "id")
    resolved_email = None
    if user_email is not None:
        resolved_email = user_email
    elif user is not None:
        resolved_email = getattr(user, "email", None)
    return {
        "user_id": str(resolved_id) if resolved_id not in (None, "") else "-",
        "user_email": resolved_email or "-",
    }


def get_request_logger(
    name: str,
    *,
    req: Optional[Any] = None,
    user: Optional[Any] = None,
    user_id: Optional[Any] = None,
    user_email: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> RequestLoggerAdapter:
    base_logger = get_logger(name)
    context: Dict[str, Any] = {}
    if req is not None:
        context["request_method"] = getattr(req, "method", "-")
        context["request_path"] = getattr(req, "url", "-")
        headers = getattr(req, "headers", None)
        if headers:
            request_id = headers.get("x-ms-request-id") or headers.get("x-request-id")
            if request_id:
                context["request_id"] = request_id
            client_ip = headers.get("x-forwarded-for") or headers.get("client-ip")
            if client_ip:
                context["client_ip"] = client_ip
    context.update(_user_context(user, user_id=user_id, user_email=user_email))
    if extra:
        context.update(extra)
    return RequestLoggerAdapter(base_logger, context)


def ensure_request_logger(
    req: Any,
    *,
    name: str,
    user: Optional[Any] = None,
    user_id: Optional[Any] = None,
    user_email: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> RequestLoggerAdapter:
    adapter = getattr(req, "log", None)
    if isinstance(adapter, RequestLoggerAdapter):
        context_updates: Dict[str, Any] = {}
        if any(value is not None for value in (user, user_id, user_email)):
            context_updates.update(_user_context(user, user_id=user_id, user_email=user_email))
        if extra:
            context_updates.update(extra)
        adapter.extra.update({k: v for k, v in context_updates.items() if v is not None})
        return adapter
    adapter = get_request_logger(
        name,
        req=req,
        user=user,
        user_id=user_id,
        user_email=user_email,
        extra=extra,
    )
    setattr(req, "log", adapter)
    return adapter
