from django.urls import path

from .views import (
    ProductListCreateView,
    ProductDetailView,
    MyProductsView,
    MyProductDetailView,
    ProductLikeToggleView,
)

from .feedback_views import (
    ShopProductFeedbackView,
    CustomerProductFeedbackView,
)


from .product_create_views import (
    CreateCustomerProductWithDetailsView,
    CreateShopProductWithDetailsView,
)

from .product_option_views import (
    ProductImageListCreateView,
    ProductImageDetailView,
    ProductOptionListCreateView,
    ProductOptionDetailView,
    ProductVariantListCreateView,
    ProductVariantDetailView,
)

from .customer_views import (
    CustomerProductListCreateView,
    CustomerProductDetailView,
    MyCustomerProductsView,
)


urlpatterns = [
path(
    "create-with-details/",
    CreateShopProductWithDetailsView.as_view(),
    name="create-shop-product-with-details",
),
path(
    "customer/create-with-details/",
    CreateCustomerProductWithDetailsView.as_view(),
    name="create-customer-product-with-details",
),

    # ============================================================
    # SHOP PRODUCTS
    # ============================================================

    path(
        "",
        ProductListCreateView.as_view(),
        name="product-list-create",
    ),

    path(
        "<int:pk>/",
        ProductDetailView.as_view(),
        name="product-detail",
    ),

    path(
        "<int:pk>/feedback/",
        ShopProductFeedbackView.as_view(),
        name="product-feedback",
    ),

    path(
        "<int:pk>/like/",
        ProductLikeToggleView.as_view(),
        name="product-like-toggle",
    ),


    path(
        "my/",
        MyProductsView.as_view(),
        name="my-products",
    ),

    path(
        "my/<int:pk>/",
        MyProductDetailView.as_view(),
        name="my-product-detail",
    ),


    # ============================================================
    # PRODUCT GALLERY / OPTIONS / VARIANTS
    # ============================================================

    path(
        "<str:product_type>/<int:pk>/images/",
        ProductImageListCreateView.as_view(),
        name="product-images",
    ),

    path(
        "<str:product_type>/<int:pk>/images/<int:image_id>/",
        ProductImageDetailView.as_view(),
        name="product-image-detail",
    ),

    path(
        "<str:product_type>/<int:pk>/options/",
        ProductOptionListCreateView.as_view(),
        name="product-options",
    ),

    path(
        "<str:product_type>/<int:pk>/options/<int:option_id>/",
        ProductOptionDetailView.as_view(),
        name="product-option-detail",
    ),

    path(
        "<str:product_type>/<int:pk>/variants/",
        ProductVariantListCreateView.as_view(),
        name="product-variants",
    ),

    path(
        "<str:product_type>/<int:pk>/variants/<int:variant_id>/",
        ProductVariantDetailView.as_view(),
        name="product-variant-detail",
    ),

    # ============================================================
    # CUSTOMER PRODUCTS
    # ============================================================

    path(
        "customer/",
        CustomerProductListCreateView.as_view(),
        name="customer-product-list-create",
    ),

    path(
        "customer/my/",
        MyCustomerProductsView.as_view(),
        name="my-customer-products",
    ),

    path(
        "customer/<int:pk>/",
        CustomerProductDetailView.as_view(),
        name="customer-product-detail",
    ),

    path(
        "customer/<int:pk>/feedback/",
        CustomerProductFeedbackView.as_view(),
        name="customer-product-feedback",
    ),
]
