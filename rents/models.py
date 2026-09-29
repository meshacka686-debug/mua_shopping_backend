from config.cloudinary_storages import CloudinaryImageStorage, CloudinaryVideoStorage
from decimal import Decimal

from django.conf import settings
from django.db import models


class Rent(models.Model):
    PRICE_PERIOD_CHOICES = [
        ("day", "Per Day"),
        ("week", "Per Week"),
        ("month", "Per Month"),
        ("year", "Per Year"),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="rent_listings",
    )

    owner_phone = models.CharField(
        max_length=30,
        blank=True,
        default="",
    )

    title = models.CharField(max_length=200)

    description = models.TextField(
        blank=True,
        default="",
    )

    location = models.CharField(
        max_length=255,
    )

    price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )

    price_period = models.CharField(
        max_length=20,
        choices=PRICE_PERIOD_CHOICES,
        default="year",
    )

    quantity = models.PositiveIntegerField(
        default=1,
    )

    image = models.ImageField(
        upload_to="rents/images/",
        blank=True,
        null=True,
        storage=CloudinaryImageStorage(),
    )

    video = models.FileField(
        upload_to="rents/videos/",
        blank=True,
        null=True,
        storage=CloudinaryVideoStorage(),
    )

    is_available = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return f"{self.title} - {self.owner.username}"


class RentImage(models.Model):
    rent = models.ForeignKey(
        Rent,
        on_delete=models.CASCADE,
        related_name="images",
    )

    image = models.ImageField(
        upload_to="rents/images/",
        storage=CloudinaryImageStorage(),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    def __str__(self):
        return f"Image for {self.rent.title}"


class RentBooking(models.Model):
    STATUS_PENDING_PAYMENT = "pending_payment"
    STATUS_PENDING_OWNER = "pending_owner"
    STATUS_OWNER_CONFIRMED = "owner_confirmed"
    STATUS_OWNER_REJECTED = "owner_rejected"
    STATUS_OWNER_CANCELLED = "owner_cancelled"
    STATUS_CUSTOMER_CANCELLED = "customer_cancelled"
    STATUS_COMPLETED = "completed"

    STATUS_CHOICES = [
        (
            STATUS_PENDING_PAYMENT,
            "Pending Payment",
        ),
        (
            STATUS_PENDING_OWNER,
            "Pending Owner Confirmation",
        ),
        (
            STATUS_OWNER_CONFIRMED,
            "Owner Confirmed",
        ),
        (
            STATUS_OWNER_REJECTED,
            "Owner Rejected",
        ),
        (
            STATUS_OWNER_CANCELLED,
            "Owner Cancelled",
        ),
        (
            STATUS_CUSTOMER_CANCELLED,
            "Customer Cancelled",
        ),
        (
            STATUS_COMPLETED,
            "Completed",
        ),
    ]

    rent = models.ForeignKey(
        Rent,
        on_delete=models.CASCADE,
        related_name="bookings",
    )

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="rent_bookings",
    )

    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )

    PAYMENT_WALLET = "wallet"
    PAYMENT_PAYSTACK = "paystack"

    PAYMENT_METHOD_CHOICES = [
        (
            PAYMENT_WALLET,
            "MUA Wallet",
        ),
        (
            PAYMENT_PAYSTACK,
            "Paystack",
        ),
    ]

    PAYMENT_PENDING = "pending"
    PAYMENT_PAID = "paid"
    PAYMENT_FAILED = "failed"
    PAYMENT_REFUND_PENDING = "refund_pending"
    PAYMENT_REFUNDED = "refunded"

    PAYMENT_STATUS_CHOICES = [
        (
            PAYMENT_PENDING,
            "Pending",
        ),
        (
            PAYMENT_PAID,
            "Paid",
        ),
        (
            PAYMENT_FAILED,
            "Failed",
        ),
        (
            PAYMENT_REFUND_PENDING,
            "Refund Pending",
        ),
        (
            PAYMENT_REFUNDED,
            "Refunded",
        ),
    ]

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default=PAYMENT_WALLET,
    )

    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default=PAYMENT_PAID,
    )

    paystack_reference = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
    )

    paystack_refund_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    paid_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    refunded_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING_OWNER,
    )

    owner_confirmed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    owner_rejected_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    owner_cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    customer_cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"Rent booking #{self.id} - "
            f"{self.rent.title} - "
            f"{self.customer.username}"
        )
