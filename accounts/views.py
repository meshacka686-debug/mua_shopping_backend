from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone
from datetime import timedelta
import secrets

from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from .serializers import (
    LoginSerializer,
    RegisterSerializer,
    ProfileSerializer,
)
from .models import PasswordResetCode


User = get_user_model()


class LoginView(APIView):

    def post(self, request):
        serializer = LoginSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        user = serializer.validated_data["user"]

        token, created = Token.objects.get_or_create(
            user=user
        )

        return Response(
            {
                "message": "Login successful",
                "token": token.key,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": user.role,
                    "phone": user.phone,
                },
            },
            status=status.HTTP_200_OK,
        )


class RegisterView(APIView):

    def post(self, request):
        serializer = RegisterSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        user = serializer.save()

        token, created = Token.objects.get_or_create(
            user=user
        )

        return Response(
            {
                "message": "Registration successful",
                "token": token.key,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": user.role,
                    "phone": user.phone,
                },
            },
            status=status.HTTP_201_CREATED,
        )
class ProfileView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        serializer = ProfileSerializer(
            request.user,
            context={"request": request},
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    def patch(self, request):
        serializer = ProfileSerializer(
            request.user,
            data=request.data,
            partial=True,
            context={"request": request},
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )
class FindFriendsView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        users = User.objects.exclude(
            id=request.user.id
        ).order_by("username")

        serializer = ProfileSerializer(
            users,
            many=True,
            context={"request": request},
        )

        return Response(serializer.data)

class ForgotPasswordView(APIView):
    """
    Request a 6-digit password reset code by email.
    """

    def post(self, request):
        email = str(request.data.get("email", "")).strip()

        if not email:
            return Response(
                {"detail": "Email is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.filter(email__iexact=email, is_active=True).first()

        # Always return the same response whether the email exists or not.
        # This prevents revealing which email addresses have accounts.
        if user:
            PasswordResetCode.objects.filter(
                user=user,
                used=False,
            ).update(used=True)

            code = f"{secrets.randbelow(1000000):06d}"

            PasswordResetCode.objects.create(
                user=user,
                code=code,
                expires_at=timezone.now() + timedelta(minutes=10),
            )

            send_mail(
                subject="MUA Shopping Password Reset Code",
                message=(
                    f"Your MUA Shopping password reset code is: {code}\n\n"
                    "This code expires in 10 minutes.\n"
                    "If you did not request a password reset, you can ignore this email."
                ),
                from_email=None,
                recipient_list=[user.email],
                fail_silently=False,
            )

        return Response(
            {
                "message": "If an account exists for that email, "
                           "a password reset code has been sent."
            },
            status=status.HTTP_200_OK,
        )


class VerifyResetCodeView(APIView):
    """
    Verify that the supplied reset code is valid.
    """

    def post(self, request):
        email = str(request.data.get("email", "")).strip()
        code = str(request.data.get("code", "")).strip()

        if not email or not code:
            return Response(
                {"detail": "Email and code are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.filter(
            email__iexact=email,
            is_active=True,
        ).first()

        if not user:
            return Response(
                {"detail": "Invalid or expired code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reset_code = PasswordResetCode.objects.filter(
            user=user,
            code=code,
            used=False,
        ).first()

        if not reset_code or reset_code.expires_at <= timezone.now():
            return Response(
                {"detail": "Invalid or expired code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"message": "Code verified successfully."},
            status=status.HTTP_200_OK,
        )


class ResetPasswordView(APIView):
    """
    Set a new password using a valid reset code.
    """

    def post(self, request):
        email = str(request.data.get("email", "")).strip()
        code = str(request.data.get("code", "")).strip()
        new_password = str(request.data.get("new_password", ""))

        if not email or not code or not new_password:
            return Response(
                {"detail": "Email, code and new password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(new_password) < 6:
            return Response(
                {"detail": "Password must be at least 6 characters long."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.filter(
            email__iexact=email,
            is_active=True,
        ).first()

        if not user:
            return Response(
                {"detail": "Invalid or expired code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reset_code = PasswordResetCode.objects.filter(
            user=user,
            code=code,
            used=False,
        ).first()

        if not reset_code or reset_code.expires_at <= timezone.now():
            return Response(
                {"detail": "Invalid or expired code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.save(update_fields=["password"])

        reset_code.used = True
        reset_code.save(update_fields=["used"])

        # Invalidate any other outstanding reset codes.
        PasswordResetCode.objects.filter(
            user=user,
            used=False,
        ).update(used=True)

        return Response(
            {"message": "Password reset successful. You can now log in."},
            status=status.HTTP_200_OK,
        )

