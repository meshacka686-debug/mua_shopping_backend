from django.db import transaction
from rest_framework import serializers

from products.models import Product
from products.customer_models import CustomerProduct
from products.product_options import ProductImage
from .models import Order, OrderItem


class ProductImageHybridField(serializers.PrimaryKeyRelatedField):
    def to_representation(self, value):
        # Deleted products and DRF PKOnlyObject values do not
        # have an image attribute. Return no image instead of
        # crashing order serialization.
        if not value:
            return None

        image = getattr(value, "image", None)

        if not image:
            return None

        request = self.context.get("request")

        try:
            url = image.url

            if request:
                return request.build_absolute_uri(url)

            return url
        except (ValueError, AttributeError):
            return None


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.SerializerMethodField()
    product_description = serializers.SerializerMethodField()
    product_category = serializers.SerializerMethodField()
    product_seller = serializers.SerializerMethodField()
    product_type_display = serializers.SerializerMethodField()
    total_price = serializers.SerializerMethodField()

    product_image = ProductImageHybridField(
        queryset=ProductImage.objects.all(),
        required=False,
        allow_null=True,
    )

    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        required=False,
        allow_null=True,
    )

    customer_product = serializers.PrimaryKeyRelatedField(
        queryset=CustomerProduct.objects.all(),
        required=False,
        allow_null=True,
    )

    product_type = serializers.ChoiceField(
        choices=["shop", "customer"],
        write_only=True,
        required=False,
    )

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product",
            "customer_product",
            "product_type",
            "product_image",
            "size",
            "product_name",
            "product_description",
            "product_category",
            "product_seller",
            "product_type_display",
            "quantity",
            "price",
            "total_price",
        ]

        read_only_fields = [
            "id",
            "product_name",
            "price",
            "total_price",
        ]

    def get_product_name(self, obj):
        if obj.product_id:
            return obj.product.name

        if obj.customer_product_id:
            return obj.customer_product.name

        return "Unknown product"

    def get_product_description(self, obj):
        if obj.product_id:
            return obj.product.description or ""

        if obj.customer_product_id:
            return obj.customer_product.description or ""

        return ""

    def get_product_category(self, obj):
        if obj.product_id:
            return obj.product.category or ""

        if obj.customer_product_id:
            return obj.customer_product.category or ""

        return ""

    def get_product_seller(self, obj):
        if obj.product_id:
            return obj.product.shop.owner.username

        if obj.customer_product_id:
            return obj.customer_product.seller.username

        return ""

    def get_product_type_display(self, obj):
        if obj.product_id:
            return "shop"

        if obj.customer_product_id:
            return "customer"

        return ""

    def get_product_image(self, obj):
        request = self.context.get("request")

        # For shop products, use the exact gallery image selected
        # when the order was created.
        if obj.product_image_id and obj.product_image:
            try:
                url = obj.product_image.image.url

                if request:
                    return request.build_absolute_uri(url)

                return url
            except ValueError:
                pass

        # Fallback to the product's main image.
        product = obj.product or obj.customer_product

        if not product or not product.image:
            return None

        try:
            url = product.image.url

            if request:
                return request.build_absolute_uri(url)

            return url
        except ValueError:
            return None

    def get_total_price(self, obj):
        return obj.total_price

    def to_representation(self, instance):
        data = super().to_representation(instance)

        # Always return a usable product image URL.
        # For newer shop orders, use the selected gallery image.
        # For older orders without product_image, fall back to
        # the product's main image.
        data["product_image"] = self.get_product_image(instance)

        return data

    def validate(self, attrs):
        product = attrs.get("product")
        customer_product = attrs.get("customer_product")
        product_type = attrs.get("product_type")
        quantity = attrs.get("quantity", 1)

        if product and customer_product:
            raise serializers.ValidationError(
                "An order item cannot contain both a shop product "
                "and a customer product."
            )

        if not product and not customer_product:
            raise serializers.ValidationError(
                "A product must be selected."
            )

        if product_type == "shop" and not product:
            raise serializers.ValidationError(
                "A shop product is required."
            )

        if product_type == "customer" and not customer_product:
            raise serializers.ValidationError(
                "A customer product is required."
            )

        if quantity < 1:
            raise serializers.ValidationError(
                "Quantity must be at least 1."
            )

        product_image = attrs.get("product_image")
        size = str(attrs.get("size", "") or "").strip()

        if product_image and not product:
            raise serializers.ValidationError(
                "A product picture can only be used with a shop product."
            )

        if product_image and product_image.product_id != product.id:
            raise serializers.ValidationError(
                "The selected product picture does not belong to this product."
            )

        if product:
            product_images = list(
                product.product_images.all()
            )

            if product_images:
                named_sizes = {
                    image.size.strip()
                    for image in product_images
                    if image.size.strip()
                }

                if named_sizes and not size:
                    raise serializers.ValidationError(
                        "Please select a size for this product."
                    )

                if size and not any(
                    image.size.strip() == size
                    and image.quantity >= quantity
                    for image in product_images
                ):
                    raise serializers.ValidationError(
                        f"Size {size} is not available in the requested quantity."
                    )

                if product_image:
                    if product_image.quantity < quantity:
                        raise serializers.ValidationError(
                            f"Only {product_image.quantity} of the selected "
                            f"product picture is available."
                        )

            if not product.is_available:
                raise serializers.ValidationError(
                    f"{product.name} is currently unavailable."
                )

            if not product.shop.is_active:
                raise serializers.ValidationError(
                    f"{product.name}'s shop is currently inactive."
                )

            if product.quantity < quantity:
                raise serializers.ValidationError(
                    f"Only {product.quantity} of "
                    f"{product.name} is available."
                )

        if customer_product:
            request = self.context.get("request")

            if request and customer_product.seller_id == request.user.id:
                raise serializers.ValidationError(
                    "You cannot order your own customer product."
                )

            if not customer_product.is_available:
                raise serializers.ValidationError(
                    f"{customer_product.name} is currently unavailable."
                )

            if customer_product.quantity < quantity:
                raise serializers.ValidationError(
                    f"Only {customer_product.quantity} of "
                    f"{customer_product.name} is available."
                )

        return attrs


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(
        many=True,
        write_only=True,
    )

    order_items = OrderItemSerializer(
        source="items",
        many=True,
        read_only=True,
    )

    class Meta:
        model = Order
        fields = [
            "id",
            "customer",
            "full_name",
            "phone",
            "address",
            "city",
            "state",
            "payment_method",
            "payment_channel",
            "payment_status",
            "payment_reference",
            "paid_at",
            "status",
            "delivery_status",
            "total_amount",
            "items",
            "delivery_fee",
            "order_items",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "customer",
            "status",
            "delivery_status",
            "payment_status",
            "payment_reference",
            "paid_at",
            "total_amount",
            "delivery_fee",
            "order_items",
            "created_at",
            "updated_at",
        ]

    def validate_payment_method(self, value):
        valid_methods = {
            "wallet",
            "paystack",
            "cash",
            "bank",
        }

        if value not in valid_methods:
            raise serializers.ValidationError(
                "Invalid payment method."
            )

        return value

    def validate(self, attrs):
        payment_method = attrs.get("payment_method")
        payment_channel = attrs.get("payment_channel", "")

        if payment_method == "paystack":
            if payment_channel not in {"card", "ussd"}:
                raise serializers.ValidationError({
                    "payment_channel": (
                        "Card or USSD must be selected "
                        "for Paystack payment."
                    )
                })

        elif payment_method == "wallet":
            if payment_channel:
                attrs["payment_channel"] = ""

        return attrs

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError(
                "Your order must contain at least one product."
            )

        seen = set()
        seller_identity = None

        for item in items:
            product = item.get("product")
            customer_product = item.get("customer_product")
            quantity = item["quantity"]

            if quantity < 1:
                raise serializers.ValidationError(
                    "Quantity must be at least 1."
                )

            if product:
                # Shop product
                current_seller = ("shop", product.shop_id)

                if seller_identity is None:
                    seller_identity = current_seller
                elif seller_identity[0] != current_seller[0]:
                    raise serializers.ValidationError(
                        "You cannot mix shop products and customer products "
                        "in the same order."
                    )
                elif seller_identity != current_seller:
                    raise serializers.ValidationError(
                        "You can only order products from one shop at a time."
                    )

                identity = ("shop", product.id)

                if identity in seen:
                    raise serializers.ValidationError(
                        f"{product.name} appears more than once "
                        "in this order."
                    )

                seen.add(identity)

            elif customer_product:
                # Customer-owned product
                current_seller = ("customer", customer_product.seller_id)

                if seller_identity is None:
                    seller_identity = current_seller
                elif seller_identity[0] != current_seller[0]:
                    raise serializers.ValidationError(
                        "You cannot mix shop products and customer products "
                        "in the same order."
                    )
                elif seller_identity != current_seller:
                    raise serializers.ValidationError(
                        "You can only order products from one customer seller "
                        "at a time."
                    )

                identity = ("customer", customer_product.id)

                if identity in seen:
                    raise serializers.ValidationError(
                        f"{customer_product.name} appears more than once "
                        "in this order."
                    )

                seen.add(identity)

            else:
                raise serializers.ValidationError(
                    "Each order item must contain a product."
                )

        return items

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop("items")

        shop_product_ids = []
        customer_product_ids = []

        for item in items_data:
            if item.get("product"):
                shop_product_ids.append(item["product"].id)

            if item.get("customer_product"):
                customer_product_ids.append(
                    item["customer_product"].id
                )

        locked_products = (
            Product.objects
            .select_for_update()
            .select_related("shop")
            .filter(id__in=shop_product_ids)
        )

        products = {
            product.id: product
            for product in locked_products
        }

        product_image_ids = [
            item["product_image"].id
            for item in items_data
            if item.get("product_image") is not None
        ]

        locked_product_images = (
            ProductImage.objects
            .select_for_update()
            .filter(id__in=product_image_ids)
        )

        product_images = {
            image.id: image
            for image in locked_product_images
        }

        if len(product_images) != len(set(product_image_ids)):
            raise serializers.ValidationError(
                "One or more selected product pictures were not found."
            )

        locked_customer_products = (
            CustomerProduct.objects
            .select_for_update()
            .filter(id__in=customer_product_ids)
        )

        customer_products = {
            product.id: product
            for product in locked_customer_products
        }

        if len(products) != len(set(shop_product_ids)):
            raise serializers.ValidationError(
                "One or more selected shop products were not found."
            )

        if len(customer_products) != len(set(customer_product_ids)):
            raise serializers.ValidationError(
                "One or more selected customer products were not found."
            )

        total = 0

        for item_data in items_data:
            quantity = item_data["quantity"]

            product = item_data.get("product")
            customer_product = item_data.get("customer_product")

            if product:
                product = products[product.id]

                if not product.is_available:
                    raise serializers.ValidationError(
                        f"{product.name} is currently unavailable."
                    )

                if not product.shop.is_active:
                    raise serializers.ValidationError(
                        f"{product.name}'s shop is currently inactive."
                    )

                if product.quantity < quantity:
                    raise serializers.ValidationError(
                        f"Only {product.quantity} of "
                        f"{product.name} is available."
                    )

                product_image = item_data.get("product_image")

                if product_image:
                    product_image = product_images[product_image.id]

                    if product_image.product_id != product.id:
                        raise serializers.ValidationError(
                            "The selected product picture does not belong "
                            "to this product."
                        )

                    if product_image.quantity < quantity:
                        raise serializers.ValidationError(
                            f"Only {product_image.quantity} of the selected "
                            f"product picture is available."
                        )

                total += product.price * quantity

            elif customer_product:
                customer_product = customer_products[
                    customer_product.id
                ]

                if customer_product.seller_id == (
                    self.context["request"].user.id
                ):
                    raise serializers.ValidationError(
                        "You cannot order your own customer product."
                    )

                if not customer_product.is_available:
                    raise serializers.ValidationError(
                        f"{customer_product.name} is currently unavailable."
                    )

                if customer_product.quantity < quantity:
                    raise serializers.ValidationError(
                        f"Only {customer_product.quantity} of "
                        f"{customer_product.name} is available."
                    )

                total += customer_product.price * quantity

        order = Order.objects.create(
            customer=self.context["request"].user,
            total_amount=total,
            **validated_data,
        )

        for item_data in items_data:
            quantity = item_data["quantity"]

            product = item_data.get("product")
            customer_product = item_data.get("customer_product")

            if product:
                product = products[product.id]

                product_image = item_data.get("product_image")

                if product_image:
                    product_image = product_images[product_image.id]
                    product_image.quantity -= quantity
                    product_image.save(update_fields=["quantity"])

                OrderItem.objects.create(
                    order=order,
                    product=product,
                    customer_product=None,
                    product_image=product_image,
                    size=str(item_data.get("size", "") or "").strip(),
                    quantity=quantity,
                    price=product.price,
                )

                product.quantity -= quantity
                product.is_available = product.quantity > 0

                product.save(
                    update_fields=[
                        "quantity",
                        "is_available",
                        "updated_at",
                    ]
                )

            elif customer_product:
                customer_product = customer_products[
                    customer_product.id
                ]

                OrderItem.objects.create(
                    order=order,
                    product=None,
                    customer_product=customer_product,
                    quantity=quantity,
                    price=customer_product.price,
                )

                customer_product.quantity -= quantity
                customer_product.is_available = (
                    customer_product.quantity > 0
                )

                customer_product.save(
                    update_fields=[
                        "quantity",
                        "is_available",
                        "updated_at",
                    ]
                )

        return order


class ShopOrderStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ["status"]

    def validate_status(self, value):
        valid_statuses = {
            "pending",
            "confirmed",
            "processing",
            "shipped",
            "delivered",
            "cancelled",
        }

        if value not in valid_statuses:
            raise serializers.ValidationError(
                "Invalid order status."
            )

        return value


class CustomerDeliveryStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ["delivery_status"]

    def validate_delivery_status(self, value):
        valid_statuses = {
            "waiting",
            "received",
            "rejected",
        }

        if value not in valid_statuses:
            raise serializers.ValidationError(
                "Invalid delivery status."
            )

        return value    
