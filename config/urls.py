from django.contrib import admin
from django.urls import include, path

handler403 = "accounts.views.forbidden"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("accounts.urls")),
    path("", include("catalog.urls")),
    path("", include("subscriptions.urls")),
    path("", include("billing.urls")),
    path("", include("payments.urls")),
]
