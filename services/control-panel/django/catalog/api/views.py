"""Curated software catalog routes - list/status/install/remove for the
vetted programs in catalog/registry.py. Ported from
control-panel/services/catalog/router.py.

list/status use the default permission (IsAuthenticatedOrServiceKey) so
the catalog grid can render without a session hiccup. install/remove are
manual UI actions with no automation caller, so they require
IsAuthenticatedSessionOnly and gate on confirm=true in the view BEFORE
calling into services - matching host_actions' _ConfirmedActionView
pattern (see host_actions/api/views.py) and Task 7's review-fixed
landmine around it.
"""
from core.api_base import ConfirmMixin, EnvelopeAPIView
from core.permissions import IsAuthenticatedSessionOnly
from catalog import services
from catalog.api.serializers import InstallRequestSerializer, RemoveRequestSerializer


class CatalogListView(EnvelopeAPIView):
    def get(self, request):
        result = services.list_catalog()
        return self.ok(result["message"], items=result["items"])


class CatalogStatusView(EnvelopeAPIView):
    def get(self, request, catalog_id):
        result = services.get_status(catalog_id)
        extra = {k: v for k, v in result.items() if k != "message"}
        return self.ok(result["message"], **extra)


class CatalogInstallView(ConfirmMixin, EnvelopeAPIView):
    permission_classes = [IsAuthenticatedSessionOnly]

    def post(self, request, catalog_id):
        self.check_confirm(request, InstallRequestSerializer)
        result = services.install(catalog_id)
        return self.ok(result["message"], ports=result["ports"])


class CatalogRemoveView(ConfirmMixin, EnvelopeAPIView):
    permission_classes = [IsAuthenticatedSessionOnly]

    def post(self, request, catalog_id):
        data = self.check_confirm(request, RemoveRequestSerializer)
        result = services.remove(catalog_id, remove_volumes=data["remove_volumes"])
        return self.ok(result["message"])
