from django.conf import settings
from django.db import models


class CustomerProduct(models.Model):
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="customer_products",
        limit_choices_to={"role": "customer"},
    )

    name = models.CharField(max_length=200)

    description = models.TextField(blank=True)

    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    quantity = models.PositiveIntegerField(default=1)

    category = models.CharField(
        max_length=100,
        blank=True,
    )

    image = models.ImageField(
        upload_to="customer_products/images/",
        blank=True,
        null=True,
    )

    video = models.FileField(
        upload_to="customer_products/videos/",
        blank=True,
        null=True,
    )

    is_available = models.BooleanField(default=True)

    views = models.PositiveIntegerField(default=0)

    likes = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.seller.username}"
