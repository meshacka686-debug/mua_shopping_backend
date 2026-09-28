
from rest_framework import serializers

from .models import Shop


class ShopSerializer(serializers.ModelSerializer):

    owner_username = serializers.CharField(
        source="owner.username",
        read_only=True,
    )

    logo_url = serializers.SerializerMethodField()

    class Meta:
        model = Shop

        fields = [
            "id",
            "owner",
            "owner_username",
            "name",
            "description",
            "phone",
            "address",
            "logo",
            "logo_url",
            "is_active",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "owner",
            "owner_username",
            "logo_url",
            "created_at",
            "updated_at",
        ]

    def get_logo_url(self, obj):
        request = self.context.get("request")

        if not obj.logo:
            return None

        try:
            url = obj.logo.url

            if request:
                return request.build_absolute_uri(url)

            return url

        except ValueError:
            return None

