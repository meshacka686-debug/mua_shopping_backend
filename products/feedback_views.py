from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from .models import Product, ProductFeedback
from .customer_models import CustomerProduct
from .serializers import ProductFeedbackSerializer


class ShopProductFeedbackView(generics.ListCreateAPIView):
    """
    GET  /api/products/<product_id>/feedback/
    POST /api/products/<product_id>/feedback/

    Customers can view feedback for a shop product.

    A customer can submit feedback only if:
    - they purchased the product,
    - the order belongs to them,
    - the order delivery status is received,
    - they have not already reviewed that order item.
    """

    serializer_class = ProductFeedbackSerializer
    permission_classes = [IsAuthenticated]

    def get_product(self):
        try:
            return Product.objects.get(
                pk=self.kwargs["pk"],
            )
        except Product.DoesNotExist:
            raise ValidationError(
                {"product": "Product not found."}
            )

    def get_queryset(self):
        product = self.get_product()

        return (
            ProductFeedback.objects
            .filter(product=product)
            .select_related("customer", "product", "order_item")
        )

    def create(self, request, *args, **kwargs):
        product = self.get_product()

        order_item = (
            __import__("orders.models", fromlist=["OrderItem"])
            .OrderItem.objects
            .filter(
                order__customer=request.user,
                order__delivery_status="received",
                product=product,
            )
            .select_related("order")
            .first()
        )

        if not order_item:
            raise ValidationError(
                {
                    "feedback": (
                        "You can only review a product after "
                        "you have received it."
                    )
                }
            )

        if ProductFeedback.objects.filter(
            customer=request.user,
            order_item=order_item,
        ).exists():
            raise ValidationError(
                {
                    "feedback": (
                        "You have already submitted feedback "
                        "for this product."
                    )
                }
            )

        serializer = self.get_serializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        serializer.save(
            customer=request.user,
            product=product,
            customer_product=None,
            order_item=order_item,
        )

        return Response(
            serializer.data,
            status=201,
        )


class CustomerProductFeedbackView(generics.ListCreateAPIView):
    """
    GET  /api/products/customer/<product_id>/feedback/
    POST /api/products/customer/<product_id>/feedback/

    Customers can view feedback for a customer product.

    A customer can submit feedback only if:
    - they purchased the product,
    - the order belongs to them,
    - the order delivery status is received,
    - they have not already reviewed that order item.
    """

    serializer_class = ProductFeedbackSerializer
    permission_classes = [IsAuthenticated]

    def get_product(self):
        try:
            return CustomerProduct.objects.get(
                pk=self.kwargs["pk"],
            )
        except CustomerProduct.DoesNotExist:
            raise ValidationError(
                {"product": "Customer product not found."}
            )

    def get_queryset(self):
        product = self.get_product()

        return (
            ProductFeedback.objects
            .filter(customer_product=product)
            .select_related(
                "customer",
                "customer_product",
                "order_item",
            )
        )

    def create(self, request, *args, **kwargs):
        product = self.get_product()

        order_item = (
            __import__("orders.models", fromlist=["OrderItem"])
            .OrderItem.objects
            .filter(
                order__customer=request.user,
                order__delivery_status="received",
                customer_product=product,
            )
            .select_related("order")
            .first()
        )

        if not order_item:
            raise ValidationError(
                {
                    "feedback": (
                        "You can only review a product after "
                        "you have received it."
                    )
                }
            )

        if ProductFeedback.objects.filter(
            customer=request.user,
            order_item=order_item,
        ).exists():
            raise ValidationError(
                {
                    "feedback": (
                        "You have already submitted feedback "
                        "for this product."
                    )
                }
            )

        serializer = self.get_serializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        serializer.save(
            customer=request.user,
            product=None,
            customer_product=product,
            order_item=order_item,
        )

        return Response(
            serializer.data,
            status=201,
        )
