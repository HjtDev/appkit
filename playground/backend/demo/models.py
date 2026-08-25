from __future__ import annotations

from django.conf import settings
from django.db import models

from demo.fields import EncryptedTextField


class DemoItem(models.Model):
    """Plain list data — exercises appkit.mixins.CachedListMixin + appkit.pagination."""

    name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="demo_items"
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name


class SecretNote(models.Model):
    """Exercises the crypto extra (via demo.fields.EncryptedTextField, wrapping
    appkit.crypto.Cipher) and the files/images extras (appkit.files.validate_upload /
    validate_image, called from demo/serializers.py before save).
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="secret_notes"
    )
    secret = EncryptedTextField()
    attachment = models.FileField(upload_to="demo/attachments/", blank=True, null=True)
    image = models.ImageField(upload_to="demo/images/", blank=True, null=True)

    def __str__(self) -> str:
        return f"SecretNote(#{self.pk})"
