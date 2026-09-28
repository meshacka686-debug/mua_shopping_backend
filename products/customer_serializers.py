from rest_framework import serializers

from .customer_models import CustomerProduct


class CustomerProductSerializer(serializers.ModelSerializer):

    seller_name = serializers.CharField(
        source="seller.username",
        read_only=True,
    )

    image_url = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()

    class Meta:
        model = CustomerProduct

        fields = [
            "id",
            "seller",
            "seller_name",
            "name",
            "description",
            "price",
            "quantity",
            "category",
            "image",
            "image_url",
            "video",
            "video_url",
            "is_available",
            "views",
            "likes",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "seller",
            "seller_name",
            "image_url",
            "video_url",
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

    def get_video_url(self, obj):
        request = self.context.get("request")

        if not obj.video:
            return None

        try:
            url = obj.video.url

            if request:
                return request.build_absolute_uri(url)

            return url

        except ValueError:
            return None

    def create(self, validated_data):
        quantity = validated_data.get("quantity", 0)

        validated_data["is_available"] = quantity > 0

        return CustomerProduct.objects.create(
            **validated_data
        )

    def update(self, instance, validated_data):
        if "quantity" in validated_data:
            validated_data["is_available"] = (
                validated_data["quantity"] > 0
            )

        return super().update(
            instance,
            validated_data,
        )
