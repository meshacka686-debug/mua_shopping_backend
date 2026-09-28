from decimal import Decimal
import os
import requests

from django.db import transaction
from django.utils import timezone

from payments.models import FinancialTransaction, Wallet

from .models import Rent, RentBooking


RENT_ADMIN_COMMISSION = Decimal("500.00")


# ============================================================
# HELPERS
# ============================================================

def _get_locked_wallet(user):
    """
    Return the user's wallet with a database lock.
    """

    wallet, _ = Wallet.objects.get_or_create(
        owner=user,
    )

    return (
        Wallet.objects
        .select_for_update()
        .get(pk=wallet.pk)
    )


def _refund_customer_hold(booking):
    """
    Return the customer's held rental money to available balance.

    This function must be called inside transaction.atomic().
    """

    customer_wallet = _get_locked_wallet(
        booking.customer
    )

    amount = Decimal(booking.amount)

    if customer_wallet.held_balance < amount:
        raise ValueError(
            "Customer held balance is insufficient "
            "for this rental refund."
        )

    hold_reference = f"RENT-HOLD-{booking.id}"

    hold_transaction = (
        FinancialTransaction.objects
        .select_for_update()
        .filter(
            reference=hold_reference,
            transaction_type="purchase_hold",
        )
        .first()
    )

    if not hold_transaction:
        raise ValueError(
            "Rental wallet hold transaction was not found."
        )

    if hold_transaction.status == "reversed":
        return

    if hold_transaction.status != "completed":
        raise ValueError(
            "Rental wallet hold is not in a refundable state."
        )

    customer_wallet.held_balance -= amount
    customer_wallet.available_balance += amount

    customer_wallet.save(
        update_fields=[
            "held_balance",
            "available_balance",
            "updated_at",
        ]
    )

    hold_transaction.status = "reversed"

    hold_transaction.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    FinancialTransaction.objects.create(
        user=booking.customer,
        transaction_type="purchase_refund",
        status="completed",
        amount=amount,
        reference=f"RENT-REFUND-{booking.id}",
        description=(
            f"Rental booking #{booking.id} funds returned "
            f"to customer wallet."
        ),
    )


def _refund_paystack_to_customer_wallet(booking):
    """
    Return a cancelled Card/USSD rental payment to the
    customer's MUA Wallet.

    This is an internal wallet credit. It does NOT call
    Paystack's external refund endpoint, because the requested
    cancellation behavior is to return the money to the
    customer's MUA Wallet.

    Must be called inside transaction.atomic().
    """

    customer_wallet = _get_locked_wallet(
        booking.customer
    )

    amount = Decimal(booking.amount)

    reference = f"RENT-PAYSTACK-WALLET-REFUND-{booking.id}"

    existing = (
        FinancialTransaction.objects
        .select_for_update()
        .filter(
            reference=reference,
            transaction_type="purchase_refund",
        )
        .first()
    )

    if existing:
        return

    customer_wallet.available_balance += amount

    customer_wallet.save(
        update_fields=[
            "available_balance",
            "updated_at",
        ]
    )

    FinancialTransaction.objects.create(
        user=booking.customer,
        transaction_type="purchase_refund",
        status="completed",
        amount=amount,
        reference=reference,
        description=(
            f"Rental booking #{booking.id} Card/USSD payment "
            f"returned to customer MUA Wallet."
        ),
    )

    booking.payment_status = RentBooking.PAYMENT_REFUNDED
    booking.refunded_at = timezone.now()

    booking.save(
        update_fields=[
            "payment_status",
            "refunded_at",
            "updated_at",
        ]
    )


def _decrease_rent_quantity(rent):
    """
    Consume one available rental unit.
    """

    if rent.quantity <= 0:
        raise ValueError(
            "This rental has no available quantity."
        )

    rent.quantity -= 1

    rent.is_available = rent.quantity > 0

    rent.save(
        update_fields=[
            "quantity",
            "is_available",
            "updated_at",
        ]
    )


def _increase_rent_quantity(rent):
    """
    Restore one rental unit after rejection/cancellation.
    """

    rent.quantity += 1

    rent.is_available = True

    rent.save(
        update_fields=[
            "quantity",
            "is_available",
            "updated_at",
        ]
    )


# ============================================================
# CREATE BOOKING
# ============================================================

