from django.db import models

from sentry.backup.scopes import RelocationScope
from sentry.db.models import control_silo_model, sane_repr
from sentry.notifications.models.notificationsettingbase import NotificationSettingBase


@control_silo_model
class NotificationSettingProvider(NotificationSettingBase):
    __relocation_scope__ = RelocationScope.Excluded

    provider = models.CharField(max_length=32, null=False)

    class Meta:
        app_label = "notifications"
        db_table = "sentry_notificationsettingprovider"
        unique_together = (
            (
                "scope_type",
                "scope_identifier",
                "user_id",
                "team_id",
                "provider",
                "type",
            ),
        )
        constraints = [
            models.CheckConstraint(
                condition=models.Q(team_id__isnull=False, user_id__isnull=True)
                | models.Q(team_id__isnull=True, user_id__isnull=False),
                name="notification_setting_provider_team_or_user_check",
            )
        ]

    __repr__ = sane_repr(
        "scope_type",
        "scope_identifier",
        "user_id",
        "team_id",
        "provider",
        "type",
        "value",
    )
