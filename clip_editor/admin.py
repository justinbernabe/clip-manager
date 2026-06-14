from django.contrib import admin, messages
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path

from .models import AutomationRun, EditProject
from .tasks import AUTOMATIONS, AUTOMATION_NAMES, run_automation


@admin.register(EditProject)
class EditProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "status", "output_media", "add_date")
    list_filter = ("status",)
    search_fields = ("title", "owner__username")
    readonly_fields = ("add_date", "edit_date", "output_media", "error")


@admin.register(AutomationRun)
class AutomationRunAdmin(admin.ModelAdmin):
    """Run history + the JoeyDVR Tools page (run automations across the library)."""

    list_display = ("name", "status", "started_at", "finished_at")
    list_filter = ("name", "status")
    readonly_fields = ("name", "status", "result", "started_at", "finished_at")

    def has_add_permission(self, request):
        return False

    def get_urls(self):
        custom = [
            path("tools/", self.admin_site.admin_view(self.tools_view), name="joeydvr_tools"),
            path("tools/run/<str:name>/", self.admin_site.admin_view(self.run_view), name="joeydvr_run"),
        ]
        return custom + super().get_urls()

    def tools_view(self, request):
        rows = [
            {
                "key": key, "label": label, "desc": desc, "on_new": on_new,
                "last": AutomationRun.objects.filter(name=key).first(),
            }
            for key, label, desc, on_new in AUTOMATIONS
        ]
        ctx = dict(self.admin_site.each_context(request), title="JoeyDVR Tools", rows=rows)
        return TemplateResponse(request, "clip_editor/tools.html", ctx)

    def run_view(self, request, name):
        if request.method == "POST" and name in AUTOMATION_NAMES:
            run_automation.delay(name)
            messages.success(
                request,
                f"Started “{name}” across the whole library — it runs in the background; "
                "refresh this page in a bit for the result.",
            )
        return redirect("admin:joeydvr_tools")
