"""Bootstrap lawyer + admin demo users (passwords in README — demo only)."""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from apps.accounts.models import UserProfile, ensure_profile

# Demo-only credentials — never use in production
DEMO_USERS = (
    ("lawyer", "lawyer-demo-2026", UserProfile.Role.LAWYER),
    ("admin", "admin-demo-2026", UserProfile.Role.ADMIN),
)


class Command(BaseCommand):
    help = "Create demo lawyer + admin users (idempotent)."

    def handle(self, *args, **options):
        for username, password, role in DEMO_USERS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"email": f"{username}@redlineguard.demo"},
            )
            if created or options.get("reset_password"):
                user.set_password(password)
                user.save()
            if role == UserProfile.Role.ADMIN:
                user.is_staff = True
                user.is_superuser = True
                user.save(update_fields=["is_staff", "is_superuser"])
            profile = ensure_profile(user)
            profile.role = role
            # Admin skips wizard by default; lawyer starts incomplete for demo
            if role == UserProfile.Role.ADMIN:
                profile.onboarding_complete = True
            profile.save()
            status = "created" if created else "updated"
            self.stdout.write(self.style.SUCCESS(f"{status}: {username} / {password} ({role})"))

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset-password",
            action="store_true",
            help="Reset passwords to demo defaults",
        )
