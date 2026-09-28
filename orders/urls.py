from django.urls import path

from .views import (
    MyOrdersView,
    MyOrderDetailView,
    ShopOrdersView,
    ShopOrderStatusView,
    CustomerDeliveryStatusView,
    CustomerCancelOrderView,
    MyCustomerProductOrdersView,
)


urlpatterns = [

    # ============================================================
    # CUSTOMER ORDERS
    # ============================================================

    path(
        "",
        MyOrdersView.as_view(),
        name="my-orders",
    ),

    path(
        "<int:pk>/",
        MyOrderDetailView.as_view(),
        name="my-order-detail",
    ),

    path(
        "my-products/",
        MyCustomerProductOrdersView.as_view(),
        name="my-customer-product-orders",
    ),


    # ============================================================
    # SHOP ORDERS
    # ============================================================

    path(
        "shop/",
        ShopOrdersView.as_view(),
        name="shop-orders",
    ),

    path(
        "shop/<int:pk>/status/",
        ShopOrderStatusView.as_view(),
        name="shop-order-status",
    ),

    # ============================================================
    # CUSTOMER DELIVERY RESPONSE
    # ============================================================

    path(
        "<int:pk>/delivery-status/",
        CustomerDeliveryStatusView.as_view(),
        name="customer-delivery-status",
    ),
    path(
        "<int:pk>/cancel/",
        CustomerCancelOrderView.as_view(),
        name="customer-cancel-order",
    ),
]