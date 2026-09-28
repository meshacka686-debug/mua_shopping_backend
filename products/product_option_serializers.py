from rest_framework import serializers

from .product_options import (
    ProductImage,
    ProductOption,
    ProductVariant,
)


class ProductImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage

        fields = [
            "id",
            "image",
            "image_url",
            "size",
            "quantity",
            "sort_order",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "image_url",
            "created_at",
        ]

    def get_image_url(self, obj):
        request = self.context.get("request")

        if not obj.image:
            return None

        try:
            url = obj.image.url

            if request:
                return request.build_absolute_uri(url)

            return url

        except ValueError:
            return None


class ProductOptionSerializer(serializers.ModelSerializer):

    class Meta:
        model = ProductOption

        fields = [
            "id",
            "name",
            "values",
            "sort_order",
        ]

        read_only_fields = [
            "id",
        ]

    def validate_values(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError(
                "Option values must be a list."
            )

        cleaned = []

        for item in value:
            item = str(item).strip()

            if item and item not in cleaned:
                cleaned.append(item)

        if not cleaned:
            raise serializers.ValidationError(
                "At least one option value is required."
            )

        return cleaned


class ProductVariantSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariant

        fields = [
            "id",
            "name",
            "option_values",
            "price",
            "quantity",
            "sku",
            "image",
            "image_url",
            "is_available",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "is_available",
            "image_url",
            "created_at",
            "updated_at",
        ]

    def get_image_url(self, obj):
        request = self.context.get("request")

        if not obj.image:
            return None

        try:
            url = obj.image.url

            if request:
                return request.build_absolute_uri(url)

            return url

        except ValueError:
            return None

    def validate_option_values(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                "option_values must be an object."
            )

        cleaned = {}

        for key, option_value in value.items():
            key = str(key).strip()
            option_value = str(option_value).strip()

            if key and option_value:
                cleaned[key] = option_value

        return cleaned
