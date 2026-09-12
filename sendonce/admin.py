from django.contrib import admin
from .models import SendAllowance, MailingLog
# Register your models here.


@admin.register(SendAllowance)
class SendAllowanceAdmin(admin.ModelAdmin):
    list_display = ('user', 'remaining', 'user_name')
    list_editable = ('remaining',)
    search_fields = ('user_name',)

@admin.register(MailingLog)
class MailingLogAdmin(admin.ModelAdmin):
    list_display = ("started_at", "finished_at", "user", "book_title", "day", "ok", "err", "status")
    list_filter = ("status", "day")
    search_fields = ("user__username", "book_title", "author_name", "errors")
    readonly_fields = (
        "user", "started_at", "finished_at", "book_title", "author_name",
        "day", "total", "ok", "err", "status", "message", "report_name", "errors",
    )