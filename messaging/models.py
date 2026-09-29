from config.cloudinary_storages import CloudinaryImageStorage, CloudinaryVideoStorage
from django.conf import settings
from django.db import models


class Conversation(models.Model):
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="conversations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        usernames = ", ".join(
            self.participants.values_list("username", flat=True)
        )
        return usernames or f"Conversation {self.id}"


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages",
    )
    text = models.TextField(blank=True, default="")
    voice_note = models.FileField(
        upload_to="messaging/voice_notes/",
        blank=True,
        null=True,
        storage=CloudinaryVideoStorage(),
    )
    voice_note_duration_ms = models.PositiveIntegerField(
        default=0,
        blank=True,
    )
    image = models.ImageField(
        upload_to="messaging/images/",
        blank=True,
        null=True,
        storage=CloudinaryImageStorage(),
    )
    video = models.FileField(
        upload_to="messaging/videos/",
        blank=True,
        null=True,
        storage=CloudinaryVideoStorage(),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        if self.text:
            content = self.text[:40]
        elif self.image:
            content = "Image"
        elif self.video:
            content = "Video"
        elif self.voice_note:
            content = "Voice note"
        else:
            content = "Message"

        return f"{self.sender.username}: {content}"
