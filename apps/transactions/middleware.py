import logging
import time

logger = logging.getLogger("transactions.middleware")


def log_response_time(func):
    """Decorador que registra el tiempo de respuesta de una función de vista."""

    def wrapper(*args, **kwargs):
        start = time.monotonic()
        response = func(*args, **kwargs)
        elapsed_ms = (time.monotonic() - start) * 1000
        logger.info(
            "view=%s method=%s status=%s duration_ms=%.2f",
            func.__qualname__,
            args[1].method if len(args) > 1 else "UNKNOWN",
            response.status_code,
            elapsed_ms,
        )
        return response

    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


class ResponseTimeMiddleware:
    """Middleware que registra el tiempo de respuesta de cada request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.monotonic()
        response = self.get_response(request)
        elapsed_ms = (time.monotonic() - start) * 1000
        logger.info(
            "path=%s method=%s status=%s duration_ms=%.2f",
            request.path,
            request.method,
            response.status_code,
            elapsed_ms,
        )
        return response
