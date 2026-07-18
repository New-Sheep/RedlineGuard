from django.contrib import admin

from apps.review.models import Draft, Finding, PlaybookImport, ReviewRun

admin.site.register(PlaybookImport)
admin.site.register(ReviewRun)
admin.site.register(Finding)
admin.site.register(Draft)
