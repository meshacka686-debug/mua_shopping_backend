from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.exceptions import PermissionDenied

from .customer_models import CustomerProduct
from .customer_serializers import CustomerProductSerializer


class IsCustomerMixin:

    def check_customer(self):
        user = self.request.user

        if not user.is_authenticated:
            raise PermissionDenied(
                "Authentication is required."
            )

        if user.role != "customer":
            raise PermissionDenied(
                "Only customers can sell customer products."
            )

        return user


class CustomerProductListCreateView(
    IsCustomerMixin,
    generics.ListCreateAPIView,
):
    """
    GET:
        Public list of customer products.

    POST:
        Logged-in customer creates a product.
    """

    serializer_class = CustomerProductSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated()]

        return [AllowAny()]

    def get_queryset(self):
        return CustomerProduct.objects.filter(
            is_available=True,
            quantity__gt=0,
        ).select_related("seller")

    def perform_create(self, serializer):
        seller = self.check_customer()

        serializer.save(
            seller=seller
        )


class CustomerProductDetailView(
    IsCustomerMixin,
    generics.RetrieveUpdateDestroyAPIView,
):
    """
    GET:
        View a customer product.

    PATCH:
        Edit your own customer product.

    DELETE:
        Delete your own customer product.
    """

    serializer_class = CustomerProductSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return CustomerProduct.objects.select_related(
            "seller"
        )

    def get_permissions(self):
        if self.request.method in ["PATCH", "PUT", "DELETE"]:
            return [IsAuthenticated()]

        return [AllowAny()]

    def get_object(self):
        product = super().get_object()

        if self.request.method in ["PATCH", "PUT", "DELETE"]:
            self.check_customer()

            if product.seller != self.request.user:
                raise PermissionDenied(
                    "You can only edit or delete your own products."
                )

        return product

    def perform_destroy(self, instance):
        # Only orders that are still in progress block deletion.
        # Delivered/cancelled historical orders do not block deletion.
        from rest_framework.exceptions import ValidationError

        active_statuses = [
            "pending",
            "confirmed",
            "processing",
            "shipped",
        ]

        has_active_order = instance.customer_order_items.filter(
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

        instance.delete()


class MyCustomerProductsView(
    IsCustomerMixin,
    generics.ListAPIView,
):
    """
    GET /api/customer-products/my/
    """

    serializer_class = CustomerProductSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        self.check_customer()

        return CustomerProduct.objects.filter(
            seller=self.request.user
        ).select_related("seller")
