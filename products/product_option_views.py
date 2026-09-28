from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.exceptions import PermissionDenied

from .models import Product
from .customer_models import CustomerProduct
from .product_options import (
    ProductImage,
    ProductOption,
    ProductVariant,
)
from .product_option_serializers import (
    ProductImageSerializer,
    ProductOptionSerializer,
    ProductVariantSerializer,
)


class ProductParentMixin:
    """
    Resolves either a shop Product or CustomerProduct.

    URL uses:
        product_type=shop
        product_type=customer
    """

    def get_parent(self):
        product_type = self.kwargs["product_type"]
        pk = self.kwargs["pk"]

        if product_type == "shop":
            return Product.objects.get(pk=pk)

        if product_type == "customer":
            return CustomerProduct.objects.get(pk=pk)

        raise PermissionDenied(
            "Invalid product type."
        )

    def check_owner(self, parent):
        user = self.request.user

        if not user.is_authenticated:
            raise PermissionDenied(
                "Authentication is required."
            )

        if isinstance(parent, Product):
            if user.role != "shop_owner":
                raise PermissionDenied(
                    "Only shop owners can manage shop products."
                )

            if parent.shop.owner != user:
                raise PermissionDenied(
                    "You can only manage your own products."
                )

        else:
            if user.role != "customer":
                raise PermissionDenied(
                    "Only customers can manage customer products."
                )

            if parent.seller != user:
                raise PermissionDenied(
                    "You can only manage your own products."
                )

        return user


class ProductImageListCreateView(
    ProductParentMixin,
    generics.ListCreateAPIView,
):
    serializer_class = ProductImageSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated()]

        return [AllowAny()]

    def get_queryset(self):
        parent = self.get_parent()

        if isinstance(parent, Product):
            return ProductImage.objects.filter(
                product=parent
            )

        return ProductImage.objects.filter(
            customer_product=parent
        )

    def perform_create(self, serializer):
        parent = self.get_parent()
        self.check_owner(parent)

        if isinstance(parent, Product):
            serializer.save(product=parent)
        else:
            serializer.save(customer_product=parent)


class ProductImageDetailView(
    ProductParentMixin,
    generics.RetrieveUpdateDestroyAPIView,
):
    serializer_class = ProductImageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        parent = self.get_parent()

        if isinstance(parent, Product):
            return ProductImage.objects.filter(
                product=parent
            )

        return ProductImage.objects.filter(
            customer_product=parent
        )

    def get_object(self):
        parent = self.get_parent()
        self.check_owner(parent)

        return super().get_object()


class ProductOptionListCreateView(
    ProductParentMixin,
    generics.ListCreateAPIView,
):
    serializer_class = ProductOptionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        parent = self.get_parent()

        if isinstance(parent, Product):
            return ProductOption.objects.filter(
                product=parent
            )

        return ProductOption.objects.filter(
            customer_product=parent
        )

    def perform_create(self, serializer):
        parent = self.get_parent()
        self.check_owner(parent)

        if isinstance(parent, Product):
            serializer.save(product=parent)
        else:
            serializer.save(customer_product=parent)


class ProductOptionDetailView(
    ProductParentMixin,
    generics.RetrieveUpdateDestroyAPIView,
):
    serializer_class = ProductOptionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        parent = self.get_parent()

        if isinstance(parent, Product):
            return ProductOption.objects.filter(
                product=parent
            )

        return ProductOption.objects.filter(
            customer_product=parent
        )

    def get_object(self):
        parent = self.get_parent()
        self.check_owner(parent)

        return super().get_object()


class ProductVariantListCreateView(
    ProductParentMixin,
    generics.ListCreateAPIView,
):
    serializer_class = ProductVariantSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        parent = self.get_parent()

        if isinstance(parent, Product):
            return ProductVariant.objects.filter(
                product=parent
            )

        return ProductVariant.objects.filter(
            customer_product=parent
        )

    def perform_create(self, serializer):
        parent = self.get_parent()
        self.check_owner(parent)

        if isinstance(parent, Product):
            serializer.save(product=parent)
        else:
            serializer.save(customer_product=parent)


class ProductVariantDetailView(
    ProductParentMixin,
    generics.RetrieveUpdateDestroyAPIView,
):
    serializer_class = ProductVariantSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        parent = self.get_parent()

        if isinstance(parent, Product):
            return ProductVariant.objects.filter(
                product=parent
            )

        return ProductVariant.objects.filter(
            customer_product=parent
        )

    def get_object(self):
        parent = self.get_parent()
        self.check_owner(parent)

        return super().get_object()
