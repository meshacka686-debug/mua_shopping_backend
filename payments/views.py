from orders.models import Order
from django.db import models, transaction
from rest_framework import generics, serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError, NotFound
from rest_framework.response import Response

import hashlib
import hmac
import json
import os

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from shops.models import Shop

from .models import (
    BankAccount,
    RefundRequest,
    WithdrawalRequest,
    FinancialTransaction,
    Wallet,
    WalletDeposit,
)
from .services import (
    create_refund_request,
    send_refund_offer,
    verify_bank_account,
    process_refund_payment,
    initiate_paystack_refund,
    verify_paystack_refund,
    initialize_paystack_payment,
    verify_paystack_payment,
    create_withdrawal_request,
    initiate_paystack_withdrawal,
    verify_paystack_withdrawal,
    get_paystack_banks,
    create_wallet_deposit,
    initialize_wallet_deposit,
    verify_wallet_deposit,

    pay_order_with_wallet,)


class WalletOrderPaymentView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            order = Order.objects.get(
                pk=pk,
                customer=request.user,
            )
        except Order.DoesNotExist:
            raise NotFound("Order not found.")

        try:
            result = pay_order_with_wallet(order)
        except ValueError as exc:
            raise ValidationError(str(exc))

        return Response(result, status=status.HTTP_200_OK)


class CreateRefundRequestSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()
    shop_id = serializers.IntegerField()
    reason = serializers.CharField(
        min_length=5
    )


class CreateRefundRequestView(generics.CreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CreateRefundRequestSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        from orders.models import Order

        try:
            order = Order.objects.get(
                id=serializer.validated_data["order_id"]
            )
        except Order.DoesNotExist:
            raise serializers.ValidationError(
                "Order not found."
            )

        try:
            shop = Shop.objects.get(
                id=serializer.validated_data["shop_id"]
            )
        except Shop.DoesNotExist:
            raise serializers.ValidationError(
                "Shop not found."
            )

        try:
            refund_request = create_refund_request(
                order=order,
                customer=request.user,
                shop=shop,
                reason=serializer.validated_data["reason"],
            )

        except ValueError as exc:
            raise serializers.ValidationError(
                str(exc)
            )

        return Response(
            {
                "message": (
                    "Refund request created successfully."
                ),
                "refund": {
                    "id": refund_request.id,
                    "order_id": refund_request.order_id,
                    "shop_id": refund_request.shop_id,
                    "status": refund_request.status,
                    "requested_amount": (
                        refund_request.requested_amount
                    ),
                    "delivery_fee": (
                        refund_request.delivery_fee
                    ),
                    "offered_amount": (
                        refund_request.offered_amount
                    ),
                    "reason": refund_request.reason,
                },
            },
            status=201,
        )
class RefundOfferSerializer(serializers.Serializer):
    delivery_fee = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=0,
    )

    offered_amount = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=0,
    )

    shop_note = serializers.CharField(
        required=False,
        allow_blank=True,
    )


