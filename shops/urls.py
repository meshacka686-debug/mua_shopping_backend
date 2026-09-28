from django.urls import path

from .views import (
    MyShopView,
    ShopDetailView,
    ShopStatisticsView,
)


urlpatterns = [
    path(
        "my-shop/",
        MyShopView.as_view(),
        name="my-shop",
    ),

    path(
        "statistics/",
        ShopStatisticsView.as_view(),
        name="shop-statistics",
    ),

    path(
        "<int:pk>/",
        ShopDetailView.as_view(),
        name="shop-detail",
    ),
]