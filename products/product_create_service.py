import json

from django.db import transaction

from .models import Product
from .customer_models import CustomerProduct
from .product_options import (
    ProductImage,
    ProductOption,
    ProductVariant,
)


def parse_json_field(value, default):
    if value is None or value == "":
        return default

    if isinstance(value, (list, dict)):
        return value

    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        raise ValueError("Invalid JSON data.")


@transaction.atomic
def create_shop_product_with_details(
    *,
    shop,
    data,
    images,
    video=None,
):
    name = str(data.get("name", "")).strip()

    if not name:
        raise ValueError("Product name is required.")

    # A shop product may use pictures OR a video, but never both.
    if images and video:
        raise ValueError(
            "Choose either product pictures or a video, not both."
        )

    if not images and not video:
        raise ValueError(
            "At least one product picture or video is required."
        )

    image_details = parse_json_field(
        data.get("image_details"),
        [],
    )

    if images:
        # Picture products calculate stock from each picture.
        total_quantity = _validate_shop_image_details(
            images=images,
            image_details=image_details,
        )
    else:
        # Video-only products use the normal top-level stock quantity.
        try:
            total_quantity = int(data.get("quantity", 0))
        except (TypeError, ValueError):
            raise ValueError(
                "Stock quantity must be a valid number."
            )

        if total_quantity < 0:
            raise ValueError(
                "Stock quantity cannot be negative."
            )

    product = Product.objects.create(
        shop=shop,
        name=name,
        description=data.get("description", ""),
        price=data.get("price", 0),
        quantity=total_quantity,
        category=data.get("category", ""),
        video=video,
        is_available=total_quantity > 0,
    )

    # First image remains the existing main product image.
    if images:
        product.image = images[0]
        product.save(update_fields=["image", "updated_at"])

    _create_shop_image_details(
        product=product,
        images=images,
        image_details=image_details,
    )

    return product


def _validate_shop_image_details(
    *,
    images,
    image_details,
):
    if not images:
        raise ValueError(
            "At least one product picture is required."
        )

    if not isinstance(image_details, list):
        raise ValueError("image_details must be a list.")

    if len(image_details) != len(images):
        raise ValueError(
            "Each product picture must have a matching size and stock quantity."
        )

    total_quantity = 0

    for index, detail in enumerate(image_details):
        if not isinstance(detail, dict):
            raise ValueError(
                f"Details for product picture {index + 1} must be an object."
            )

        size = str(
            detail.get("size", "")
        ).strip()

        try:
            quantity = int(
                detail.get("quantity", 0)
            )
        except (TypeError, ValueError):
            raise ValueError(
                f"Stock quantity for product picture {index + 1} must be a number."
            )

        if quantity < 0:
            raise ValueError(
                f"Stock quantity for product picture {index + 1} cannot be negative."
            )

        total_quantity += quantity

    return total_quantity


def _create_shop_image_details(
    *,
    product,
    images,
    image_details,
):
    for index, image in enumerate(images):
        detail = image_details[index]

        size = str(
            detail.get("size", "")
        ).strip()

        quantity = int(
            detail.get("quantity", 0)
        )

        ProductImage.objects.create(
            product=product,
            image=image,
            size=size,
            quantity=quantity,
            sort_order=index,
        )


@transaction.atomic
def create_customer_product_with_details(
    *,
    seller,
    data,
    images,
    video=None,
):
    name = str(data.get("name", "")).strip()

    if not name:
        raise ValueError("Product name is required.")

    product = CustomerProduct.objects.create(
        seller=seller,
        name=name,
        description=data.get("description", ""),
        price=data.get("price", 0),
        quantity=int(data.get("quantity", 0)),
        category=data.get("category", ""),
        video=video,
        is_available=int(data.get("quantity", 0)) > 0,
    )

    # First image remains the existing main product image.
    if images:
        product.image = images[0]
        product.save(update_fields=["image", "updated_at"])

    _create_details(
        parent=product,
        images=images,
        options=parse_json_field(data.get("options"), []),
        variants=parse_json_field(data.get("variants"), []),
    )

    return product


def _create_shop_image_details(
    *,
    product,
    images,
    image_details,
):
    if not isinstance(image_details, list):
        raise ValueError("image_details must be a list.")

    if len(image_details) != len(images):
        raise ValueError(
            "Each product picture must have a matching size and stock quantity."
        )

    for index, image in enumerate(images):
        detail = image_details[index]

        if not isinstance(detail, dict):
            raise ValueError(
                "Each image detail must be an object."
            )

        size = str(
            detail.get("size", "")
        ).strip()

        if not size:
            raise ValueError(
                f"Size is required for product picture {index + 1}."
            )

        try:
            quantity = int(
                detail.get("quantity", 0)
            )
        except (TypeError, ValueError):
            raise ValueError(
                f"Stock quantity for product picture {index + 1} must be a number."
            )

        if quantity < 0:
            raise ValueError(
                f"Stock quantity for product picture {index + 1} cannot be negative."
            )

        ProductImage.objects.create(
            product=product,
            image=image,
            size=size,
            quantity=quantity,
            sort_order=index,
        )


def _create_details(
    *,
    parent,
    images,
    options,
    variants,
):
    is_shop_product = isinstance(parent, Product)

    # ---------------------------------------------------------
    # Additional product pictures
    # ---------------------------------------------------------
    for index, image in enumerate(images):
        if is_shop_product:
            ProductImage.objects.create(
                product=parent,
                image=image,
                sort_order=index,
            )
        else:
            ProductImage.objects.create(
                customer_product=parent,
                image=image,
                sort_order=index,
            )

    # ---------------------------------------------------------
    # Product options
    # ---------------------------------------------------------
    if not isinstance(options, list):
        raise ValueError("options must be a list.")

    for index, option in enumerate(options):
        if not isinstance(option, dict):
            raise ValueError("Each option must be an object.")

        option_name = str(
            option.get("name", "")
        ).strip()

        values = option.get("values", [])

        if not option_name:
            raise ValueError(
                "Every option must have a name."
            )

        if not isinstance(values, list):
            raise ValueError(
                f"Values for {option_name} must be a list."
            )

        values = [
            str(value).strip()
            for value in values
            if str(value).strip()
        ]

        if is_shop_product:
            ProductOption.objects.create(
                product=parent,
                name=option_name,
                values=values,
                sort_order=index,
            )
        else:
            ProductOption.objects.create(
                customer_product=parent,
                name=option_name,
                values=values,
                sort_order=index,
            )

    # ---------------------------------------------------------
    # Product variants
    # ---------------------------------------------------------
    if not isinstance(variants, list):
        raise ValueError("variants must be a list.")

    for variant in variants:
        if not isinstance(variant, dict):
            raise ValueError(
                "Each variant must be an object."
            )

        option_values = variant.get(
            "option_values",
            {},
        )

        if not isinstance(option_values, dict):
            raise ValueError(
                "variant option_values must be an object."
            )

        quantity = int(
            variant.get("quantity", 0)
        )

        price = variant.get("price")

        if is_shop_product:
            ProductVariant.objects.create(
                product=parent,
                name=str(
                    variant.get("name", "")
                ).strip(),
                option_values=option_values,
                price=price,
                quantity=quantity,
                sku=str(
                    variant.get("sku", "")
                ).strip(),
            )
        else:
            ProductVariant.objects.create(
                customer_product=parent,
                name=str(
                    variant.get("name", "")
                ).strip(),
                option_values=option_values,
                price=price,
                quantity=quantity,
                sku=str(
                    variant.get("sku", "")
                ).strip(),
            )