@transaction.atomic
def create_rent_booking(
    *,
    rent_id,
    customer,
    payment_method=RentBooking.PAYMENT_WALLET,
):
    """
    Customer books one available rental.

    Wallet:
        available -> held
        booking becomes pending_owner

    Paystack:
        booking becomes pending_payment
        no wallet money is moved
        rental quantity is reserved until payment succeeds
    """

    if payment_method not in (
        RentBooking.PAYMENT_WALLET,
        RentBooking.PAYMENT_PAYSTACK,
    ):
        raise ValueError(
            "Invalid rental payment method."
        )

    rent = (
        Rent.objects
        .select_for_update()
        .select_related("owner")
        .get(pk=rent_id)
    )

    if not rent.is_available or rent.quantity <= 0:
        raise ValueError(
            "This rental is currently unavailable."
        )

    if rent.owner_id == customer.id:
        raise ValueError(
            "You cannot book your own rental."
        )

    if getattr(customer, "role", None) != "customer":
        raise ValueError(
            "Only customer accounts can book rentals."
        )

    amount = Decimal(rent.price)

    if amount <= Decimal("0.00"):
        raise ValueError(
            "Rental price must be greater than zero."
        )

    if amount <= RENT_ADMIN_COMMISSION:
        raise ValueError(
            "Rental price must be greater than the "
            "₦500 admin commission."
        )

    # ---------------------------------------------------------
    # MUA WALLET
    # ---------------------------------------------------------
    if payment_method == RentBooking.PAYMENT_WALLET:

        customer_wallet = _get_locked_wallet(customer)

        if customer_wallet.available_balance < amount:
            raise ValueError(
                "Insufficient wallet balance."
            )

        booking = RentBooking.objects.create(
            rent=rent,
            customer=customer,
            amount=amount,
            status=RentBooking.STATUS_PENDING_OWNER,
            payment_method=RentBooking.PAYMENT_WALLET,
            payment_status=RentBooking.PAYMENT_PAID,
            paid_at=timezone.now(),
        )

        customer_wallet.available_balance -= amount
        customer_wallet.held_balance += amount

        customer_wallet.save(
            update_fields=[
                "available_balance",
                "held_balance",
                "updated_at",
            ]
        )

        FinancialTransaction.objects.create(
            user=customer,
            transaction_type="purchase_hold",
            status="completed",
            amount=amount,
            reference=f"RENT-HOLD-{booking.id}",
            description=(
                f"Wallet funds held for rental "
                f"booking #{booking.id}."
            ),
        )

        _decrease_rent_quantity(rent)

        return booking

    # ---------------------------------------------------------
    # PAYSTACK
    # ---------------------------------------------------------
    booking = RentBooking.objects.create(
        rent=rent,
        customer=customer,
        amount=amount,
        status=RentBooking.STATUS_PENDING_PAYMENT,
        payment_method=RentBooking.PAYMENT_PAYSTACK,
        payment_status=RentBooking.PAYMENT_PENDING,
    )

    # Reserve the rental while the customer completes payment.
    _decrease_rent_quantity(rent)

    return booking


# ============================================================
# PAYSTACK RENT PAYMENT
# ============================================================

@transaction.atomic
def initialize_paystack_rent_payment(
    *,
    booking_id,
    customer,
):
    """
    Initialize a Paystack payment for a rental booking.

    If a previous Paystack transaction was abandoned, failed,
    or reversed, create a fresh unique reference for the retry.
    """

    booking = (
        RentBooking.objects
        .select_for_update()
        .select_related("rent", "customer")
        .get(pk=booking_id)
    )

    if booking.customer_id != customer.id:
        raise ValueError(
            "You can only pay for your own rental booking."
        )

    if booking.payment_method != RentBooking.PAYMENT_PAYSTACK:
        raise ValueError(
            "This rental booking is not using Paystack."
        )

    if booking.payment_status == RentBooking.PAYMENT_PAID:
        raise ValueError(
            "This rental booking has already been paid."
        )

    if booking.status != RentBooking.STATUS_PENDING_PAYMENT:
        raise ValueError(
            "This rental booking is not waiting for payment."
        )

    email = getattr(customer, "email", None)

    if not email:
        raise ValueError(
            "Your account must have an email address "
            "before using Paystack."
        )

    amount = Decimal(booking.amount)
    amount_kobo = int(amount * Decimal("100"))

    from payments.services import _paystack_headers

    reference = booking.paystack_reference

    if reference:
        try:
            verify_response = requests.get(
                f"https://api.paystack.co/transaction/verify/{reference}",
                headers=_paystack_headers(),
                timeout=30,
            )

            verify_data = verify_response.json()

            if verify_response.ok and verify_data.get("status"):
                transaction_data = verify_data.get("data") or {}
                transaction_status = transaction_data.get("status")

                if transaction_status in {
                    "abandoned",
                    "failed",
                    "reversed",
                }:
                    reference = None

                elif transaction_status == "success":
                    raise ValueError(
                        "This Paystack transaction was already successful. "
                        "Verify the rental payment instead."
                    )

        except ValueError:
            raise
        except Exception:
            pass

    if not reference:
        from uuid import uuid4

        reference = (
            f"RENT-{booking.id}-"
            f"{booking.customer_id}-"
            f"{uuid4().hex[:10]}"
        )

    payload = {
        "email": email,
        "amount": amount_kobo,
        "reference": reference,
        "currency": "NGN",
        "channels": ["card"],
        "metadata": {
            "type": "rent_booking",
            "rent_booking_id": booking.id,
            "rent_id": booking.rent_id,
            "customer_id": booking.customer_id,
        },
    }

    callback_url = os.getenv("PAYSTACK_CALLBACK_URL")

    if callback_url:
        payload["callback_url"] = callback_url

    response = requests.post(
        "https://api.paystack.co/transaction/initialize",
        headers=_paystack_headers(),
        json=payload,
        timeout=30,
    )

    try:
        data = response.json()
    except ValueError:
        raise ValueError(
            "Paystack returned an invalid response."
        )

    if not response.ok or not data.get("status"):
        message = data.get(
            "message",
            "Unable to initialize Paystack payment.",
        )
        raise ValueError(message)

    payment_data = data.get("data") or {}

    booking.paystack_reference = (
        payment_data.get("reference") or reference
    )

    booking.save(
        update_fields=[
            "paystack_reference",
            "updated_at",
        ]
    )

    return {
        "reference": booking.paystack_reference,
        "authorization_url": payment_data.get(
            "authorization_url"
        ),
        "access_code": payment_data.get(
            "access_code"
        ),
        "amount": amount,
        "booking_id": booking.id,
    }

@transaction.atomic
def verify_paystack_rent_payment(
    *,
    booking_id,
    customer,
):
    """
    Verify a Paystack rental payment.

    Successful payment:
        payment_status -> paid
        status -> pending_owner

    Failed payment:
        payment_status -> failed
        rental quantity is restored
    """

    booking = (
        RentBooking.objects
        .select_for_update()
        .select_related("rent", "customer")
        .get(pk=booking_id)
    )

    if booking.customer_id != customer.id:
        raise ValueError(
            "You can only verify your own rental payment."
        )

    if booking.payment_method != RentBooking.PAYMENT_PAYSTACK:
        raise ValueError(
            "This rental booking is not using Paystack."
        )

    if not booking.paystack_reference:
        raise ValueError(
            "No Paystack payment reference exists."
        )

    if booking.payment_status == RentBooking.PAYMENT_PAID:
        return booking

    from payments.services import _paystack_headers

    response = requests.get(
        "https://api.paystack.co/transaction/verify/"
        f"{booking.paystack_reference}",
        headers=_paystack_headers(),
        timeout=30,
    )

    try:
        data = response.json()
    except ValueError:
        raise ValueError(
            "Paystack returned an invalid response."
        )

    if not response.ok or not data.get("status"):
        raise ValueError(
            data.get(
                "message",
                "Unable to verify Paystack payment.",
            )
        )

    payment = data.get("data") or {}

    expected_amount = int(
        Decimal(booking.amount) * Decimal("100")
    )

    paid_amount = int(
        payment.get("amount") or 0
    )

    reference = payment.get("reference")

    if reference != booking.paystack_reference:
        raise ValueError(
            "Paystack payment reference does not match "
            "this rental booking."
        )

    if paid_amount != expected_amount:
        raise ValueError(
            "Paystack payment amount does not match "
            "the rental amount."
        )

    payment_status = str(
        payment.get("status") or ""
    ).lower()

    if payment_status == "success":
        booking.payment_status = (
            RentBooking.PAYMENT_PAID
        )
        booking.status = (
            RentBooking.STATUS_PENDING_OWNER
        )
        booking.paid_at = timezone.now()

        booking.save(
            update_fields=[
                "payment_status",
                "status",
                "paid_at",
                "updated_at",
            ]
        )

        return booking

    if payment_status in (
        "failed",
        "abandoned",
        "reversed",
    ):
        booking.payment_status = (
            RentBooking.PAYMENT_FAILED
        )

        booking.status = (
            RentBooking.STATUS_CUSTOMER_CANCELLED
        )

        booking.customer_cancelled_at = timezone.now()

        booking.save(
            update_fields=[
                "payment_status",
                "status",
                "customer_cancelled_at",
                "updated_at",
            ]
        )

        _increase_rent_quantity(booking.rent)

        return booking

    raise ValueError(
        "Paystack payment has not been completed yet."
    )


# ============================================================
# OWNER CONFIRMS
# ============================================================

@transaction.atomic
def confirm_rent_booking(*, booking_id, owner):
    """
    Owner confirms the booking.

    No money moves here.

    Customer money remains held until customer confirms.
    """

    booking = (
        RentBooking.objects
        .select_for_update()
        .select_related("rent", "customer")
        .get(pk=booking_id)
    )

    if booking.rent.owner_id != owner.id:
        raise ValueError(
            "You can only manage bookings for your own rentals."
        )

    if booking.status == RentBooking.STATUS_OWNER_CONFIRMED:
        return booking

    if booking.status != RentBooking.STATUS_PENDING_OWNER:
        raise ValueError(
            "This booking cannot be confirmed in its current state."
        )

    booking.status = RentBooking.STATUS_OWNER_CONFIRMED
    booking.owner_confirmed_at = timezone.now()

    booking.save(
        update_fields=[
            "status",
            "owner_confirmed_at",
            "updated_at",
        ]
    )

    return booking



def refund_paystack_rent_booking(*, booking):
    """
    Request a full Paystack refund for a successfully paid
    rental booking.

    Paystack processes the refund asynchronously, so the
    booking is marked as refunded only after Paystack
    confirms the refund.
    """

    if booking.payment_method != RentBooking.PAYMENT_PAYSTACK:
        raise ValueError(
            "This rental booking was not paid through Paystack."
        )

    if booking.payment_status != RentBooking.PAYMENT_PAID:
        raise ValueError(
            "Only a successfully paid Paystack booking "
            "can be refunded."
        )

    reference = (
        booking.paystack_reference or ""
    ).strip()

    if not reference:
        raise ValueError(
            "This booking does not have a Paystack reference."
        )

    from payments.services import _paystack_headers

    try:
        response = requests.post(
            "https://api.paystack.co/refund",
            headers=_paystack_headers(),
            json={
                "transaction": reference,
                "currency": "NGN",
                "customer_note": (
                    f"Refund for rental booking #{booking.id}"
                ),
                "merchant_note": (
                    f"Rental cancellation refund "
                    f"for booking #{booking.id}"
                ),
            },
            timeout=30,
        )
    except requests.RequestException as exc:
        raise ValueError(
            f"Unable to connect to Paystack: {exc}"
        )

    try:
        data = response.json()
    except ValueError:
        raise ValueError(
            "Paystack returned an invalid refund response."
        )

    if not response.ok or not data.get("status"):
        raise ValueError(
            data.get(
                "message",
                "Paystack could not initiate the refund.",
            )
        )

    refund_data = data.get("data") or {}

    refund_id = refund_data.get("id")
    refund_status = (
        refund_data.get("status")
        or "pending"
    ).lower()

    booking.paystack_refund_id = (
        str(refund_id) if refund_id else None
    )

    if refund_status in (
        "pending",
        "processing",
        "needs-attention",
    ):
        booking.payment_status = (
            RentBooking.PAYMENT_REFUND_PENDING
        )

    booking.save(
        update_fields=[
            "paystack_refund_id",
            "payment_status",
            "updated_at",
        ]
    )

    return {
        "status": refund_status,
        "reference": reference,
        "refund_id": refund_id,
        "amount": str(booking.amount),
    }


def verify_paystack_rent_refund(*, booking):
    """
    Check the current Paystack refund status.

    When Paystack reports the refund as processed:
        Paystack refund -> customer MUA Wallet

    The wallet credit is idempotent, so the customer cannot
    receive the same refund twice.
    """

    booking = (
        RentBooking.objects
        .select_for_update()
        .select_related("customer")
        .get(pk=booking.pk)
    )

    if booking.payment_method != RentBooking.PAYMENT_PAYSTACK:
        raise ValueError(
            "This rental booking was not paid through Paystack."
        )

    refund_id = str(
        booking.paystack_refund_id or ""
    ).strip()

    if not refund_id:
        raise ValueError(
            "This rental booking does not have a Paystack refund ID."
        )

    if booking.payment_status == RentBooking.PAYMENT_REFUNDED:
        return {
            "status": "processed",
            "booking_id": booking.id,
            "amount": str(booking.amount),
            "wallet_credited": True,
        }

    from payments.services import _paystack_headers

    try:
        response = requests.get(
            f"https://api.paystack.co/refund/{refund_id}",
            headers=_paystack_headers(),
            timeout=30,
        )
    except requests.RequestException as exc:
        raise ValueError(
            f"Unable to connect to Paystack: {exc}"
        )

    try:
        data = response.json()
    except ValueError:
        raise ValueError(
            "Paystack returned an invalid refund response."
        )

    if not response.ok or not data.get("status"):
        raise ValueError(
            data.get(
                "message",
                "Unable to verify Paystack refund.",
            )
        )

    refund_data = data.get("data") or {}

    refund_status = (
        refund_data.get("status") or ""
    ).lower()

    amount = Decimal(booking.amount)

    if refund_status in (
        "pending",
        "processing",
        "needs-attention",
    ):
        booking.payment_status = (
            RentBooking.PAYMENT_REFUND_PENDING
        )

        booking.save(
            update_fields=[
                "payment_status",
                "updated_at",
            ]
        )

        return {
            "status": refund_status,
            "booking_id": booking.id,
            "amount": str(amount),
            "wallet_credited": False,
        }

    if refund_status == "failed":
        # Paystack says a failed refund returns the refunded
        # amount to the merchant balance. Do not credit the
        # customer wallet because the customer has not received
        # the refund.
        booking.payment_status = RentBooking.PAYMENT_PAID

        booking.save(
            update_fields=[
                "payment_status",
                "updated_at",
            ]
        )

        return {
            "status": "failed",
            "booking_id": booking.id,
            "amount": str(amount),
            "wallet_credited": False,
        }

    if refund_status != "processed":
        raise ValueError(
            f"Unknown Paystack refund status: {refund_status}"
        )

    wallet = _get_locked_wallet(booking.customer)

    refund_reference = (
        f"RENT-PAYSTACK-REFUND-{booking.id}"
    )

    existing_refund = (
        FinancialTransaction.objects
        .select_for_update()
        .filter(
            reference=refund_reference,
            transaction_type="purchase_refund",
        )
        .first()
    )

    if existing_refund:
        booking.payment_status = (
            RentBooking.PAYMENT_REFUNDED
        )
        booking.refunded_at = (
            booking.refunded_at or timezone.now()
        )

        booking.save(
            update_fields=[
                "payment_status",
                "refunded_at",
                "updated_at",
            ]
        )

        return {
            "status": "processed",
            "booking_id": booking.id,
            "amount": str(amount),
            "wallet_credited": True,
        }

    wallet.available_balance += amount

    wallet.save(
        update_fields=[
            "available_balance",
            "updated_at",
        ]
    )

    FinancialTransaction.objects.create(
        user=booking.customer,
        transaction_type="purchase_refund",
        status="completed",
        amount=amount,
        reference=refund_reference,
        description=(
            f"Paystack refund for rental booking "
            f"#{booking.id} returned to MUA Wallet."
        ),
    )

    booking.payment_status = (
        RentBooking.PAYMENT_REFUNDED
    )
    booking.refunded_at = timezone.now()

    booking.save(
        update_fields=[
            "payment_status",
            "refunded_at",
            "updated_at",
        ]
    )

    return {
        "status": "processed",
        "booking_id": booking.id,
        "amount": str(amount),
        "wallet_credited": True,
    }

# ============================================================
# OWNER REJECTS
# ============================================================

