from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
    (
        "MUA Shopping Information",
        {
            "fields": (
                "role",
                "phone",
                "bio",
                "profile_image",
            )
        },
    ),
)

    add_fieldsets = UserAdmin.add_fieldsets + (
    (
        "MUA Shopping Information",
        {
            "fields": (
                "role",
                "phone",
                "bio",
                "profile_image",
            )
        },
    ),
)

    list_display = (
        "username",
        "email",
        "role",
        "is_active",
        "is_staff",
    )

    list_filter = (
        "role",
        "is_active",
        "is_staff",
    )

    search_fields = (
        "username",
        "email",
        "phone",
    )