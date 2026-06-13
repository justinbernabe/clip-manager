from rest_framework import serializers

from .models import EditProject


class EditProjectSerializer(serializers.ModelSerializer):
    output_token = serializers.SerializerMethodField()

    class Meta:
        model = EditProject
        fields = [
            "id",
            "title",
            "status",
            "edl",
            "output_token",
            "error",
            "add_date",
            "edit_date",
        ]
        read_only_fields = ["id", "status", "output_token", "error", "add_date", "edit_date"]

    def get_output_token(self, obj):
        return obj.output_media.friendly_token if obj.output_media else None
