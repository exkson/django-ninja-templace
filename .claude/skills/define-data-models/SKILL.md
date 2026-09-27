---
name: define-data-models
description: Use when adding or modifying Django models in core/models/. Covers ULIDMixin, i18n, optional-field rules, Choices + Literal enums, constraints, and the migration workflow.
---

# Defining data models

Models live in `core/models/`, one file per domain, all re-exported from `core/models/__init__.py`.

## Mandatory base

- Inherit `ULIDMixin` from [core/models/mixins.py](../../../core/models/mixins.py). It provides `id` (26-char ULID PK), `created_at` and `updated_at`. Never declare these manually. Never use UUID or auto-increment IDs.

## Fields

- Wrap every user-facing string in `gettext_lazy as _`: `verbose_name`, `help_text`, `Meta.verbose_name[_plural]`.
- **Optional string fields** (`CharField`, `TextField`, `EmailField`, `URLField`, `SlugField`): `blank=True, default=""`. Never `null=True` on a string field.
- **Optional non-string fields** (FK, Date, JSON, Bool, Int): `null=True, blank=True` is fine.
- **Conditional uniqueness** (empty values may repeat): `UniqueConstraint(fields=["x"], condition=~Q(x=""), name="core_<model>_unique_nonempty_x")` in `Meta.constraints`.

## Closed-set fields: Choices + Literal

Every closed-set string column (status, kind, channel…) gets **two** artefacts in the same model file:

```python
class ProjectStatus(models.TextChoices):
    DRAFT = "draft", _("draft")
    PUBLISHED = "published", _("published")


# Keep in sync with ProjectStatus.values
ProjectStatusValue = Literal["draft", "published"]
```

- The `TextChoices` class is the storage contract (`choices=ProjectStatus.choices`).
- The `Literal` is the type contract, used in pydantic validators and ninja schemas so the enum is enforced natively (no regex `pattern=`, no custom `field_validator`).
- Export both from `core/models/__init__.py` and add a drift test to `web/tests/test_schemas.py`.

Working example: `OTPChannel` / `OTPChannelValue` in [core/models/otp.py](../../../core/models/otp.py).

## Relationships

Always set `related_name=` and `verbose_name=_(...)` on `ForeignKey` / `OneToOneField` / `ManyToManyField`. Reference the user model as `"core.User"`.

## Migrations

- Dev iteration: `./scripts/dev-migrate.sh` wipes the SQLite db and regenerates all `core` migrations.
- Additive change with data preservation: `uv run python manage.py makemigrations core && uv run python manage.py migrate`.

## Docstrings and comments: domain language only

Model files describe entities in pure domain terms. They must not name services, validators, endpoints or planning context ("next PR…"), and must not reference `CLAUDE.md` / `CHANGELOG.md`.

## Anti-patterns

- A new Django app for a new domain. Add a module inside `core/` instead.
- `null=True` on a string field.
- Hand-written `id` / `created_at` / `updated_at`.
- A `TextChoices` class without its `Literal` mirror and drift test.
- Business logic in model methods (it belongs in services).
