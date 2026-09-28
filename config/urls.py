from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path(
        "admin/",
        admin.site.urls,
    ),

    # Authentication
    path(
        "api/auth/",
        include("accounts.urls"),
    ),

    # Products
    path(
        "api/products/",
        include("products.urls"),
    ),

    # Orders
    path(
        "api/orders/",
        include("orders.urls"),
    ),

    # Payments
    path(
        "api/payments/",
        include("payments.urls"),
    ),

    # Shops
    path(
        "api/shops/",
        include("shops.urls"),
    ),

    # Rents
    path(
        "api/rents/",
        include("rents.urls"),
    ),

    # Admin API
    path(
        "api/admin/",
        include("admin_api.urls"),
    ),

    # Social Media
    path(
        "api/social/",
        include("social.urls"),
    ),

    # Messaging
    path(
        "api/messaging/",
        include("messaging.urls"),
    ),
]


# Development only.
# Production media will be handled separately.
if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )
