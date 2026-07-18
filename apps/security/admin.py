from django.contrib import admin

from apps.security.models import SecurityEvent

admin.site.register(SecurityEvent)
