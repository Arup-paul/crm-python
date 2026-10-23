from django.conf import settings
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    """Adds created_at and updated_at to every model that inherits it."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AuditModel(models.Model):
    """Adds created_by and updated_by. Services set them; the API client never can."""

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        abstract = True


class ActiveManager(models.Manager):
    """Default manager for soft-delete models: hides archived rows."""

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class SoftDeleteModel(TimeStampedModel):
    """Archive instead of delete (ADR 003). `objects` hides archived rows; `all_objects` sees all."""

    is_active = models.BooleanField(default=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    objects = ActiveManager()  # declared first, so it's the default manager
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def archive(self, user=None):
        if not self.is_active:
            return  # already archived: keep the original date and person
        self.is_active = False
        self.archived_at = timezone.now()
        self.archived_by = user
        self.save(update_fields=["is_active", "archived_at", "archived_by", "updated_at"])

    def restore(self):
        if self.is_active:
            return
        self.is_active = True
        self.archived_at = None
        self.archived_by = None
        self.save(update_fields=["is_active", "archived_at", "archived_by", "updated_at"])
