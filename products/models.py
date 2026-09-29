from config.cloudinary_storages import CloudinaryImageStorage, CloudinaryVideoStorage
from django.db import models


class Product(models.Model):
    shop = models.ForeignKey(
        "shops.Shop",
        on_delete=models.CASCADE,
        related_name="products",
    )

    name = models.CharField(max_length=200)

    description = models.TextField(blank=True)

    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    quantity = models.PositiveIntegerField(default=0)

    category = models.CharField(
        max_length=100,
        blank=True,
    )

    image = models.ImageField(
        upload_to="products/images/",
        blank=True,
        null=True,
        storage=CloudinaryImageStorage(),
    )

    video = models.FileField(
        upload_to="products/videos/",
        blank=True,
        null=True,
        storage=CloudinaryVideoStorage(),
    )

    is_available = models.BooleanField(default=True)

    views = models.PositiveIntegerField(default=0)

    likes = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.shop.name}"
from .customer_models import CustomerProduct


class ProductFeedback(models.Model):
    customer = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="product_feedback",
    )

    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="feedback",
        null=True,
        blank=True,
    )

    customer_product = models.ForeignKey(
        "products.CustomerProduct",
        on_delete=models.CASCADE,
        related_name="feedback",
        null=True,
        blank=True,
    )

    order_item = models.ForeignKey(
        "orders.OrderItem",
        on_delete=models.CASCADE,
        related_name="feedback",
    )

    rating = models.PositiveSmallIntegerField()

    comment = models.TextField(
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
        constraints = [
            models.UniqueConstraint(
                fields=["customer", "order_item"],
                name="unique_customer_order_item_feedback",
            ),
        ]

    def __str__(self):
        target = self.product or self.customer_product
        return (
            f"{self.customer.username} - "
            f"{target} - {self.rating}/5"
        )

from .product_options import ProductImage, ProductOption, ProductVariant


class ProductLike(models.Model):
    customer = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="product_likes",
    )

    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="like_records",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["customer", "product"],
                name="unique_customer_product_like",
            ),
        ]

    def __str__(self):
        return f"{self.customer.username} liked {self.product.name}"