class SendRefundOfferView(generics.UpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = RefundOfferSerializer
    queryset = RefundRequest.objects.select_related(
        "shop__owner",
        "customer",
        "order",
    )

    def update(self, request, *args, **kwargs):
        refund_request = self.get_object()

        if refund_request.shop.owner_id != request.user.id:
            raise serializers.ValidationError(
                "You can only manage refunds for your own shop."
            )

        serializer = self.get_serializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        try:
            refund_request = send_refund_offer(
                refund_request=refund_request,
                shop_owner=request.user,
                delivery_fee=serializer.validated_data[
                    "delivery_fee"
                ],
                offered_amount=serializer.validated_data[
                    "offered_amount"
                ],
                shop_note=serializer.validated_data.get(
                    "shop_note",
                    "",
                ),
            )

        except ValueError as exc:
            raise serializers.ValidationError(
                str(exc)
            )

        return Response(
            {
                "message": "Refund offer sent successfully.",
                "refund": {
                    "id": refund_request.id,
                    "order_id": refund_request.order_id,
                    "shop_id": refund_request.shop_id,
                    "status": refund_request.status,
                    "requested_amount": (
                        refund_request.requested_amount
                    ),
                    "delivery_fee": (
                        refund_request.delivery_fee
                    ),
                    "offered_amount": (
                        refund_request.offered_amount
                    ),
                    "shop_note": (
                        refund_request.shop_note
                    ),
                },
            },
            status=200,
        )
class RefundResponseSerializer(serializers.Serializer):
    response = serializers.ChoiceField(
        choices=[
            "accept",
            "reject",
            "receive_product",
            "reject_product_again",
        ]
    )

    bank_account_id = serializers.IntegerField(
        required=False
    )

    def validate(self, attrs):
        response = attrs.get("response")
        bank_account_id = attrs.get(
            "bank_account_id"
        )

        if response == "accept" and not bank_account_id:
            raise serializers.ValidationError(
                {
                    "bank_account_id": (
                        "A verified bank account is required "
                        "when accepting a refund."
                    )
                }
            )

        return attrs

class RefundResponseView(generics.UpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = RefundResponseSerializer

    queryset = RefundRequest.objects.select_related(
        "shop",
        "customer",
        "order",
        "bank_account",
    )

    def update(self, request, *args, **kwargs):
        refund_request = self.get_object()

        if refund_request.customer_id != request.user.id:
            raise serializers.ValidationError(
                "You can only respond to your own refund request."
            )

        serializer = self.get_serializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        bank_account = None

        if (
            serializer.validated_data["response"]
            == "accept"
        ):
            bank_account_id = (
                serializer.validated_data[
                    "bank_account_id"
                ]
            )

            try:
                bank_account = (
                    BankAccount.objects.get(
                        id=bank_account_id,
                        user=request.user,
                        is_verified=True,
                    )
                )
            except BankAccount.DoesNotExist:
                raise serializers.ValidationError(
                    {
                        "bank_account_id": (
                            "The selected bank account "
                            "does not exist, does not belong "
                            "to you, or has not been verified."
                        )
                    }
                )

        try:
            from .services import (
                respond_to_refund_offer
            )

            refund_request = (
                respond_to_refund_offer(
                    refund_request=refund_request,
                    customer=request.user,
                    response=serializer.validated_data[
                        "response"
                    ],
                    bank_account=bank_account,
                )
            )

        except ValueError as exc:
            raise serializers.ValidationError(
                str(exc)
            )

        return Response(
            {
                "message": (
                    "Refund response recorded successfully."
                ),
                "refund": {
                    "id": refund_request.id,
                    "order_id": (
                        refund_request.order_id
                    ),
                    "shop_id": (
                        refund_request.shop_id
                    ),
                    "status": (
                        refund_request.status
                    ),
                    "requested_amount": (
                        refund_request.requested_amount
                    ),
                    "delivery_fee": (
                        refund_request.delivery_fee
                    ),
                    "offered_amount": (
                        refund_request.offered_amount
                    ),
                    "reason": (
                        refund_request.reason
                    ),
                    "bank_account": (
                        {
                            "id": (
                                refund_request.bank_account_id
                            ),
                            "bank_code": (
                                refund_request.bank_account.bank_code
                            ),
                            "bank_name": (
                                refund_request.bank_account.bank_name
                            ),
                            "account_number": (
                                refund_request.bank_account.account_number
                            ),
                            "account_name": (
                                refund_request.bank_account.account_name
                            ),
                            "is_verified": (
                                refund_request.bank_account.is_verified
                            ),
                        }
                        if refund_request.bank_account_id
                        else None
                    ),
                },
            },
            status=200,
        )

class ProcessRefundPaymentView(generics.UpdateAPIView):
    """
    Admin processes an accepted refund.

    This performs the internal financial accounting only.
    Actual bank transfer will be integrated separately.
    """

    queryset = RefundRequest.objects.select_related(
        "order",
        "customer",
        "shop",
        "shop__owner",
        "bank_account",
    )

    permission_classes = [IsAuthenticated]

    def update(self, request, *args, **kwargs):
        refund_request = self.get_object()

        if request.user.role != "admin":
            return Response(
                {
                    "detail": "Only an admin can process refunds."
                },
                status=403,
            )

        try:
            with transaction.atomic():
                refund_request = (
                    RefundRequest.objects
                    .select_for_update()
                    .select_related(
                        "order",
                        "customer",
                        "shop",
                        "shop__owner",
                        "bank_account",
                    )
                    .get(pk=refund_request.pk)
                )

                processed_refund = process_refund_payment(
                    refund_request
                )

        except ValueError as exc:
            return Response(
                {
                    "detail": str(exc)
                },
                status=400,
            )

        return Response(
            {
                "message": "Refund processed successfully.",
                "refund": {
                    "id": processed_refund.id,
                    "order_id": processed_refund.order_id,
                    "shop_id": processed_refund.shop_id,
                    "customer_id": processed_refund.customer_id,
                    "status": processed_refund.status,
                    "requested_amount": str(
                        processed_refund.requested_amount
                    ),
                    "delivery_fee": str(
                        processed_refund.delivery_fee
                    ),
                    "offered_amount": str(
                        processed_refund.offered_amount
                    ),
                    "paid_at": processed_refund.paid_at,
                },
            },
            status=200,
        )

class BankAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankAccount
        fields = [
            "id",
            "bank_code",
            "bank_name",
            "account_number",
            "account_name",
            "is_verified",
            "is_default",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "bank_code",
            "bank_name",
            "account_number",
            "account_name",
            "is_verified",
            "created_at",
        ]


class CustomerBankAccountListCreateView(
    generics.ListCreateAPIView
):
    """
    Customer bank accounts.

    GET:
        Return only the authenticated customer's
        bank accounts.

    POST:
        Not allowed here.

    Bank accounts must be added through the
    Paystack verification endpoint.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = BankAccountSerializer

    def get_queryset(self):
        return BankAccount.objects.filter(
            user=self.request.user
        )

    def create(self, request, *args, **kwargs):
        return Response(
            {
                "detail": (
                    "Bank accounts must be verified "
                    "before they can be saved."
                ),
                "verification_endpoint": (
                    "/api/payments/bank-accounts/verify/"
                ),
            },
            status=400,
        )


class VerifyBankAccountSerializer(serializers.Serializer):
    bank_code = serializers.CharField(
        max_length=20
    )

    bank_name = serializers.CharField(
        max_length=150,
        required=False,
        allow_blank=True,
    )

    account_number = serializers.CharField(
        max_length=30
    )


class VerifyBankAccountView(
    generics.GenericAPIView
):
    """
    Verify and save a customer's Nigerian bank account
    using Paystack.

    The customer supplies:

        bank_code
        bank_name
        account_number

    Paystack supplies the verified account name.

    The account is saved only after successful
    verification.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = VerifyBankAccountSerializer

    def post(self, request, *args, **kwargs):

        serializer = self.get_serializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        bank_code = serializer.validated_data[
            "bank_code"
        ]

        bank_name = serializer.validated_data.get(
            "bank_name",
            "",
        )

        account_number = (
            serializer.validated_data[
                "account_number"
            ]
            .strip()
        )

        try:

            verified_data = verify_bank_account(
                bank_code=bank_code,
                account_number=account_number,
            )

        except ValueError as exc:

            return Response(
                {
                    "detail": str(exc)
                },
                status=400,
            )

        bank_account = (
            BankAccount.objects.filter(
                user=request.user,
                account_number=(
                    verified_data[
                        "account_number"
                    ]
                ),
                bank_code=(
                    verified_data[
                        "bank_code"
                    ]
                ),
            )
            .first()
        )

        if bank_account:

            bank_account.bank_name = (
                bank_name
                or bank_account.bank_name
            )

            bank_account.account_name = (
                verified_data[
                    "account_name"
                ]
            )

            bank_account.is_verified = True

            bank_account.save(
                update_fields=[
                    "bank_name",
                    "account_name",
                    "is_verified",
                    "updated_at",
                ]
            )

        else:

            bank_account = (
                BankAccount.objects.create(
                    user=request.user,
                    bank_code=(
                        verified_data[
                            "bank_code"
                        ]
                    ),
                    bank_name=bank_name,
                    account_number=(
                        verified_data[
                            "account_number"
                        ]
                    ),
                    account_name=(
                        verified_data[
                            "account_name"
                        ]
                    ),
                    is_verified=True,
                )
            )

        return Response(
            {
                "message": (
                    "Bank account verified "
                    "successfully."
                ),
                "bank_account": {
                    "id": bank_account.id,
                    "bank_code": (
                        bank_account.bank_code
                    ),
                    "bank_name": (
                        bank_account.bank_name
                    ),
                    "account_number": (
                        bank_account.account_number
                    ),
                    "account_name": (
                        bank_account.account_name
                    ),
                    "is_verified": (
                        bank_account.is_verified
                    ),
                    "is_default": (
                        bank_account.is_default
                    ),
                },
            },
            status=200,
        )

class InitiatePaystackRefundView(generics.UpdateAPIView):
    """
    Admin starts the actual Paystack bank transfer
    for a refund that has already been processed internally.

    The refund must already have:
        status = processing

    This endpoint does NOT perform the internal refund
    accounting. That has already been done by
    ProcessRefundPaymentView.
    """

    permission_classes = [IsAuthenticated]

    queryset = RefundRequest.objects.select_related(
        "order",
        "customer",
        "shop",
        "shop__owner",
        "bank_account",
    )

    def update(self, request, *args, **kwargs):

        refund_request = self.get_object()

        if request.user.role != "admin":
            return Response(
                {
                    "detail": (
                        "Only an admin can initiate "
                        "refund payouts."
                    )
                },
                status=403,
            )

        try:
            payout = initiate_paystack_refund(
                refund_request
            )

        except ValueError as exc:
            return Response(
                {
                    "detail": str(exc)
                },
                status=400,
            )

        return Response(
            {
                "message": (
                    "Paystack refund payout initiated "
                    "successfully."
                ),
                "refund": {
                    "id": refund_request.id,
                    "order_id": refund_request.order_id,
                    "customer_id": refund_request.customer_id,
                    "shop_id": refund_request.shop_id,
                    "status": refund_request.status,
                    "offered_amount": str(
                        refund_request.offered_amount
                    ),
                    "payout_reference": (
                        payout["reference"]
                    ),
                    "paystack_status": (
                        payout["status"]
                    ),
                    "amount_kobo": (
                        payout["amount_kobo"]
                    ),
                },
            },
            status=200,
        )


class VerifyPaystackRefundView(generics.UpdateAPIView):
    """
    Admin verifies the status of an already initiated
    Paystack refund payout.
    """

    permission_classes = [IsAuthenticated]

    queryset = RefundRequest.objects.select_related(
        "order",
        "customer",
        "shop",
        "shop__owner",
        "bank_account",
    )

    def update(self, request, *args, **kwargs):

        refund_request = self.get_object()

        if request.user.role != "admin":
            return Response(
                {
                    "detail": (
                        "Only an admin can verify "
                        "refund payouts."
                    )
                },
                status=403,
            )

        try:
            refund_request = verify_paystack_refund(
                refund_request
            )

        except ValueError as exc:
            return Response(
                {
                    "detail": str(exc)
                },
                status=400,
            )

        return Response(
            {
                "message": (
                    "Paystack refund payout status "
                    "verified successfully."
                ),
                "refund": {
                    "id": refund_request.id,
                    "order_id": refund_request.order_id,
                    "customer_id": refund_request.customer_id,
                    "shop_id": refund_request.shop_id,
                    "status": refund_request.status,
                    "offered_amount": str(
                        refund_request.offered_amount
                    ),
                    "payout_reference": (
                        refund_request.payout_reference
                    ),
                    "payout_failure_reason": (
                        refund_request.payout_failure_reason
                    ),
                    "paid_at": (
                        refund_request.paid_at
                    ),
                },
            },
            status=200,
        )
    
class InitializePaystackPaymentView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from orders.models import Order

        try:
            order = Order.objects.get(
                pk=pk,
                customer=request.user,
            )
        except Order.DoesNotExist:
            raise serializers.ValidationError(
                "Order not found."
            )

        try:
            payment = initialize_paystack_payment(
                order
            )
        except ValueError as exc:
            raise serializers.ValidationError(
                str(exc)
            )

        return Response(
            {
                "message": (
                    "Paystack payment initialized successfully."
                ),
                "order_id": order.id,
                "payment": payment,
            },
            status=200,
        )


class VerifyPaystackPaymentView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from orders.models import Order

        try:
            order = Order.objects.get(
                pk=pk,
                customer=request.user,
            )
        except Order.DoesNotExist:
            raise serializers.ValidationError(
                "Order not found."
            )

        try:
            result = verify_paystack_payment(
                order
            )
        except ValueError as exc:
            raise serializers.ValidationError(
                str(exc)
            )

        return Response(
            {
                "message": (
                    "Payment verification completed."
                ),
                "order_id": order.id,
                "payment": result,
            },
            status=200,
        )


@csrf_exempt
def paystack_webhook(request):
    """
    Receive and securely process Paystack webhook events.

    We use Paystack's x-paystack-signature header to verify
    that the request came from Paystack.

    For transfer events, the existing
    verify_paystack_refund() service performs the authoritative
    transfer-status check and updates the refund/accounting.
    """

    if request.method != "POST":
        return JsonResponse(
            {
                "detail": "Method not allowed."
            },
            status=405,
        )

    secret_key = os.getenv("PAYSTACK_SECRET_KEY")

    if not secret_key:
        return JsonResponse(
            {
                "detail": "Paystack secret key is not configured."
            },
            status=500,
        )

    signature = request.headers.get(
        "x-paystack-signature",
        "",
    )

    if not signature:
        return JsonResponse(
            {
                "detail": "Missing Paystack signature."
            },
            status=401,
        )

    expected_signature = hmac.new(
        secret_key.encode("utf-8"),
        request.body,
        hashlib.sha512,
    ).hexdigest()

    if not hmac.compare_digest(
        signature,
        expected_signature,
    ):
        return JsonResponse(
            {
                "detail": "Invalid Paystack signature."
            },
            status=401,
        )

    try:
        payload = json.loads(
            request.body.decode("utf-8")
        )

    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse(
            {
                "detail": "Invalid JSON payload."
            },
            status=400,
        )

    event = payload.get("event", "")
    data = payload.get("data") or {}

    transfer_events = {
        "transfer.success",
        "transfer.failed",
        "transfer.reversed",
    }

    if event not in transfer_events:
        return JsonResponse(
            {
                "status": "ignored",
                "event": event,
            },
            status=200,
        )

    reference = data.get("reference")

    if not reference:
        return JsonResponse(
            {
                "detail": "Transfer reference is missing."
            },
            status=400,
        )

    refund_request = (
        RefundRequest.objects.filter(
            payout_reference=reference
        )
        .select_related(
            "order",
            "customer",
            "shop",
            "shop__owner",
            "bank_account",
        )
        .first()
    )

    if not refund_request:
        # Return 200 so Paystack does not repeatedly retry
        # an event belonging to another transfer.
        return JsonResponse(
            {
                "status": "ignored",
                "reason": "Refund not found.",
                "reference": reference,
            },
            status=200,
        )

    try:
        refund_request = verify_paystack_refund(
            refund_request
        )

    except ValueError as exc:
        return JsonResponse(
            {
                "detail": str(exc),
            },
            status=400,
        )

    return JsonResponse(
        {
            "status": "processed",
            "event": event,
            "reference": reference,
            "refund_id": refund_request.id,
            "refund_status": refund_request.status,
        },
        status=200,
    )

# =========================================================
# WALLET / WITHDRAWAL API
# =========================================================

class WalletView(generics.GenericAPIView):
    """
    Return the authenticated user's wallet balances.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user

        if getattr(user, "role", None) not in [
    "customer",
    "shop_owner",
    "admin",
]:
            return Response(
                {
                    "detail": (
                        "Your account is not eligible "
                        "for a financial wallet."
                    )
                },
                status=403,
            )

        wallet, created = Wallet.objects.get_or_create(
            owner=user,
        )

        completed_earnings = (
            FinancialTransaction.objects
            .filter(
                user=user,
                transaction_type="sale_released",
                status="completed",
            )
            .aggregate(total=models.Sum("amount"))["total"]
            or 0
        )

        transactions = (
            FinancialTransaction.objects
            .filter(user=user)
            .order_by("-created_at")[:50]
        )

        transaction_data = []

        for item in transactions:
            transaction_data.append(
                {
                    "id": item.id,
                    "type": item.transaction_type,
                    "status": item.status,
                    "amount": str(item.amount),
                    "reference": item.reference,
                    "description": item.description,
                    "created_at": item.created_at,
                }
            )

        return Response(
            {
                "available_balance": str(
                    wallet.available_balance
                ),
                "pending_balance": str(
                    wallet.pending_balance
                ),
                "completed_earnings": str(
                    completed_earnings
                ),
                "held_balance": str(
                    wallet.held_balance
                ),
                "transactions": transaction_data,
            }
        )

# =========================================================
# WALLET DEPOSIT API
# =========================================================

class CreateWalletDepositView(generics.GenericAPIView):
    """
    Create a pending wallet deposit.

    Expected JSON:
    {
        "amount": "5000.00"
    }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        amount = request.data.get("amount")

        if amount is None:
            return Response(
                {
                    "detail": "amount is required."
                },
                status=400,
            )

        try:
            deposit = create_wallet_deposit(
                user=request.user,
                amount=amount,
            )
        except ValueError as exc:
            return Response(
                {
                    "detail": str(exc),
                },
                status=400,
            )

        return Response(
            {
                "id": deposit.id,
                "amount": str(deposit.amount),
                "reference": deposit.reference,
                "status": deposit.status,
            },
            status=201,
        )


class InitializeWalletDepositView(generics.GenericAPIView):
    """
    Initialize a pending wallet deposit through Paystack.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        try:
            deposit = WalletDeposit.objects.get(
                pk=pk,
                user=request.user,
            )
        except WalletDeposit.DoesNotExist:
            return Response(
                {
                    "detail": "Wallet deposit not found."
                },
                status=404,
            )

        payment_method = request.data.get(
            "payment_method",
            "card",
        )

        try:
            result = initialize_wallet_deposit(
                deposit,
                payment_method=payment_method,
            )
        except ValueError as exc:
            return Response(
                {
                    "detail": str(exc),
                },
                status=400,
            )

        return Response(
            {
                "id": result["deposit"].id,
                "amount": str(
                    result["deposit"].amount
                ),
                "reference": result["reference"],
                "authorization_url": (
                    result["authorization_url"]
                ),
                "access_code": result["access_code"],
                "status": result["deposit"].status,
            },
            status=200,
        )


class VerifyWalletDepositView(generics.GenericAPIView):
    """
    Verify a wallet deposit with Paystack.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        try:
            deposit = WalletDeposit.objects.get(
                pk=pk,
                user=request.user,
            )
        except WalletDeposit.DoesNotExist:
            return Response(
                {
                    "detail": "Wallet deposit not found."
                },
                status=404,
            )

        try:
            deposit = verify_wallet_deposit(
                deposit
            )
        except ValueError as exc:
            return Response(
                {
                    "detail": str(exc),
                },
                status=400,
            )

        return Response(
            {
                "id": deposit.id,
                "amount": str(deposit.amount),
                "reference": deposit.reference,
                "status": deposit.status,
                "failure_reason": (
                    deposit.failure_reason
                ),
                "completed_at": (
                    deposit.completed_at
                ),
            },
            status=200,
        )


class PaystackBanksView(generics.GenericAPIView):
    """
    Return Nigerian banks supported by Paystack.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            banks = get_paystack_banks()

        except ValueError as exc:
            return Response(
                {
                    "detail": str(exc),
                },
                status=400,
            )

        return Response(
            {
                "banks": banks,
            }
        )


class CreateWithdrawalView(generics.GenericAPIView):
    """
    Create and initiate a wallet withdrawal.

    Expected JSON:

    {
        "bank_account_id": 1,
        "amount": "5000.00"
    }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):

        bank_account_id = request.data.get(
            "bank_account_id"
        )

        amount = request.data.get(
            "amount"
        )

        if not bank_account_id:
            return Response(
                {
                    "detail": (
                        "bank_account_id is required."
                    )
                },
                status=400,
            )

        if amount is None:
            return Response(
                {
                    "detail": (
                        "amount is required."
                    )
                },
                status=400,
            )

        try:
            withdrawal = create_withdrawal_request(
                user=request.user,
                bank_account_id=bank_account_id,
                amount=amount,
            )

        except ValueError as exc:
            return Response(
                {
                    "detail": str(exc),
                },
                status=400,
            )

        try:
            withdrawal = (
                initiate_paystack_withdrawal(
                    withdrawal
                )
            )

        except ValueError as exc:

            return Response(
                {
                    "detail": str(exc),
                    "withdrawal": {
                        "id": withdrawal.id,
                        "reference": withdrawal.reference,
                        "status": withdrawal.status,
                        "amount": str(
                            withdrawal.amount
                        ),
                    },
                },
                status=400,
            )

        return Response(
            {
                "message": (
                    "Withdrawal request submitted "
                    "successfully."
                ),
                "withdrawal": {
                    "id": withdrawal.id,
                    "reference": withdrawal.reference,
                    "provider_reference": (
                        withdrawal.provider_reference
                    ),
                    "amount": str(
                        withdrawal.amount
                    ),
                    "status": withdrawal.status,
                    "failure_reason": (
                        withdrawal.failure_reason
                    ),
                    "completed_at": (
                        withdrawal.completed_at
                    ),
                },
            },
            status=201,
        )


class VerifyWithdrawalView(generics.GenericAPIView):
    """
    Verify a withdrawal with Paystack.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):

        withdrawal = (
            WithdrawalRequest.objects
            .filter(
                id=pk,
                owner=request.user,
            )
            .first()
        )

        if not withdrawal:
            return Response(
                {
                    "detail": (
                        "Withdrawal not found."
                    )
                },
                status=404,
            )

        try:
            withdrawal = (
                verify_paystack_withdrawal(
                    withdrawal
                )
            )

        except ValueError as exc:
            return Response(
                {
                    "detail": str(exc),
                },
                status=400,
            )

        return Response(
            {
                "message": (
                    "Withdrawal status checked."
                ),
                "withdrawal": {
                    "id": withdrawal.id,
                    "reference": withdrawal.reference,
                    "provider_reference": (
                        withdrawal.provider_reference
                    ),
                    "amount": str(
                        withdrawal.amount
                    ),
                    "status": withdrawal.status,
                    "failure_reason": (
                        withdrawal.failure_reason
                    ),
                    "completed_at": (
                        withdrawal.completed_at
                    ),
                },
            }
        )


class WithdrawalListView(generics.ListAPIView):
    """
    Return the authenticated user's withdrawal history.
    """

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            WithdrawalRequest.objects
            .filter(owner=self.request.user)
            .select_related("bank_account")
            .order_by("-created_at")
        )

    def list(self, request, *args, **kwargs):

        withdrawals = self.get_queryset()

        data = []

        for withdrawal in withdrawals:
            data.append(
                {
                    "id": withdrawal.id,
                    "reference": withdrawal.reference,
                    "provider_reference": (
                        withdrawal.provider_reference
                    ),
                    "amount": str(
                        withdrawal.amount
                    ),
                    "status": withdrawal.status,
                    "bank_name": (
                        withdrawal.bank_account.bank_name
                    ),
                    "account_number": (
                        withdrawal.bank_account.account_number
                    ),
                    "account_name": (
                        withdrawal.bank_account.account_name
                    ),
                    "failure_reason": (
                        withdrawal.failure_reason
                    ),
                    "created_at": withdrawal.created_at,
                    "completed_at": withdrawal.completed_at,
                }
            )

        return Response(data)