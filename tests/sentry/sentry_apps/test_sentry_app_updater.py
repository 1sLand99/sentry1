from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from sentry.constants import SentryAppStatus
from sentry.coreapi import APIError
from sentry.integrations.types import EventLifecycleOutcome
from sentry.models.apitoken import ApiToken
from sentry.sentry_apps.logic import SentryAppUpdater, expand_events
from sentry.sentry_apps.models.sentry_app import SentryApp
from sentry.sentry_apps.models.sentry_app_component import SentryAppComponent
from sentry.sentry_apps.models.servicehook import ServiceHook
from sentry.silo.base import SiloMode
from sentry.testutils.asserts import assert_count_of_metric, assert_success_metric
from sentry.testutils.cases import TestCase
from sentry.testutils.silo import assume_test_silo_mode, control_silo_test


@control_silo_test
class TestUpdater(TestCase):
    def setUp(self) -> None:
        self.user = self.create_user()
        self.org = self.create_organization(owner=self.user)
        self.sentry_app = self.create_sentry_app(
            name="nulldb",
            organization=self.org,
            scopes=("project:read",),
            schema={"elements": [self.create_issue_link_schema()]},
        )
        self.updater = SentryAppUpdater(sentry_app=self.sentry_app)

    def test_updates_name(self) -> None:
        self.updater.name = "A New Thing"
        self.updater.run(user=self.user)
        assert self.sentry_app.name == "A New Thing"

    @patch("sentry.integrations.utils.metrics.EventLifecycle.record_event")
    def test_update_scopes_internal_integration(self, mock_record: MagicMock) -> None:
        self.create_project(organization=self.org)
        sentry_app = self.create_internal_integration(
            scopes=("project:read",), organization=self.org
        )
        token = self.create_internal_integration_token(
            user=self.user, internal_integration=sentry_app
        )

        updater = SentryAppUpdater(sentry_app=sentry_app)
        updater.scopes = ["project:read", "project:write"]
        updater.run(user=self.user)
        token.refresh_from_db()

        assert sentry_app.get_scopes() == ["project:read", "project:write"]
        assert ApiToken.objects.get(application=sentry_app.application).get_scopes() == [
            "project:read",
            "project:write",
        ]

        # SLO assertions
        assert_success_metric(mock_record=mock_record)

        # CREATE (success) -> INSTALLATION_CREATE (success) -> UPDATE (success)
        assert_count_of_metric(
            mock_record=mock_record, outcome=EventLifecycleOutcome.STARTED, outcome_count=3
        )
        assert_count_of_metric(
            mock_record=mock_record, outcome=EventLifecycleOutcome.SUCCESS, outcome_count=3
        )

    def test_updates_unpublished_app_scopes(self) -> None:
        # create both expired token and not expired tokens
        ApiToken.objects.create(
            application=self.sentry_app.application,
            user=self.sentry_app.proxy_user,
            scopes=self.sentry_app.scopes,
            scope_list=self.sentry_app.scope_list,
            expires_at=(timezone.now() + timedelta(hours=1)),
        )
        ApiToken.objects.create(
            application=self.sentry_app.application,
            user=self.sentry_app.proxy_user,
            scopes=self.sentry_app.scopes,
            scope_list=self.sentry_app.scope_list,
            expires_at=(timezone.now() - timedelta(hours=1)),
        )
        self.updater.scopes = ["project:read", "project:write"]
        self.updater.run(user=self.user)
        assert self.sentry_app.get_scopes() == ["project:read", "project:write"]
        tokens = ApiToken.objects.filter(application=self.sentry_app.application).order_by(
            "expires_at"
        )
        assert tokens[0].get_scopes() == ["project:read"]
        assert tokens[1].get_scopes() == ["project:read", "project:write"]

    def test_doesnt_update_published_app_scopes(self) -> None:
        sentry_app = self.create_sentry_app(
            name="sentry", organization=self.org, scopes=("project:read",), published=True
        )
        updater = SentryAppUpdater(sentry_app=sentry_app)
        updater.scopes = ["project:read", "project:write"]

        with pytest.raises(APIError):
            updater.run(self.user)

    def test_update_webhook_published_app(self) -> None:
        sentry_app = self.create_sentry_app(
            name="sentry", organization=self.org, scopes=("project:read",), published=True
        )
        updater = SentryAppUpdater(sentry_app=sentry_app)
        # pass in scopes but as the same value
        updater.scopes = ["project:read"]
        updater.webhook_url = "http://example.com/hooks"
        updater.run(self.user)
        assert sentry_app.webhook_url == "http://example.com/hooks"

    def test_doesnt_update_app_with_invalid_event_permissions(self) -> None:
        sentry_app = self.create_sentry_app(
            name="sentry", organization=self.org, scopes=("project:read",)
        )
        updater = SentryAppUpdater(sentry_app=sentry_app)
        updater.events = ["issue"]
        with pytest.raises(APIError):
            updater.run(self.user)

    def test_doesnt_update_verify_install_if_internal(self) -> None:
        self.create_project(organization=self.org)
        sentry_app = self.create_internal_integration(name="Internal", organization=self.org)
        updater = SentryAppUpdater(sentry_app=sentry_app)
        updater.verify_install = True
        with pytest.raises(APIError):
            updater.run(self.user)

    def test_updates_service_hook_events(self) -> None:
        sentry_app = self.create_sentry_app(
            name="sentry",
            organization=self.org,
            scopes=("project:read", "event:read"),
            events=("event.alert",),
        )
        self.create_sentry_app_installation(slug="sentry")
        updater = SentryAppUpdater(
            sentry_app=sentry_app,
            events=[
                "issue",
            ],
        )
        updater.run(self.user)
        assert sentry_app.events == expand_events(["issue"])
        with assume_test_silo_mode(SiloMode.REGION):
            service_hook = ServiceHook.objects.filter(application_id=sentry_app.application_id)[0]
        assert service_hook.events == expand_events(["issue"])

    def test_updates_webhook_url(self) -> None:
        sentry_app = self.create_sentry_app(
            name="sentry",
            organization=self.org,
            scopes=("project:read", "event:read"),
            events=("event.alert",),
        )
        self.create_sentry_app_installation(slug="sentry")
        updater = SentryAppUpdater(sentry_app=sentry_app, webhook_url="http://example.com/hooks")
        updater.run(self.user)
        assert sentry_app.webhook_url == "http://example.com/hooks"
        with assume_test_silo_mode(SiloMode.REGION):
            service_hook = ServiceHook.objects.get(application_id=sentry_app.application_id)
        assert service_hook.url == "http://example.com/hooks"
        assert service_hook.events == expand_events(["event.alert"])

    def test_updates_redirect_url(self) -> None:
        self.updater.redirect_url = "http://example.com/finish-setup"
        self.updater.run(self.user)
        assert self.sentry_app.redirect_url == "http://example.com/finish-setup"

    def test_updates_is_alertable(self) -> None:
        self.updater.is_alertable = True
        self.updater.run(self.user)
        assert self.sentry_app.is_alertable

    def test_updates_schema(self) -> None:
        ui_component = SentryAppComponent.objects.get(sentry_app_id=self.sentry_app.id)
        self.updater.schema = {"elements": [self.create_alert_rule_action_schema()]}
        self.updater.run(self.user)
        new_ui_component = SentryAppComponent.objects.get(sentry_app_id=self.sentry_app.id)
        assert not ui_component.type == new_ui_component.type
        assert self.sentry_app.schema == {"elements": [self.create_alert_rule_action_schema()]}

    def test_updates_overview(self) -> None:
        self.updater.overview = "Description of my very cool application"
        self.updater.run(self.user)
        assert self.sentry_app.overview == "Description of my very cool application"

    def test_update_popularity_if_superuser(self) -> None:
        popularity = 27
        self.updater.popularity = popularity
        self.user.is_superuser = True
        self.updater.run(self.user)
        assert self.sentry_app.popularity == popularity

    def test_doesnt_update_popularity_if_not_superuser(self) -> None:
        self.updater.popularity = 27
        self.updater.run(self.user)
        assert self.sentry_app.popularity == SentryApp._meta.get_field("popularity").default

    def test_update_status_if_superuser(self) -> None:
        self.updater.status = "published"
        self.user.is_superuser = True
        self.updater.run(self.user)
        assert self.sentry_app.status == SentryAppStatus.PUBLISHED

    def test_doesnt_update_status_if_not_superuser(self) -> None:
        self.updater.status = "published"
        self.updater.run(self.user)
        assert self.sentry_app.status == SentryAppStatus.UNPUBLISHED

    @patch("sentry.integrations.utils.metrics.EventLifecycle.record_event")
    def test_create_service_hook_on_update(self, mock_record: MagicMock) -> None:
        self.create_project(organization=self.org)
        internal_app = self.create_internal_integration(
            name="Internal", organization=self.org, webhook_url=None, scopes=("event:read",)
        )
        with assume_test_silo_mode(SiloMode.REGION):
            assert len(ServiceHook.objects.filter(application_id=internal_app.application_id)) == 0
        updater = SentryAppUpdater(sentry_app=internal_app)
        updater.webhook_url = "https://sentry.io/hook"
        updater.events = ["issue"]
        updater.run(self.user)
        with assume_test_silo_mode(SiloMode.REGION):
            service_hook = ServiceHook.objects.get(application_id=internal_app.application_id)
        assert service_hook.url == "https://sentry.io/hook"
        assert service_hook.events == expand_events(["issue"])

        # SLO assertions
        assert_success_metric(mock_record=mock_record)

        # APP_CREATE (success) -> INSTALL_CREATE (success) -> WEBHOOK_UPDATE (success)
        assert_count_of_metric(
            mock_record=mock_record, outcome=EventLifecycleOutcome.STARTED, outcome_count=3
        )
        assert_count_of_metric(
            mock_record=mock_record, outcome=EventLifecycleOutcome.SUCCESS, outcome_count=3
        )

    def test_delete_service_hook_on_update(self) -> None:
        self.create_project(organization=self.org)
        internal_app = self.create_internal_integration(
            name="Internal", organization=self.org, webhook_url="https://sentry.io/hook"
        )
        with assume_test_silo_mode(SiloMode.REGION):
            assert len(ServiceHook.objects.filter(application_id=internal_app.application_id)) == 1
        updater = SentryAppUpdater(sentry_app=internal_app)
        updater.webhook_url = ""
        updater.run(self.user)
        with assume_test_silo_mode(SiloMode.REGION):
            assert len(ServiceHook.objects.filter(application_id=internal_app.application_id)) == 0
