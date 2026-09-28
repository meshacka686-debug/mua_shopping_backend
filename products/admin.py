from django.contrib import admin

from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "shop",
        "price",
        "quantity",
        "category",
        "is_available",
        "created_at",
    )

    list_filter = (
        "is_available",
        "category",
    )

    search_fields = (
        "name",
        "shop__name",
        "description",
    )

    ordering = (
        "-created_at",
    )