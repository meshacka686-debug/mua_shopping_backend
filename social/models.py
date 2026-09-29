from config.cloudinary_storages import CloudinaryImageStorage, CloudinaryVideoStorage
from django.conf import settings
from django.db import models


class SocialPost(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="social_posts",
    )

    caption = models.TextField(blank=True)

    image = models.ImageField(
        upload_to="social/images/",
        blank=True,
        null=True,
        storage=CloudinaryImageStorage(),
    )

    video = models.FileField(
        upload_to="social/videos/",
        blank=True,
        null=True,
        storage=CloudinaryVideoStorage(),
    )

    product = models.ForeignKey(
        "products.Product",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="social_posts",
    )

    # Kept for compatibility with the existing API/UI.
    # It is synchronized from PostLike records.
    likes = models.PositiveIntegerField(default=0)

    shares = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.caption[:40]}"


class PostLike(models.Model):
    post = models.ForeignKey(
        SocialPost,
        on_delete=models.CASCADE,
        related_name="like_records",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="social_post_likes",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["post", "user"],
                name="unique_social_post_like",
            )
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} likes post {self.post_id}"


class PostComment(models.Model):
    post = models.ForeignKey(
        SocialPost,
        on_delete=models.CASCADE,
        related_name="comments",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="social_comments",
    )

    text = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return (
            f"{self.user.username} commented on post "
            f"{self.post_id}"
        )


class UserFollow(models.Model):
    follower = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="following_relationships",
    )

    following = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="follower_relationships",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["follower", "following"],
                name="unique_user_follow",
            )
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.follower.username} follows {self.following.username}"




class SocialActivity(models.Model):
    ACTION_CHOICES = [
        ("like", "Like"),
        ("comment", "Comment"),
        ("follow", "Follow"),
        ("share", "Share"),
    ]

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="social_activities_received",
    )

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="social_activities_created",
    )

    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
    )

    post = models.ForeignKey(
        SocialPost,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="activities",
    )

    comment = models.ForeignKey(
        PostComment,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="activity_records",
    )

    is_read = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"{self.actor.username} {self.action} "
            f"for {self.recipient.username}"
        )
