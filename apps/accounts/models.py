from __future__ import annotations

from django.conf import settings
from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    class Role(models.TextChoices):
        LAWYER = "lawyer", "Lawyer"
        ADMIN = "admin", "Admin"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(
        max_length=16,
        choices=Role.choices,
        default=Role.LAWYER,
    )
    onboarding_complete = models.BooleanField(default=False)
    onboarding_step = models.PositiveSmallIntegerField(default=0)

    def __str__(self) -> str:
        return f"{self.user.username} ({self.role})"


def ensure_profile(user: User) -> UserProfile:
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile
