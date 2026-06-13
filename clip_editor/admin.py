from django.contrib import admin

from .models import EditProject


@admin.register(EditProject)
class EditProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "status", "output_media", "add_date")
    list_filter = ("status",)
    search_fields = ("title", "owner__username")
    readonly_fields = ("add_date", "edit_date", "output_media", "error")
