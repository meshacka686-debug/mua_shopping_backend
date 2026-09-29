from config.cloudinary_storages import CloudinaryImageStorage, CloudinaryVideoStorage
from django.db import models
from django.db.models import Q


class ProductImage(models.Model):
    """
    Additional product pictures.

    A picture belongs to either a shop Product
    or a CustomerProduct.
    """

    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="product_images",
        null=True,
        blank=True,
    )

    customer_product = models.ForeignKey(
        "products.CustomerProduct",
        on_delete=models.CASCADE,
        related_name="product_images",
        null=True,
        blank=True,
    )

    image = models.ImageField(
        upload_to="products/gallery/",
        storage=CloudinaryImageStorage(),
    )

    size = models.CharField(
        max_length=100,
        blank=True,
    )

    quantity = models.PositiveIntegerField(
        default=0,
    )

    sort_order = models.PositiveIntegerField(
        default=0,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["sort_order", "id"]

        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(product__isnull=False)
                    | Q(customer_product__isnull=False)
                ),
                name="product_image_has_parent",
            ),
            models.CheckConstraint(
                condition=(
                    Q(product__isnull=True)
                    | Q(customer_product__isnull=True)
                ),
                name="product_image_one_parent_only",
            ),
        ]

    def __str__(self):
        if self.product_id:
            return f"Image - {self.product.name}"

        return f"Image - {self.customer_product.name}"


class ProductOption(models.Model):
    """
    Flexible product option.

    Examples:
        Color -> ["Black", "White", "Blue"]
        Size -> ["S", "M", "L", "XL"]
        Storage -> ["128GB", "256GB", "512GB"]
        RAM -> ["8GB", "16GB", "32GB"]
    """

    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="product_options",
        null=True,
        blank=True,
    )

    customer_product = models.ForeignKey(
        "products.CustomerProduct",
        on_delete=models.CASCADE,
        related_name="product_options",
        null=True,
        blank=True,
    )

    name = models.CharField(
        max_length=100,
    )

    values = models.JSONField(
        default=list,
    )

    sort_order = models.PositiveIntegerField(
        default=0,
    )

    class Meta:
        ordering = ["sort_order", "id"]

        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(product__isnull=False)
                    | Q(customer_product__isnull=False)
                ),
                name="product_option_has_parent",
            ),
            models.CheckConstraint(
                condition=(
                    Q(product__isnull=True)
                    | Q(customer_product__isnull=True)
                ),
                name="product_option_one_parent_only",
            ),
        ]

    def __str__(self):
        if self.product_id:
            return f"{self.product.name} - {self.name}"

        return f"{self.customer_product.name} - {self.name}"


class ProductVariant(models.Model):
    """
    A specific purchasable combination of product options.

    Examples:
        {
            "Color": "Black",
            "Size": "XL"
        }

        {
            "Storage": "256GB",
            "RAM": "16GB"
        }
    """

    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="product_variants",
        null=True,
        blank=True,
    )

    customer_product = models.ForeignKey(
        "products.CustomerProduct",
        on_delete=models.CASCADE,
        related_name="product_variants",
        null=True,
        blank=True,
    )

    name = models.CharField(
        max_length=255,
        blank=True,
    )

    option_values = models.JSONField(
        default=dict,
    )

    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )

    quantity = models.PositiveIntegerField(
        default=0,
    )

    sku = models.CharField(
        max_length=100,
        blank=True,
    )

    image = models.ImageField(
        upload_to="products/variants/",
        blank=True,
        null=True,
        storage=CloudinaryImageStorage(),
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

    class Meta:
        ordering = ["id"]

        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(product__isnull=False)
                    | Q(customer_product__isnull=False)
                ),
                name="product_variant_has_parent",
            ),
            models.CheckConstraint(
                condition=(
                    Q(product__isnull=True)
                    | Q(customer_product__isnull=True)
                ),
                name="product_variant_one_parent_only",
            ),
        ]

    def save(self, *args, **kwargs):
        self.is_available = self.quantity > 0
        super().save(*args, **kwargs)

    def __str__(self):
        if self.product_id:
            product_name = self.product.name
        else:
            product_name = self.customer_product.name

        return f"{product_name} - {self.name or self.option_values}"
