from rest_framework import serializers

from .models import PostLike, SocialPost, UserFollow


class SocialPostSerializer(serializers.ModelSerializer):
    username = serializers.CharField(
        source="user.username",
        read_only=True,
    )

    image = serializers.ImageField(
        write_only=True,
        required=False,
        allow_null=True,
    )

    video = serializers.FileField(
        write_only=True,
        required=False,
        allow_null=True,
    )

    image_url = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()

    product_id = serializers.IntegerField(
        source="product.id",
        read_only=True,
    )

    liked_by_me = serializers.SerializerMethodField()
    likes = serializers.SerializerMethodField()
    profile_image_url = serializers.SerializerMethodField()

    class Meta:
        model = SocialPost
        fields = [
            "id",
            "username",
            "profile_image_url",
            "caption",
            "image",
            "image_url",
            "video",
            "video_url",
            "product_id",
            "likes",
            "liked_by_me",
            "shares",
            "created_at",
            "updated_at",
        ]

    def get_image_url(self, obj):
        request = self.context.get("request")

        if not obj.image:
            return None

        url = obj.image.url

        if request:
            return request.build_absolute_uri(url)

        return url

    def get_video_url(self, obj):
        request = self.context.get("request")

        if not obj.video:
            return None

        url = obj.video.url

        if request:
            return request.build_absolute_uri(url)

        return url

    def get_likes(self, obj):
        if hasattr(obj, "like_count"):
            return obj.like_count

        return PostLike.objects.filter(post=obj).count()

    def get_profile_image_url(self, obj):
        request = self.context.get("request")

        if not obj.user.profile_image:
            return None

        url = obj.user.profile_image.url

        if request:
            return request.build_absolute_uri(url)

        return url

    def get_liked_by_me(self, obj):
        request = self.context.get("request")

        if not request or not request.user.is_authenticated:
            return False

        return PostLike.objects.filter(
            post=obj,
            user=request.user,
        ).exists()


class UserFollowSerializer(serializers.ModelSerializer):
    follower_username = serializers.CharField(
        source="follower.username",
        read_only=True,
    )

    following_username = serializers.CharField(
        source="following.username",
        read_only=True,
    )

    class Meta:
        model = UserFollow
        fields = [
            "id",
            "follower_username",
            "following_username",
            "created_at",
        ]
