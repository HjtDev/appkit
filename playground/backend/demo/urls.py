from __future__ import annotations

from django.urls import path

from demo import views

app_name = "demo"

urlpatterns = [
    path("items/", views.DemoItemListView.as_view(), name="items"),
    path("items/invalidate/", views.DemoItemInvalidateView.as_view(), name="items-invalidate"),
    path("items/<int:pk>/", views.DemoItemDetailView.as_view(), name="item-detail"),
    path("notes/", views.SecretNoteListView.as_view(), name="notes"),
    path("echo/", views.EchoView.as_view(), name="echo"),
    path("admin/", views.DemoAdminView.as_view(), name="admin"),
    path("errors/validation/", views.ValidationErrorView.as_view(), name="err-validation"),
    path(
        "errors/not-authenticated/",
        views.UnauthenticatedView.as_view(),
        name="err-not-authenticated",
    ),
    # Same view as above: wrong Basic credentials -> authentication_failed instead of
    # not_authenticated. No separate view needed — the client controls which code fires.
    path(
        "errors/authentication-failed/",
        views.UnauthenticatedView.as_view(),
        name="err-authentication-failed",
    ),
    path(
        "errors/permission-denied/",
        views.PermissionDeniedView.as_view(),
        name="err-permission-denied",
    ),
    path("errors/not-found/", views.NotFoundView.as_view(), name="err-not-found"),
    path(
        "errors/method-not-allowed/",
        views.MethodNotAllowedView.as_view(),
        name="err-method-not-allowed",
    ),
    path("errors/server/", views.ServerErrorView.as_view(), name="err-server"),
    path("errors/catchall/", views.CatchAllErrorView.as_view(), name="err-catchall"),
    # errors/parse/ is deliberately absent — parse_error fires from ANY JSON-parsing view given
    # a malformed body; POST malformed JSON to items/ instead. See views.py's module docstring.
]
