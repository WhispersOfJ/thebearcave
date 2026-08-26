import logging

from django.utils import timezone
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import APIView, exception_handler

from core.authentication import SessionOrApiKeyAuthentication
from core.permissions import IsAuthenticatedOrServiceKey

logger = logging.getLogger(__name__)


class ServiceError(APIException):
    """Raised by any services.py function to signal a failure that should
    render as the {ok:false, message} envelope, mirroring FastAPI-era
    core.responses.fail(). status_code defaults to 502 (bad upstream) to
    match the old default; pass status= to override (404, 409, etc.).

    fail() always did `logger.error(message)` before raising its
    HTTPException. That per-call logging was dropped when the 28 call
    sites across the ported client modules were switched to
    `raise ServiceError(...)` directly. Logging it once here - at
    construction, i.e. the same moment fail() used to log - restores
    identical behavior without re-adding logger.error() at every call
    site: every ServiceError that gets raised is logged server-side
    exactly once, with the same message text a human would see in the
    envelope."""

    def __init__(self, message: str, status: int = 502):
        self.status_code = status
        logger.error(message)
        super().__init__(detail=message)


def envelope_exception_handler(exc, context):
    if not isinstance(exc, ServiceError):
        return exception_handler(exc, context)
    return Response({"ok": False, "message": str(exc.detail)}, status=exc.status_code)


class ConfirmMixin:
    """Mixin that gates a POST on confirm=true in the request body.

    Subclasses pass a serializer with a BooleanField('confirm') to
    check_confirm(), which raises ServiceError(400) if not confirmed.
    Shared by host_actions and catalog views to avoid inlining the
    same pattern in every mutating endpoint.
    """

    def check_confirm(self, request, serializer_class) -> dict:
        """Validate request body and enforce confirm=true. Returns
        validated_data on success."""
        body = serializer_class(data=request.data)
        body.is_valid(raise_exception=True)
        if not body.validated_data["confirm"]:
            raise ServiceError(
                "Set confirm=true to proceed - this is a real action.",
                status=400,
            )
        return body.validated_data


class EnvelopeAPIView(APIView):
    authentication_classes = [SessionOrApiKeyAuthentication]
    permission_classes = [IsAuthenticatedOrServiceKey]

    def ok(self, message: str, **extra) -> Response:
        return Response({
            "ok": True,
            "message": message,
            "time": timezone.now().strftime("%H:%M:%S"),
            **extra,
        })
