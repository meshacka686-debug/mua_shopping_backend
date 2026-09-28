from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F, Q

from .models import Product, ProductLike
from .serializers import ProductSerializer


class IsShopOwnerMixin:
    def check_shop_owner(self):
        user = self.request.user

        if not user.is_authenticated:
            raise PermissionDenied("Authentication is required.")

        if user.role != "shop_owner":
            raise PermissionDenied(
                "Only shop owners can manage products."
            )

        try:
            shop = user.shop
        except Exception:
            raise ValidationError(
                {
                    "shop": (
                        "This account does not have a shop. "
                        "Please create a shop first."
                    )
                }
            )

        if not shop.is_active:
            raise PermissionDenied(
                "Your shop is currently inactive."
            )

        return shop


class ProductListCreateView(
    IsShopOwnerMixin,
    generics.ListCreateAPIView,
):
    """
    GET  /api/products/
        Public list of available products.

    POST /api/products/
        Shop owner creates a product.
    """

    serializer_class = ProductSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated()]

        return [AllowAny()]

    def get_queryset(self):
        queryset = Product.objects.filter(
            is_available=True,
            shop__is_active=True,
        ).select_related("shop")

        search = self.request.query_params.get("search", "").strip()

        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(description__icontains=search)
                | Q(category__icontains=search)
                | Q(shop__name__icontains=search)
            )

        return queryset

    def perform_create(self, serializer):
        shop = self.check_shop_owner()
        serializer.save(shop=shop)


class ProductDetailView(generics.RetrieveAPIView):
    """
    GET /api/products/<id>/

    Public product details.
    """

    queryset = Product.objects.filter(
        is_available=True,
        shop__is_active=True,
    ).select_related("shop")

    serializer_class = ProductSerializer
    permission_classes = [AllowAny]


class MyProductsView(
    IsShopOwnerMixin,
    generics.ListCreateAPIView,
):
    """
    GET  /api/products/my/
    POST /api/products/my/

    Shop owner's own products.
    """

    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Product.objects.filter(
            shop__owner=self.request.user
        ).select_related("shop")

    def perform_create(self, serializer):
        shop = self.check_shop_owner()
        serializer.save(shop=shop)


class MyProductDetailView(
    IsShopOwnerMixin,
    generics.RetrieveUpdateDestroyAPIView,
):
    """
    GET    /api/products/my/<id>/
    PUT    /api/products/my/<id>/
    PATCH  /api/products/my/<id>/
    DELETE /api/products/my/<id/>

    Shop owner can manage their own products.

    DELETE behavior:
    - Product with no active orders -> permanently deleted.
    - Product with an active order -> deletion is blocked.
    - Completed/delivered/cancelled historical orders do not block deletion.
    """

    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Product.objects.filter(
            shop__owner=self.request.user
        ).select_related("shop")

    def update(self, request, *args, **kwargs):
        self.check_shop_owner()
        return super().update(request, *args, **kwargs)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        self.check_shop_owner()

        product = self.get_object()

        from orders.models import OrderItem

        # Only orders that are still in progress block deletion.
        # Historical delivered/cancelled orders do not block deletion.
        active_statuses = [
            "pending",
            "confirmed",
            "processing",
            "shipped",
        ]

        has_active_order = OrderItem.objects.filter(
            product=product,
            order__status__in=active_statuses,
        ).exists()

        if has_active_order:
            raise ValidationError(
                {
                    "detail": (
                        "This product cannot be deleted because "
                        "it has an active order in progress. "
                        "Wait until the order is completed or cancelled."
                    )
                }
            )

        product.delete()

        return Response(
            {
                "detail": "Product deleted successfully."
            },
            status=status.HTTP_204_NO_CONTENT,
        )

class ProductLikeToggleView(generics.GenericAPIView):
    """
    GET  /api/products/<id>/like/
        Return the customer's current like state and total likes.

    POST /api/products/<id>/like/
        Toggle like/unlike for the authenticated customer.
    """

    queryset = Product.objects.filter(
        is_available=True,
        shop__is_active=True,
    )
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def get(self, request, pk):
        product = self.get_object()

        liked = ProductLike.objects.filter(
            customer=request.user,
            product=product,
        ).exists()

        product.refresh_from_db(fields=["likes"])

        return Response(
            {
                "product_id": product.id,
                "liked": liked,
                "likes": product.likes,
            }
        )

    @transaction.atomic
    def post(self, request, pk):
        product = self.get_object()

        like = ProductLike.objects.filter(
            customer=request.user,
            product=product,
        ).first()

        if like:
            like.delete()

            Product.objects.filter(
                pk=product.pk,
                likes__gt=0,
            ).update(
                likes=F("likes") - 1
            )

            liked = False

        else:
            ProductLike.objects.create(
                customer=request.user,
                product=product,
            )

            Product.objects.filter(
                pk=product.pk,
            ).update(
                likes=F("likes") + 1
            )

            liked = True

        product.refresh_from_db(fields=["likes"])

        return Response(
            {
                "product_id": product.id,
                "liked": liked,
                "likes": product.likes,
            }
        )
