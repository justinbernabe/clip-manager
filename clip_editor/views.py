from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import EditProject
from .serializers import EditProjectSerializer
from .tasks import render_edit_project


class EditProjectViewSet(viewsets.ModelViewSet):
    """CRUD for non-destructive edit projects + an async render action.

    Owner-scoped: you only ever see and touch your own projects.
    """

    serializer_class = EditProjectSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return EditProject.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def update(self, request, *args, **kwargs):
        project = self.get_object()
        if project.status == "rendering":
            return Response(
                {"detail": "Can't edit a project while it's rendering."},
                status=status.HTTP_409_CONFLICT,
            )
        return super().update(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def render(self, request, pk=None):
        project = self.get_object()
        if project.status == "rendering":
            return Response(
                {"detail": "Already rendering."}, status=status.HTTP_409_CONFLICT
            )
        if not (project.edl or {}).get("tracks"):
            return Response(
                {"detail": "Nothing to render — the EDL has no tracks."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        project.status = "rendering"
        project.error = ""
        project.output_media = None
        project.save(update_fields=["status", "error", "output_media", "edit_date"])
        render_edit_project.delay(project.id)
        return Response(
            self.get_serializer(project).data, status=status.HTTP_202_ACCEPTED
        )