@transaction.atomic
def reject_rent_booking(*, booking_id, owner):
    """
    Owner rejects a booking while it is waiting for confirmation.

    Customer:
        held -> available

    Rental:
        quantity += 1
    """

    booking = (
        RentBooking.objects
        .select_for_update()
        .select_related("rent", "customer")
        .get(pk=booking_id)
    )

    if booking.rent.owner_id != owner.id:
        raise ValueError(
            "You can only manage bookings for your own rentals."
        )

    if booking.status == RentBooking.STATUS_OWNER_REJECTED:
        return booking

    if booking.status != RentBooking.STATUS_PENDING_OWNER:
        raise ValueError(
            "This booking cannot be rejected in its current state."
        )

    if booking.payment_method == RentBooking.PAYMENT_WALLET:
        _refund_customer_hold(booking)

    elif booking.payment_method == RentBooking.PAYMENT_PAYSTACK:
        if booking.payment_status == RentBooking.PAYMENT_PAID:
            _refund_paystack_to_customer_wallet(booking)

    booking.status = RentBooking.STATUS_OWNER_REJECTED
    booking.owner_rejected_at = timezone.now()

    booking.save(
        update_fields=[
            "status",
            "owner_rejected_at",
            "updated_at",
        ]
    )

    _increase_rent_quantity(booking.rent)

    return booking


# ============================================================
# OWNER CANCELS AFTER CONFIRMATION
# ============================================================

@transaction.atomic
def cancel_rent_booking_by_owner(*, booking_id, owner):
    """
    Owner cancels a booking after previously confirming it.

    Customer:
        wallet payment: held -> available
        Card/USSD payment: credited to available MUA Wallet

    Rental:
        quantity += 1

    Owner:
        receives nothing.

    Admin:
        receives nothing.
    """

    booking = (
        RentBooking.objects
        .select_for_update()
        .select_related("rent", "customer")
        .get(pk=booking_id)
    )

    if booking.rent.owner_id != owner.id:
        raise ValueError(
            "You can only manage bookings for your own rentals."
        )

    if booking.status == RentBooking.STATUS_OWNER_CANCELLED:
        return booking

    if booking.status != RentBooking.STATUS_OWNER_CONFIRMED:
        raise ValueError(
            "Only an owner-confirmed booking can be cancelled "
            "by the owner."
        )

    if booking.payment_method == RentBooking.PAYMENT_WALLET:
        _refund_customer_hold(booking)

    elif booking.payment_method == RentBooking.PAYMENT_PAYSTACK:
        if booking.payment_status == RentBooking.PAYMENT_PAID:
            _refund_paystack_to_customer_wallet(booking)

    booking.status = RentBooking.STATUS_OWNER_CANCELLED
    booking.owner_cancelled_at = timezone.now()

    booking.save(
        update_fields=[
            "status",
            "owner_cancelled_at",
            "updated_at",
        ]
    )

    _increase_rent_quantity(booking.rent)

    return booking


# ============================================================
# CUSTOMER FINAL CONFIRMATION
# ============================================================

