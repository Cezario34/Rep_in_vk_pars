from django.contrib import admin
from .models import SendAllowance
# Register your models here.


@admin.register(SendAllowance)
class SendAllowanceAdmin(admin.ModelAdmin):
    list_display = ('user', 'remaining', 'user_name')
    list_editable = ('remaining',)
    search_fields = ('user_name',)
