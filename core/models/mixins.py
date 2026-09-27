from django.db import models

from ulid import ULID


class ULIDMixin(models.Model):
    id = models.CharField(
        primary_key=True, max_length=26, editable=False, default=ULID.as_str
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
