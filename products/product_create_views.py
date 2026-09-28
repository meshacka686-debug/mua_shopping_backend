from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .customer_models import CustomerProduct
from .models import Product
from .product_create_service import (
    create_customer_product_with_details,
    create_shop_product_with_details,
)


class CreateShopProductWithDetailsView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        user = request.user

        if not user.is_authenticated:
            return Response(
                {"detail": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if getattr(user, "role", None) not in {"shop", "shop_owner"}:
            return Response(
                {"detail": "Only shop owners can create shop products."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            shop = user.shop
        except Exception:
            return Response(
                {"detail": "No shop is linked to this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        images = request.FILES.getlist("images")
        video = request.FILES.get("video")

        if images and video:
            return Response(
                {
                    "detail": (
                        "Choose either product pictures or a video, "
                        "not both."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not images and not video:
            return Response(
                {
                    "detail": (
                        "At least one product picture or video is required."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            product = create_shop_product_with_details(
                shop=shop,
                data=request.data,
                images=images,
                video=video,
            )
        except (ValueError, TypeError) as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "message": "Product created successfully.",
                "product_id": product.id,
                "product_type": "shop",
            },
            status=status.HTTP_201_CREATED,
        )


class CreateCustomerProductWithDetailsView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        user = request.user

        if not user.is_authenticated:
            return Response(
                {"detail": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if getattr(user, "role", None) != "customer":
            return Response(
                {
                    "detail": "Only customers can create customer products."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        images = request.FILES.getlist("images")
        video = request.FILES.get("video")

        try:
            product = create_customer_product_with_details(
                seller=user,
                data=request.data,
                images=images,
                video=video,
            )
        except (ValueError, TypeError) as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "message": "Customer product created successfully.",
                "product_id": product.id,
                "product_type": "customer",
            },
            status=status.HTTP_201_CREATED,
        )
