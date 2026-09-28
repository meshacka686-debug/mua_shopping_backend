from django.db import transaction
from django.db.models import Q
from payments.services import (
    release_order_earnings,
    cancel_customer_order,
    cancel_shop_order,
)

from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .models import Order
from .serializers import (
    OrderSerializer,
    ShopOrderStatusSerializer,
    CustomerDeliveryStatusSerializer,
)


# ================================================================
# CUSTOMER ORDERS
# ================================================================

class MyOrdersView(generics.ListCreateAPIView):

    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Order.objects
            .filter(customer=self.request.user)
            .prefetch_related(
                "items__product",
                "items__customer_product",
            )
            .order_by("-created_at")
        )


# ================================================================
# CUSTOMER ORDER DETAIL
# ================================================================

class MyOrderDetailView(generics.RetrieveAPIView):

    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Order.objects
            .filter(customer=self.request.user)
            .prefetch_related(
                "items__product",
                "items__customer_product",
            )
        )


# ================================================================
# ORDERS ON MY CUSTOMER PRODUCTS
# ================================================================

class MyCustomerProductOrdersView(generics.ListAPIView):

    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Order.objects
            .filter(
                items__customer_product__seller=self.request.user
            )
            .prefetch_related(
                "items__product",
                "items__customer_product",
            )
            .distinct()
            .order_by("-created_at")
        )


# ================================================================
# SHOP ORDERS
# ================================================================

class ShopOrdersView(generics.ListAPIView):

    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Order.objects
            .filter(
                items__product__shop__owner=self.request.user
            )
            .prefetch_related(
                "items__product",
                "items__customer_product",
            )
            .distinct()
            .order_by("-created_at")
        )


# ================================================================
# SHOP UPDATE ORDER STATUS
# ================================================================

class ShopOrderStatusView(generics.UpdateAPIView):

    serializer_class = ShopOrderStatusSerializer
    permission_classes = [IsAuthenticated]

    http_method_names = ["patch"]

    def get_queryset(self):
        return (
            Order.objects
            .filter(
                Q(items__product__shop__owner=self.request.user)
                | Q(items__customer_product__seller=self.request.user)
            )
            .prefetch_related(
                "items__product",
                "items__customer_product",
            )
            .distinct()
        )

    def update(self, request, *args, **kwargs):
        self._cancel_result = None

        response = super().update(
            request,
            *args,
            **kwargs,
        )

        if self._cancel_result is not None:
            return Response(
                self._cancel_result,
                status=200,
            )

        return response

    @transaction.atomic
    def perform_update(self, serializer):

        # Lock the order while updating it.
        order = self.get_object()

        order = (
            Order.objects
            .select_for_update()
            .get(pk=order.pk)
        )

        new_status = serializer.validated_data["status"]

        # ========================================================
        # PREVENT CHANGING A CANCELLED ORDER
        # ========================================================

        if order.status == "cancelled":
            raise ValidationError(
                "A cancelled order cannot be updated."
            )

        # ========================================================
        # PREVENT CHANGING A COMPLETED ORDER
        # ========================================================

        if order.status == "delivered":
            raise ValidationError(
                "A delivered order cannot be changed."
            )

        # ========================================================
        # ORDER STATUS FLOW
        # ========================================================

        allowed_transitions = {
            "pending": ["confirmed", "cancelled"],
            "confirmed": ["processing", "cancelled"],
            "processing": ["shipped"],
            "shipped": ["delivered"],
        }

        allowed = allowed_transitions.get(
            order.status,
            []
        )

        if new_status not in allowed:
            raise ValidationError(
                f"Cannot change order status from "
                f"'{order.status}' to '{new_status}'."
            )

        # ========================================================
        # SELLER CANCELLATION
        # ========================================================

        if new_status == "cancelled":

            try:
                result = cancel_shop_order(
                    order=order,
                    owner=self.request.user,
                )
            except ValueError as exc:
                raise ValidationError(str(exc))

            # Store the result so the API response can expose it.
            self._cancel_result = result
            return

        # ========================================================
        # PAYMENT CHECK
        # ========================================================

        # A seller should not process/ship an unpaid online order.
        if new_status in ["processing", "shipped", "delivered"]:

            if order.payment_method in ["bank", "paystack"]:

                if order.payment_status != "paid":
                    raise ValidationError(
                        "This order cannot be processed because "
                        "payment has not been confirmed."
                    )

        # ========================================================
        # SAVE STATUS
        # ========================================================

        order.status = new_status

        order.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )


# ================================================================
# CUSTOMER CANCEL ORDER
# ================================================================

class CustomerCancelOrderView(generics.GenericAPIView):

    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk, *args, **kwargs):

        try:
            order = (
                Order.objects
                .select_for_update()
                .get(
                    pk=pk,
                    customer=request.user,
                )
            )
        except Order.DoesNotExist:
            raise ValidationError(
                "Order not found."
            )

        try:
            result = cancel_customer_order(order)
        except ValueError as exc:
            raise ValidationError(str(exc))

        return Response(
            result,
            status=200,
        )


# ================================================================
# CUSTOMER DELIVERY RESPONSE
# ================================================================

class CustomerDeliveryStatusView(generics.UpdateAPIView):

    serializer_class = CustomerDeliveryStatusSerializer
    permission_classes = [IsAuthenticated]

    http_method_names = ["patch"]

    def get_queryset(self):

        # Only the customer who owns the order
        # can update the delivery status.

        return (
            Order.objects
            .filter(
                customer=self.request.user
            )
        )

    @transaction.atomic
    def perform_update(self, serializer):

        # ========================================================
        # LOCK ORDER
        # ========================================================

        order = self.get_object()

        order = (
            Order.objects
            .select_for_update()
            .get(pk=order.pk)
        )

        # ========================================================
        # ORDER MUST BE DELIVERED
        # ========================================================

        if order.status != "delivered":
            raise ValidationError(
                "You can only respond to delivery "
                "after the order has been delivered."
            )

        # ========================================================
        # CUSTOMER CAN RESPOND ONLY ONCE
        # ========================================================

        if order.delivery_status != "waiting":
            raise ValidationError(
                "You have already responded to this delivery."
            )

        # ========================================================
        # SAVE CUSTOMER RESPONSE
        # ========================================================

        new_status = serializer.validated_data[
            "delivery_status"
        ]

        order.delivery_status = new_status

        order.save(
            update_fields=[
                "delivery_status",
                "updated_at",
            ]
        )

        # ========================================================
        # RELEASE SHOP EARNINGS
        # ========================================================

        if new_status == "received":
            release_order_earnings(order)