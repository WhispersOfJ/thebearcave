"""Tests for core.api_base.ConfirmMixin — the shared confirm=true gate."""
import pytest
from rest_framework import serializers
from rest_framework.test import APIRequestFactory, force_authenticate

from core.api_base import ConfirmMixin, EnvelopeAPIView, ServiceError
from core.authentication import AnonymousServiceUser


class _ConfirmSerializer(serializers.Serializer):
    confirm = serializers.BooleanField(default=False)


class _ExtraConfirmSerializer(serializers.Serializer):
    confirm = serializers.BooleanField(default=False)
    extra = serializers.BooleanField(default=False)


class _TestView(ConfirmMixin, EnvelopeAPIView):
    def post(self, request):
        data = self.check_confirm(request, _ConfirmSerializer)
        return self.ok("confirmed", data=data)


class _TestExtraView(ConfirmMixin, EnvelopeAPIView):
    def post(self, request):
        data = self.check_confirm(request, _ExtraConfirmSerializer)
        return self.ok("confirmed", extra=data.get("extra"))


factory = APIRequestFactory()


def _authed_request(method, path="/", data=None, **kwargs):
    """Create an API request with a fake authenticated user."""
    request = factory.post(path, data or {}, format="json", **kwargs)
    force_authenticate(request, user=AnonymousServiceUser())
    return request


class TestConfirmMixin:
    def test_confirm_true_passes(self):
        request = _authed_request("post", data={"confirm": True})
        view = _TestView.as_view()
        response = view(request)
        assert response.data["ok"] is True

    def test_confirm_false_returns_400(self):
        request = _authed_request("post", data={"confirm": False})
        view = _TestView.as_view()
        response = view(request)
        assert response.status_code == 400
        assert response.data["ok"] is False
        assert "confirm=true" in response.data["message"]

    def test_missing_confirm_defaults_false_returns_400(self):
        request = _authed_request("post", data={})
        view = _TestView.as_view()
        response = view(request)
        assert response.status_code == 400
        assert response.data["ok"] is False

    def test_extra_fields_pass_through(self):
        request = _authed_request("post", data={"confirm": True, "extra": True})
        view = _TestExtraView.as_view()
        response = view(request)
        assert response.data["ok"] is True
        assert response.data["extra"] is True
