from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Customer, User


@admin.register(User)
class UserAdm(UserAdmin):
    ordering = ("email",)
    list_display = ("email", "name", "role", "is_active")
    fieldsets = ((None, {"fields": ("email", "password", "name", "role")}),
                 ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}))
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "name", "role", "password1", "password2")}),)
    search_fields = ("email", "name")


admin.site.register(Customer)
