from rest_framework import serializers

from .models import Product, ProductFeedback
from .product_option_serializers import ProductImageSerializer


class ProductSerializer(serializers.ModelSerializer):

    shop_name = serializers.CharField(
        source="shop.name",
        read_only=True,
    )

    shop_logo_url = serializers.SerializerMethodField()

    product_images = ProductImageSerializer(
        many=True,
        read_only=True,
    )

    stock = serializers.IntegerField(
        source="quantity",
        write_only=True,
        required=False,
        min_value=0,
    )

    class Meta:
        model = Product

        fields = [
            "id",
            "shop",
            "shop_name",
            "shop_logo_url",
            "product_images",
            "name",
            "description",
            "price",
            "quantity",
            "stock",
            "category",
            "image",
            "video",
            "is_available",
            "views",
            "likes",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "shop",
            "shop_name",
            "shop_logo_url",
            "quantity",
            "is_available",
            "views",
            "likes",
            "created_at",
            "updated_at",
        ]

    def validate_price(self, value):
        if value < 2000:
            raise serializers.ValidationError(
                "Product price must be at least ₦2,000."
            )
        return value

    def get_shop_logo_url(self, obj):
        request = self.context.get("request")

        if not obj.shop.logo:
            return None

        try:
            url = obj.shop.logo.url

            if request:
                return request.build_absolute_uri(url)

            return url

        except ValueError:
            return None

    def create(self, validated_data):
        quantity = validated_data.get(
            "quantity",
            0,
        )

        validated_data["is_available"] = (
            quantity > 0
        )

        return Product.objects.create(
            **validated_data
        )

    def update(
        self,
        instance,
        validated_data,
    ):
        if "quantity" in validated_data:
            quantity = validated_data["quantity"]

            validated_data[
                "is_available"
            ] = quantity > 0

        return super().update(
            instance,
            validated_data,
        )

class ProductFeedbackSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(
        source="customer.username",
        read_only=True,
    )

    product_name = serializers.SerializerMethodField()

    class Meta:
        model = ProductFeedback
        fields = [
            "id",
            "customer",
            "customer_name",
            "product",
            "customer_product",
            "order_item",
            "product_name",
            "rating",
            "comment",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "customer",
            "customer_name",
            "order_item",
            "product_name",
            "created_at",
            "updated_at",
        ]

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError(
                "Rating must be between 1 and 5."
            )
        return value

    def get_product_name(self, obj):
        if obj.product_id:
            return obj.product.name

        if obj.customer_product_id:
            return obj.customer_product.name

        return ""
