from django.contrib import admin

from apps.accounts.models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "onboarding_complete", "onboarding_step")
    list_filter = ("role", "onboarding_complete")
