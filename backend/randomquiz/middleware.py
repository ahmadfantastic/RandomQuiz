import logging

from django.db import connections
from django.db.utils import OperationalError

logger = logging.getLogger(__name__)
SAFE_METHODS = frozenset({'GET', 'HEAD', 'OPTIONS'})


class RetryDatabaseConnectionMiddleware:
    """Retry once on GET/HEAD/OPTIONS when the database connection dies mid-request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except OperationalError as exc:
            if request.method not in SAFE_METHODS:
                raise
            logger.warning(
                'Database connection died handling %s %s; retrying once',
                request.method,
                request.path,
                exc_info=exc,
            )
            connections.close_all()
            return self.get_response(request)
