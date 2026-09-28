from django.urls import path

from .views import (
    LoginView,
    RegisterView,
    ProfileView,
    FindFriendsView,
    ForgotPasswordView,
    VerifyResetCodeView,
    ResetPasswordView,
)


urlpatterns = [
    path(
        "login/",
        LoginView.as_view(),
        name="login",
    ),
    path(
    "profile/",
    ProfileView.as_view(),
    name="profile",
),
    path(
        "register/",
        RegisterView.as_view(),
        name="register",
    ),
    path("find-friends/", FindFriendsView.as_view(), name="find-friends"),
    path("forgot-password/", ForgotPasswordView.as_view(), name="forgot-password"),
    path("verify-reset-code/", VerifyResetCodeView.as_view(), name="verify-reset-code"),
    path("reset-password/", ResetPasswordView.as_view(), name="reset-password"),
]