@transaction.atomic
def complete_rent_booking(*, booking_id, customer):
    """
    Customer gives the final confirmation.

    Customer:
        held -> released

    Owner:
        available += amount - ₦500

    Admin:
        available += ₦500

    Rental quantity remains consumed.
    """

    booking = (
        RentBooking.objects
        .select_for_update()
        .select_related(
            "rent",
            "rent__owner",
            "customer",
        )
        .get(pk=booking_id)
    )

    if booking.customer_id != customer.id:
        raise ValueError(
            "You can only confirm your own rental bookings."
        )

    if booking.status == RentBooking.STATUS_COMPLETED:
        return booking

    if booking.status != RentBooking.STATUS_OWNER_CONFIRMED:
        raise ValueError(
            "The rental owner must confirm the booking first."
        )

    amount = Decimal(booking.amount)

    if amount <= RENT_ADMIN_COMMISSION:
        raise ValueError(
            "Rental amount must be greater than "
            "the admin commission."
        )

    owner = booking.rent.owner

    customer_wallet = _get_locked_wallet(
        booking.customer
    )

    owner_wallet = _get_locked_wallet(
        owner
    )

    admin = (
        owner.__class__.objects
        .filter(
            role="admin",
            is_active=True,
        )
        .order_by("id")
        .first()
    )

    if not admin:
        raise ValueError(
            "No active admin account is available "
            "for rental commission."
        )

    admin_wallet = _get_locked_wallet(admin)

    owner_amount = amount - RENT_ADMIN_COMMISSION

    if booking.payment_method == RentBooking.PAYMENT_WALLET:
        if customer_wallet.held_balance < amount:
            raise ValueError(
                "Customer held balance is insufficient "
                "to complete this rental."
            )

        hold_reference = f"RENT-HOLD-{booking.id}"

        hold_transaction = (
            FinancialTransaction.objects
            .select_for_update()
            .filter(
                reference=hold_reference,
                transaction_type="purchase_hold",
            )
            .first()
        )

        if not hold_transaction:
            raise ValueError(
                "Rental wallet hold transaction was not found."
            )

        if hold_transaction.status != "completed":
            raise ValueError(
                "Rental wallet hold is not available for settlement."
            )

        customer_wallet.held_balance -= amount

        customer_wallet.save(
            update_fields=[
                "held_balance",
                "updated_at",
            ]
        )

    elif booking.payment_method == RentBooking.PAYMENT_PAYSTACK:
        if booking.payment_status != RentBooking.PAYMENT_PAID:
            raise ValueError(
                "Paystack payment has not been completed."
            )

    else:
        raise ValueError(
            "Unsupported rental payment method."
        )

    owner_wallet.available_balance += owner_amount

    admin_wallet.available_balance += RENT_ADMIN_COMMISSION

    owner_wallet.save(
        update_fields=[
            "available_balance",
            "updated_at",
        ]
    )

    admin_wallet.save(
        update_fields=[
            "available_balance",
            "updated_at",
        ]
    )

    if booking.payment_method == RentBooking.PAYMENT_WALLET:
        hold_transaction.status = "reversed"

        hold_transaction.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        FinancialTransaction.objects.create(
            user=customer,
            transaction_type="purchase_release",
            status="completed",
            amount=amount,
            reference=f"RENT-RELEASE-{booking.id}",
            description=(
                f"Customer rental hold released after "
                f"completion of booking #{booking.id}."
            ),
        )

    FinancialTransaction.objects.create(
        user=owner,
        transaction_type="sale_released",
        status="completed",
        amount=owner_amount,
        reference=f"RENT-EARNING-{booking.id}",
        description=(
            f"Rental earnings released for "
            f"booking #{booking.id}."
        ),
    )

    FinancialTransaction.objects.create(
        user=admin,
        transaction_type="commission",
        status="completed",
        amount=RENT_ADMIN_COMMISSION,
        reference=f"RENT-COMMISSION-{booking.id}",
        description=(
            f"Admin commission for rental "
            f"booking #{booking.id}."
        ),
    )

    booking.status = RentBooking.STATUS_COMPLETED
    booking.completed_at = timezone.now()

    booking.save(
        update_fields=[
            "status",
            "completed_at",
            "updated_at",
        ]
    )

    return booking


# ============================================================
# CUSTOMER CANCELS AFTER OWNER CONFIRMATION
# ============================================================

@transaction.atomic
def cancel_rent_booking(*, booking_id, customer):
    """
    Customer cancels after owner confirmation.

    Customer:
        wallet payment: held -> available
        Card/USSD payment: credited to available MUA Wallet

    Rental:
        quantity += 1

    Owner:
        receives nothing.

    Admin:
        receives nothing.
    """

    booking = (
        RentBooking.objects
        .select_for_update()
        .select_related("rent", "customer")
        .get(pk=booking_id)
    )

    if booking.customer_id != customer.id:
        raise ValueError(
            "You can only cancel your own rental bookings."
        )

    if booking.status == RentBooking.STATUS_CUSTOMER_CANCELLED:
        return booking

    if booking.status not in (
        RentBooking.STATUS_PENDING_OWNER,
        RentBooking.STATUS_OWNER_CONFIRMED,
    ):
        raise ValueError(
            "This booking can only be cancelled after "
            "the owner confirms it."
        )

    if booking.payment_method == RentBooking.PAYMENT_WALLET:
        _refund_customer_hold(booking)

    elif booking.payment_method == RentBooking.PAYMENT_PAYSTACK:
        if booking.payment_status == RentBooking.PAYMENT_PAID:
            _refund_paystack_to_customer_wallet(booking)

    booking.status = RentBooking.STATUS_CUSTOMER_CANCELLED
    booking.customer_cancelled_at = timezone.now()

    booking.save(
        update_fields=[
            "status",
            "customer_cancelled_at",
            "updated_at",
        ]
    )

    _increase_rent_quantity(booking.rent)

    return booking
