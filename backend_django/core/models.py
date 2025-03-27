from django.db import models
from django_extensions.db.fields import ShortUUIDField

from django.conf import settings
from django.utils.translation import gettext_lazy as _
from crum import get_current_user
# Create your models here.

class TimeStampedModelMixin(models.Model):
    """
    An abstract base model that includes a UUID field, a created date field,
    an updated date field, a created by field, and an updated by field.
    """

    id = models.AutoField(primary_key=True, editable=False)
    optional_id = ShortUUIDField(editable=False)
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Creado en"),
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Modificado en"))
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        default=None,
        on_delete=models.PROTECT,
        related_name="+",
        editable=False,
        verbose_name=_("Creado por"),
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        default=None,
        on_delete=models.PROTECT,
        related_name="+",
        editable=False,
        verbose_name=_("Modificado por"),
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        user = get_current_user()
        if user and not user.pk:
            user = None
        if not self.pk:
            self.created_by = user
        self.updated_by = user
        super().save(*args, **kwargs)
