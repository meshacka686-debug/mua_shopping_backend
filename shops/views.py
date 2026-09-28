from decimal import Decimal

from django.db.models import (
    DecimalField,
    ExpressionWrapper,
    F,
    Sum,
)

from rest_framework import permissions, status
from rest_framework.parsers import (
    FormParser,
    MultiPartParser,
    JSONParser,
)
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Shop
from .serializers import ShopSerializer


class IsShopOwner(permissions.BasePermission):
    """
    Allows access only to authenticated shop-owner accounts.
    """

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == "shop_owner"
        )


class MyShopView(APIView):
    """
    GET   /api/shops/my-shop/
    PUT   /api/shops/my-shop/
    PATCH /api/shops/my-shop/
    """

    permission_classes = [IsShopOwner]

    parser_classes = [
        MultiPartParser,
        FormParser,
        JSONParser,
    ]

    def get_shop(self, request):
        shop, created = Shop.objects.get_or_create(
            owner=request.user,
            defaults={
                "name": request.user.username,
                "phone": getattr(
                    request.user,
                    "phone",
                    "",
                ) or "",
            },
        )

        return shop

    def get(self, request):
        shop = self.get_shop(request)

        serializer = ShopSerializer(
            shop,
            context={"request": request},
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    def put(self, request):
        shop = self.get_shop(request)

        serializer = ShopSerializer(
            shop,
            data=request.data,
            partial=False,
            context={"request": request},
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    def patch(self, request):
        shop = self.get_shop(request)

        serializer = ShopSerializer(
            shop,
            data=request.data,
            partial=True,
            context={"request": request},
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


class ShopDetailView(APIView):
    """
    GET /api/shops/<id>/

    Public shop details.
    """

    permission_classes = [
        permissions.AllowAny
    ]

    def get(self, request, pk):
        try:
            shop = Shop.objects.get(pk=pk)
        except Shop.DoesNotExist:
            return Response(
                {
                    "detail": "Shop not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ShopSerializer(
            shop,
            context={"request": request},
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


class ShopStatisticsView(APIView):
    """
    GET /api/shops/statistics/

    Returns statistics for the logged-in shop owner.
    """

    permission_classes = [IsShopOwner]

    def get(self, request):

        from products.models import Product
        from orders.models import OrderItem

        try:
            shop = request.user.shop
        except Shop.DoesNotExist:
            return Response(
                {
                    "products": 0,
                    "orders": 0,
                    "sales": "0.00",
                    "commission": "0.00",
                },
                status=status.HTTP_200_OK,
            )

        # ========================================================
        # PRODUCTS
        # ========================================================

        product_count = Product.objects.filter(
            shop=shop
        ).count()

        # ========================================================
        # SHOP ORDER ITEMS
        # ========================================================

        shop_items = OrderItem.objects.filter(
            product__shop=shop
        ).exclude(
            order__status="cancelled"
        )

        # ========================================================
        # ORDERS
        # ========================================================

        order_count = (
            shop_items
            .values("order_id")
            .distinct()
            .count()
        )

        # ========================================================
        # SALES
        # ========================================================

        sales_expression = ExpressionWrapper(
            F("price") * F("quantity"),
            output_field=DecimalField(
                max_digits=14,
                decimal_places=2,
            ),
        )

        sales = (
            shop_items
            .aggregate(
                total=Sum(sales_expression)
            )["total"]
            or Decimal("0.00")
        )

        sales = Decimal(sales).quantize(
            Decimal("0.01")
        )

        # ========================================================
        # COMMISSION
        # ========================================================

        commission = (
            sales * Decimal("0.10")
        ).quantize(
            Decimal("0.01")
        )

        # ========================================================
        # RESPONSE
        # ========================================================

        return Response(
            {
                "products": product_count,
                "orders": order_count,
                "sales": str(sales),
                "commission": str(commission),
            },
            status=status.HTTP_200_OK,
        )