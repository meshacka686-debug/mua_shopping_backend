from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count
from rest_framework import generics, status
from rest_framework.authentication import TokenAuthentication
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    PostComment,
    PostLike,
    SocialActivity,
    SocialPost,
    UserFollow,
)
from .serializers import SocialPostSerializer


from django.db.models import Q
from rest_framework.permissions import AllowAny
User = get_user_model()


class SocialPostListView(generics.ListAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    queryset = (
        SocialPost.objects
        .select_related("user", "product")
        .annotate(like_count=Count("like_records"))
        .order_by("-created_at")
    )
    serializer_class = SocialPostSerializer


class SocialPostCreateView(generics.CreateAPIView):
    serializer_class = SocialPostSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def perform_create(self, serializer):
        serializer.save(
            user=self.request.user,
            likes=0,
        )


class SocialPostDeleteView(generics.DestroyAPIView):
    queryset = SocialPost.objects.all()
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return SocialPost.objects.filter(
            user=self.request.user
        )


class SocialPostLikeView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        try:
            post = SocialPost.objects.select_for_update().get(pk=pk)
        except SocialPost.DoesNotExist:
            return Response(
                {"detail": "Post not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        like, created = PostLike.objects.get_or_create(
            post=post,
            user=request.user,
        )

        post.likes = PostLike.objects.filter(post=post).count()
        post.save(update_fields=["likes"])

        if created and post.user_id != request.user.id:
            SocialActivity.objects.create(
                recipient=post.user,
                actor=request.user,
                action="like",
                post=post,
            )

        return Response(
            {
                "liked": True,
                "likes": post.likes,
                "created": created,
            },
            status=status.HTTP_200_OK,
        )

    @transaction.atomic
    def delete(self, request, pk):
        try:
            post = SocialPost.objects.select_for_update().get(pk=pk)
        except SocialPost.DoesNotExist:
            return Response(
                {"detail": "Post not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        PostLike.objects.filter(
            post=post,
            user=request.user,
        ).delete()

        post.likes = PostLike.objects.filter(post=post).count()
        post.save(update_fields=["likes"])

        return Response(
            {
                "liked": False,
                "likes": post.likes,
            },
            status=status.HTTP_200_OK,
        )


class SocialPostLikesView(generics.ListAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            post = SocialPost.objects.get(pk=pk)
        except SocialPost.DoesNotExist:
            return Response(
                {"detail": "Post not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        likes = (
            PostLike.objects
            .filter(post=post)
            .select_related("user")
        )

        return Response(
            [
                {
                    "id": like.user.id,
                    "username": like.user.username,
                    "profile_image_url": (
                        request.build_absolute_uri(
                            like.user.profile_image.url
                        )
                        if like.user.profile_image
                        else None
                    ),
                }
                for like in likes
            ]
        )


class SocialPostCommentsView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            post = SocialPost.objects.get(pk=pk)
        except SocialPost.DoesNotExist:
            return Response(
                {"detail": "Post not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        comments = (
            PostComment.objects
            .filter(post=post)
            .select_related("user")
            .order_by("created_at")
        )

        return Response([
            {
                "id": comment.id,
                "username": comment.user.username,
                "text": comment.text,
                "profile_image_url": (
                    request.build_absolute_uri(
                        comment.user.profile_image.url
                    )
                    if comment.user.profile_image
                    else None
                ),
                "created_at": comment.created_at,
                "is_me": comment.user_id == request.user.id,
            }
            for comment in comments
        ])


class SocialPostCommentCreateView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            post = SocialPost.objects.get(pk=pk)
        except SocialPost.DoesNotExist:
            return Response(
                {"detail": "Post not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        text = str(request.data.get("text", "")).strip()

        if not text:
            return Response(
                {"detail": "Comment cannot be empty."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(text) > 2000:
            return Response(
                {"detail": "Comment is too long."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        comment = PostComment.objects.create(
            post=post,
            user=request.user,
            text=text,
        )

        if post.user_id != request.user.id:
            SocialActivity.objects.create(
                recipient=post.user,
                actor=request.user,
                action="comment",
                post=post,
                comment=comment,
            )

        return Response(
            {
                "id": comment.id,
                "username": comment.user.username,
                "text": comment.text,
                "profile_image_url": (
                    request.build_absolute_uri(
                        comment.user.profile_image.url
                    )
                    if comment.user.profile_image
                    else None
                ),
                "created_at": comment.created_at,
                "is_me": True,
            },
            status=status.HTTP_201_CREATED,
        )


class SocialPostCommentDeleteView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        try:
            comment = PostComment.objects.get(
                pk=pk,
                user=request.user,
            )
        except PostComment.DoesNotExist:
            return Response(
                {"detail": "Comment not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        comment.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)


class MyLikedPostsView(generics.ListAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        posts = (
            SocialPost.objects
            .filter(like_records__user=request.user)
            .select_related("user", "product")
            .annotate(like_count=Count("like_records"))
            .order_by("-created_at")
        )

        return Response(
            SocialPostSerializer(
                posts,
                many=True,
                context={"request": request},
            ).data
        )


class UserFollowToggleView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, username):
        try:
            target = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                {"detail": "User not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if target == request.user:
            return Response(
                {"detail": "You cannot follow yourself."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        relationship, created = UserFollow.objects.get_or_create(
            follower=request.user,
            following=target,
        )

        if created:
            SocialActivity.objects.create(
                recipient=target,
                actor=request.user,
                action="follow",
            )

        return Response(
            {
                "following": True,
                "created": created,
                "followers_count": UserFollow.objects.filter(
                    following=target
                ).count(),
                "following_count": UserFollow.objects.filter(
                    follower=request.user
                ).count(),
            }
        )

    @transaction.atomic
    def delete(self, request, username):
        try:
            target = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                {"detail": "User not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        UserFollow.objects.filter(
            follower=request.user,
            following=target,
        ).delete()

        return Response(
            {
                "following": False,
                "followers_count": UserFollow.objects.filter(
                    following=target
                ).count(),
                "following_count": UserFollow.objects.filter(
                    follower=request.user
                ).count(),
            }
        )


class UserProfileView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, username=None):
        target = request.user

        if username:
            try:
                target = User.objects.get(username=username)
            except User.DoesNotExist:
                return Response(
                    {"detail": "User not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        posts = (
            SocialPost.objects
            .filter(user=target)
            .select_related("user", "product")
            .order_by("-created_at")
        )

        following_count = UserFollow.objects.filter(
            follower=target
        ).count()

        followers_count = UserFollow.objects.filter(
            following=target
        ).count()

        likes_count = PostLike.objects.filter(
            post__user=target
        ).count()

        is_following = UserFollow.objects.filter(
            follower=request.user,
            following=target,
        ).exists()

        return Response(
            {
                "id": target.id,
                "username": target.username,
                "first_name": target.first_name,
                "last_name": target.last_name,
                "bio": target.bio,
                "profile_image_url": (
                    request.build_absolute_uri(
                        target.profile_image.url
                    )
                    if target.profile_image
                    else None
                ),
                "followers_count": followers_count,
                "following_count": following_count,
                "likes_count": likes_count,
                "is_following": is_following,
                "is_me": target == request.user,
                "posts": SocialPostSerializer(
                    posts,
                    many=True,
                    context={"request": request},
                ).data,
            }
        )


class FollowersView(generics.ListAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, username):
        try:
            target = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                {"detail": "User not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        relationships = (
            UserFollow.objects
            .filter(following=target)
            .select_related("follower")
        )

        return Response(
            [
                {
                    "id": item.follower.id,
                    "username": item.follower.username,
                    "profile_image_url": (
                        request.build_absolute_uri(
                            item.follower.profile_image.url
                        )
                        if item.follower.profile_image
                        else None
                    ),
                }
                for item in relationships
            ]
        )


class FollowingView(generics.ListAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, username):
        try:
            target = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                {"detail": "User not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        relationships = (
            UserFollow.objects
            .filter(follower=target)
            .select_related("following")
        )

        return Response(
            [
                {
                    "id": item.following.id,
                    "username": item.following.username,
                    "profile_image_url": (
                        request.build_absolute_uri(
                            item.following.profile_image.url
                        )
                        if item.following.profile_image
                        else None
                    ),
                }
                for item in relationships
            ]
        )


class SocialPostShareView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            post = SocialPost.objects.select_related("user").get(pk=pk)
        except SocialPost.DoesNotExist:
            return Response(
                {"detail": "Post not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        post.shares = (post.shares or 0) + 1
        post.save(update_fields=["shares"])

        if post.user_id != request.user.id:
            SocialActivity.objects.create(
                recipient=post.user,
                actor=request.user,
                action="share",
                post=post,
            )

        return Response(
            {
                "success": True,
                "post_id": post.id,
                "shares": post.shares,
            },
            status=status.HTTP_200_OK,
        )


class SocialActivityView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        activities = (
            SocialActivity.objects
            .filter(recipient=request.user)
            .select_related(
                "actor",
                "post",
                "comment",
            )
            .order_by("-created_at")
        )

        results = []

        for activity in activities:
            actor_image = None

            if activity.actor.profile_image:
                try:
                    actor_image = request.build_absolute_uri(
                        activity.actor.profile_image.url
                    )
                except ValueError:
                    actor_image = None

            results.append({
                "id": activity.id,
                "action": activity.action,
                "actor_id": activity.actor_id,
                "actor_username": activity.actor.username,
                "actor_profile_image_url": actor_image,
                "post_id": activity.post_id,
                "comment_id": activity.comment_id,
                "comment_text": (
                    activity.comment.text
                    if activity.comment
                    else None
                ),
                "is_read": activity.is_read,
                "created_at": activity.created_at,
            })

        return Response(results, status=status.HTTP_200_OK)


class SocialActivityReadView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            activity = SocialActivity.objects.get(
                pk=pk,
                recipient=request.user,
            )
        except SocialActivity.DoesNotExist:
            return Response(
                {"detail": "Activity not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        activity.is_read = True
        activity.save(update_fields=["is_read"])

        return Response(
            {
                "id": activity.id,
                "is_read": True,
            },
            status=status.HTTP_200_OK,
        )


class SocialActivityReadAllView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        updated = (
            SocialActivity.objects
            .filter(
                recipient=request.user,
                is_read=False,
            )
            .update(is_read=True)
        )

        return Response(
            {
                "marked_read": updated,
            },
            status=status.HTTP_200_OK,
        )


class SocialSearchView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        query = request.query_params.get("q", "").strip()

        if not query:
            return Response({
                "users": [],
                "posts": [],
            })

        User = get_user_model()

        # Search users by username or name.
        users = (
            User.objects
            .filter(
                Q(username__icontains=query)
                | Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
            )
            .order_by("username")[:20]
        )

        user_results = []

        for user in users:
            profile_image_url = None

            if user.profile_image:
                try:
                    profile_image_url = request.build_absolute_uri(
                        user.profile_image.url
                    )
                except ValueError:
                    profile_image_url = None

            user_results.append({
                "id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "bio": user.bio,
                "profile_image_url": profile_image_url,
            })

        # Search social posts by caption, username,
        # or attached product name.
        posts = (
            SocialPost.objects
            .select_related("user", "product")
            .filter(
                Q(caption__icontains=query)
                | Q(user__username__icontains=query)
                | Q(product__name__icontains=query)
            )
            .order_by("-created_at")[:30]
        )

        post_results = SocialPostSerializer(
            posts,
            many=True,
            context={"request": request},
        ).data

        return Response({
            "users": user_results,
            "posts": post_results,
        })
