from django.contrib.auth import get_user_model

from rest_framework import serializers

from .models import Conversation, Message


User = get_user_model()


class ParticipantSerializer(serializers.ModelSerializer):
    profile_image_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "role",
            "profile_image",
            "profile_image_url",
        ]

    def get_profile_image_url(self, obj):
        request = self.context.get("request")

        if not obj.profile_image:
            return None

        if request:
            return request.build_absolute_uri(
                obj.profile_image.url
            )

        return obj.profile_image.url


class MessageSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(
        source="sender.username",
        read_only=True,
    )
    sender_role = serializers.CharField(
        source="sender.role",
        read_only=True,
    )
    sender_profile_image = serializers.ImageField(
        source="sender.profile_image",
        read_only=True,
    )
    sender_profile_image_url = serializers.SerializerMethodField()
    voice_note_url = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            "id",
            "conversation",
            "sender",
            "sender_username",
            "sender_role",
            "sender_profile_image",
            "sender_profile_image_url",
            "text",
            "voice_note",
            "voice_note_url",
            "voice_note_duration_ms",
            "image",
            "image_url",
            "video",
            "video_url",
            "created_at",
            "is_read",
        ]
        read_only_fields = [
            "id",
            "sender",
            "sender_username",
            "sender_role",
            "sender_profile_image",
            "sender_profile_image_url",
            "voice_note",
            "voice_note_url",
            "created_at",
        ]

    def get_image_url(self, obj):
        if not obj.image:
            return None

        request = self.context.get("request")

        if request:
            return request.build_absolute_uri(
                obj.image.url
            )

        return obj.image.url

    def get_video_url(self, obj):
        if not obj.video:
            return None

        request = self.context.get("request")

        if request:
            return request.build_absolute_uri(
                obj.video.url
            )

        return obj.video.url

    def get_voice_note_url(self, obj):
        if not obj.voice_note:
            return None

        request = self.context.get("request")

        if request:
            return request.build_absolute_uri(obj.voice_note.url)

        return obj.voice_note.url

    def get_sender_profile_image_url(self, obj):
        request = self.context.get("request")

        if not obj.sender.profile_image:
            return None

        if request:
            return request.build_absolute_uri(
                obj.sender.profile_image.url
            )

        return obj.sender.profile_image.url


class ConversationSerializer(serializers.ModelSerializer):
    participants = ParticipantSerializer(
        many=True,
        read_only=True,
    )
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            "id",
            "participants",
            "created_at",
            "updated_at",
            "last_message",
        ]

    def get_last_message(self, obj):
        message = obj.messages.order_by("-created_at").first()

        if not message:
            return None

        return MessageSerializer(
            message,
            context=self.context,
        ).data
