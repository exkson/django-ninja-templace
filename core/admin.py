from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from core.models import OTPCode, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["-date_joined"]
    list_display = [
        "email",
        "phone",
        "first_name",
        "last_name",
        "country",
        "is_active",
        "is_staff",
    ]
    list_filter = ["is_active", "is_staff", "country"]
    search_fields = ["email", "phone", "first_name", "last_name"]
    fieldsets = (
        (None, {"fields": ("email", "phone", "password")}),
        (
            _("Personal info"),
            {"fields": ("first_name", "last_name", "country")},
        ),
        (_("Admin"), {"fields": ("internal_notes", "banned_at", "ban_reason")}),
        (_("Preferences"), {"fields": ("parameters",)}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "phone",
                    "password1",
                    "password2",
                ),
            },
        ),
    )


@admin.register(OTPCode)
class OTPCodeAdmin(admin.ModelAdmin):
    list_display = ["user", "channel", "expires_at", "consumed_at", "attempts"]
    list_filter = ["channel"]
    search_fields = ["user__email", "user__phone"]
    readonly_fields = ["code_hash", "created_at", "updated_at"]
