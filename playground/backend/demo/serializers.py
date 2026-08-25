from __future__ import annotations

from typing import Any

from rest_framework import serializers

from appkit.media import file_url
from demo.models import DemoItem, SecretNote


class DemoItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = DemoItem
        fields = ["id", "name", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_name(self, value: str) -> str:
        # A real place for `validation_error` to fire from over HTTP.
        if not value.strip():
            raise serializers.ValidationError("name must not be blank.")
        return value


class SecretNoteSerializer(serializers.ModelSerializer):
    attachment_url = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = SecretNote
        fields = ["id", "secret", "attachment", "image", "attachment_url", "image_url"]
        extra_kwargs = {"attachment": {"write_only": True}, "image": {"write_only": True}}

    def get_attachment_url(self, obj: SecretNote) -> str | None:
        request = self.context.get("request")
        return file_url(obj.attachment, request=request) if obj.attachment else None

    def get_image_url(self, obj: SecretNote) -> str | None:
        request = self.context.get("request")
        return file_url(obj.image, request=request) if obj.image else None

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        # appkit.files.validate_upload / validate_image run here, before .save() — the
        # "validate server-side, not just client-side" line from APP-DESIGN.md §9.
        from appkit.files import validate_image, validate_upload

        attachment = attrs.get("attachment")
        if attachment:
            validate_upload(
                attachment,
                allowed_mimetypes=["application/pdf", "text/plain", "application/json"],
            )
        image = attrs.get("image")
        if image:
            validate_image(image, max_dimensions=(4096, 4096))
        return attrs
