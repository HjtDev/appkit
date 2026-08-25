"""The demo app's entire reason to exist: exercise every appkit integration point over real
HTTP. See playground/backend/demo/urls.py for the route table and
docs/CONTRACT.md §1 (lines 64-75) for the ten error codes each errors/* view is built to trigger.
"""

from __future__ import annotations

from typing import ClassVar

from django.http import Http404, HttpRequest, JsonResponse
from rest_framework import generics, permissions, status
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.exceptions import UnsupportedMediaType
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from appkit.cache import invalidate_namespace
from appkit.media import absolute_url
from appkit.mixins import CachedListMixin
from appkit.net import client_ip
from appkit.permissions import IsAppAdmin, IsObjectOwner
from appkit.request_id import request_id_var
from appkit.throttling import throttle_scope
from demo.models import DemoItem, SecretNote
from demo.serializers import DemoItemSerializer, SecretNoteSerializer

# ---------------------------------------------------------------------------------------------
# appkit.mixins.CachedListMixin + appkit.pagination.DefaultPagination + appkit.throttling
# ---------------------------------------------------------------------------------------------


class DemoItemListView(CachedListMixin, generics.ListCreateAPIView):
    """GET is cached per-user (CachedListMixin is hardcoded per_user=True) and paginated by
    appkit.pagination.DefaultPagination (wired globally in settings.REST_FRAMEWORK). POST is
    plain DRF create — CachedListMixin only overrides list().
    """

    serializer_class = DemoItemSerializer
    cache_namespace = "demo_items"
    throttle_scope = throttle_scope("demo", "list")
    permission_classes: ClassVar = [IsAuthenticated]

    def get_queryset(self) -> object:
        return DemoItem.objects.all()

    def perform_create(self, serializer: DemoItemSerializer) -> None:
        serializer.save(owner=self.request.user)


class DemoItemInvalidateView(APIView):
    """POST invalidates the "demo_items" cache namespace — appkit.cache.invalidate_namespace."""

    permission_classes: ClassVar = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        new_version = invalidate_namespace("demo_items")
        return Response({"namespace": "demo_items", "version": new_version})


class DemoItemDetailView(generics.RetrieveDestroyAPIView):
    """Object-level ownership check — appkit.permissions.IsObjectOwner, the IDOR case."""

    serializer_class = DemoItemSerializer
    queryset = DemoItem.objects.all()
    permission_classes: ClassVar = [IsAuthenticated, IsObjectOwner]
    owner_field = "owner"

    def get_object(self) -> DemoItem:
        obj = super().get_object()
        self.check_object_permissions(self.request, obj)
        return obj


# ---------------------------------------------------------------------------------------------
# appkit.net.client_ip + appkit.media.absolute_url + appkit.request_id.request_id_var
# ---------------------------------------------------------------------------------------------


class EchoView(APIView):
    """Echoes what appkit resolved for this exact request — the thing only a live proxy chain
    can prove right or wrong (docs/CONTRACT.md §2.10).
    """

    permission_classes: ClassVar = [permissions.AllowAny]

    def get(self, request: Request) -> Response:
        return Response(
            {
                "client_ip": client_ip(request),
                "media_url": absolute_url("/media/demo/probe.txt", request=request),
                "request_id": request_id_var.get(),
                "remote_addr": request.META.get("REMOTE_ADDR", ""),
                "x_forwarded_for": request.META.get("HTTP_X_FORWARDED_FOR", ""),
                "x_forwarded_proto": request.META.get("HTTP_X_FORWARDED_PROTO", ""),
                "is_secure": request.is_secure(),
            }
        )


# ---------------------------------------------------------------------------------------------
# appkit.crypto (via demo.fields.EncryptedTextField) + appkit.files (crypto / images extras)
# ---------------------------------------------------------------------------------------------


class SecretNoteListView(generics.ListCreateAPIView):
    serializer_class = SecretNoteSerializer
    permission_classes: ClassVar = [IsAuthenticated]
    parser_classes: ClassVar = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self) -> object:
        return SecretNote.objects.filter(owner=self.request.user)

    def perform_create(self, serializer: SecretNoteSerializer) -> None:
        serializer.save(owner=self.request.user)


# ---------------------------------------------------------------------------------------------
# appkit.permissions.IsAppAdmin
# ---------------------------------------------------------------------------------------------


class DemoAdminView(APIView):
    permission_classes: ClassVar = [IsAppAdmin]

    def get(self, request: Request) -> Response:
        return Response({"ok": True, "who": str(request.user)})


# ---------------------------------------------------------------------------------------------
# The ten error-envelope codes — docs/CONTRACT.md §1, lines 64-75.
#
# "parse_error" has no dedicated view: it fires from ANY JSON-parsing view (e.g. POST malformed
# JSON to /api/v1/demo/items/) — DRF's JSONParser raises ParseError before a view's own code
# ever runs, so a purpose-built endpoint for it would be redundant.
# ---------------------------------------------------------------------------------------------


class ValidationErrorView(APIView):
    """POST any body with a blank/missing "name" -> validation_error (400)."""

    permission_classes: ClassVar = [permissions.AllowAny]

    def post(self, request: Request) -> Response:
        serializer = DemoItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data)


class UnauthenticatedView(APIView):
    """No credentials -> not_authenticated (401) with a real WWW-Authenticate, because
    BasicAuthentication supplies authenticate_header (tests/backend/urls_errors.py's pattern) —
    without it DRF's handle_exception silently downgrades to a bare 403.
    """

    authentication_classes: ClassVar = [BasicAuthentication]
    permission_classes: ClassVar = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return Response({"ok": True})


class PermissionDeniedView(APIView):
    """Authenticated but non-staff -> permission_denied (403), via appkit.permissions.IsAppAdmin."""

    authentication_classes: ClassVar = [SessionAuthentication, BasicAuthentication]
    permission_classes: ClassVar = [IsAuthenticated, IsAppAdmin]

    def get(self, request: Request) -> Response:
        return Response({"ok": True})


class NotFoundView(APIView):
    """Raises Http404 explicitly -> not_found (404). Deliberately NOT a URL miss — a URL that
    matches no urlpattern never reaches DRF's exception_handler at all.
    """

    permission_classes: ClassVar = [permissions.AllowAny]

    def get(self, request: Request) -> Response:
        raise Http404("No such demo object.")


class MethodNotAllowedView(APIView):
    """GET-only view; POST -> method_not_allowed (405)."""

    permission_classes: ClassVar = [permissions.AllowAny]

    def get(self, request: Request) -> Response:
        return Response({"ok": True})


class ServerErrorView(APIView):
    """Raises an unhandled exception -> server_error (500), DEBUG=False so the message is the
    generic "Internal server error." (appkit.exceptions.standard_exception_handler).
    """

    permission_classes: ClassVar = [permissions.AllowAny]

    def get(self, request: Request) -> Response:
        return Response({"boom": 1 / 0})  # noqa: B018 - deliberate ZeroDivisionError


class CatchAllErrorView(APIView):
    """Raises UnsupportedMediaType (415) -> the documented "error" catch-all (HTTP status is
    authoritative, not the code — docs/CONTRACT.md §1 rule 2).
    """

    permission_classes: ClassVar = [permissions.AllowAny]

    def get(self, request: Request) -> Response:
        raise UnsupportedMediaType("application/x-demo-unsupported")


def healthz(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"}, status=status.HTTP_200_OK)
