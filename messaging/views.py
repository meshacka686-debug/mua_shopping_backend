from pathlib import Path
from django.contrib.auth import get_user_model
from django.db.models import Q

from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.parsers import (
    FormParser,
    JSONParser,
    MultiPartParser,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Conversation, Message
from .serializers import ConversationSerializer, MessageSerializer


User = get_user_model()


class ConversationListView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        conversations = (
            Conversation.objects
            .filter(participants=request.user)
            .prefetch_related("participants", "messages")
            .order_by("-updated_at")
        )

        serializer = ConversationSerializer(
            conversations,
            many=True,
        )

        return Response(serializer.data)


class ConversationMessagesView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_conversation(self, request, conversation_id):
        return (
            Conversation.objects
            .filter(
                id=conversation_id,
                participants=request.user,
            )
            .first()
        )

    def get(self, request, conversation_id):
        conversation = self.get_conversation(
            request,
            conversation_id,
        )

        if not conversation:
            return Response(
                {"detail": "Conversation not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        messages = conversation.messages.select_related(
            "sender"
        ).all()

        serializer = MessageSerializer(
            messages,
            many=True,
        )

        return Response(serializer.data)

    def post(self, request, conversation_id):
        conversation = self.get_conversation(
            request,
            conversation_id,
        )

        if not conversation:
            return Response(
                {"detail": "Conversation not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        text = str(request.data.get("text", "")).strip()
        voice_note = request.FILES.get("voice_note")
        image = request.FILES.get("image")
        video = request.FILES.get("video")

        if not text and not voice_note and not image and not video:
            return Response(
                {
                    "detail": (
                        "Message text, voice note, image, or video "
                        "is required."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if image and video:
            return Response(
                {
                    "detail": (
                        "Send an image or a video in one message, "
                        "not both."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        duration_raw = request.data.get(
            "voice_note_duration_ms",
            0,
        )

        try:
            duration_ms = max(0, int(duration_raw or 0))
        except (TypeError, ValueError):
            duration_ms = 0

        if voice_note:
            max_size = 10 * 1024 * 1024

            if voice_note.size > max_size:
                return Response(
                    {"detail": "Voice note must be 10 MB or smaller."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            allowed_extensions = {
                ".m4a",
                ".aac",
                ".mp3",
                ".wav",
                ".ogg",
                ".webm",
            }

            extension = Path(voice_note.name).suffix.lower()

            if extension not in allowed_extensions:
                return Response(
                    {"detail": "Unsupported voice note format."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if image:
            max_image_size = 10 * 1024 * 1024

            if image.size > max_image_size:
                return Response(
                    {
                        "detail": (
                            "Image must be 10 MB or smaller."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            allowed_image_extensions = {
                ".jpg",
                ".jpeg",
                ".png",
                ".webp",
                ".gif",
            }

            extension = Path(image.name).suffix.lower()

            if extension not in allowed_image_extensions:
                return Response(
                    {"detail": "Unsupported image format."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if video:
            max_video_size = 100 * 1024 * 1024

            if video.size > max_video_size:
                return Response(
                    {
                        "detail": (
                            "Video must be 100 MB or smaller."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            allowed_video_extensions = {
                ".mp4",
                ".mov",
                ".m4v",
                ".webm",
                ".avi",
                ".mkv",
            }

            extension = Path(video.name).suffix.lower()

            if extension not in allowed_video_extensions:
                return Response(
                    {"detail": "Unsupported video format."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        message = Message.objects.create(
            conversation=conversation,
            sender=request.user,
            text=text,
            voice_note=voice_note,
            voice_note_duration_ms=duration_ms,
            image=image,
            video=video,
        )

        conversation.save(update_fields=["updated_at"])

        serializer = MessageSerializer(
            message,
            context={"request": request},
        )

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
        )


class StartConversationView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user_id = request.data.get("user_id")

        if not user_id:
            return Response(
                {"detail": "user_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            other_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"detail": "User not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if other_user.id == request.user.id:
            return Response(
                {"detail": "You cannot message yourself."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        conversation = (
            Conversation.objects
            .filter(participants=request.user)
            .filter(participants=other_user)
            .first()
        )

        if not conversation:
            conversation = Conversation.objects.create()
            conversation.participants.add(
                request.user,
                other_user,
            )

        serializer = ConversationSerializer(conversation)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


class MarkMessagesReadView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, conversation_id):
        conversation = (
            Conversation.objects
            .filter(
                id=conversation_id,
                participants=request.user,
            )
            .first()
        )

        if not conversation:
            return Response(
                {"detail": "Conversation not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        conversation.messages.exclude(
            sender=request.user
        ).filter(
            is_read=False
        ).update(
            is_read=True
        )

        return Response(
            {"detail": "Messages marked as read."},
            status=status.HTTP_200_OK,
        )
