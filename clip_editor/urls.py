from rest_framework import routers

from .views import EditProjectViewSet

router = routers.DefaultRouter()
router.register(r"api/v1/editor/projects", EditProjectViewSet, basename="editor-projects")

urlpatterns = router.urls
