from functools import cached_property
from unittest.mock import MagicMock, patch

import pytest
import responses
from rest_framework.serializers import ValidationError

from sentry.integrations.models.integration import Integration
from sentry.integrations.models.organization_integration import OrganizationIntegration
from sentry.integrations.opsgenie.integration import OpsgenieIntegrationProvider
from sentry.integrations.opsgenie.tasks import (
    ALERT_LEGACY_INTEGRATIONS,
    ALERT_LEGACY_INTEGRATIONS_WITH_NAME,
)
from sentry.integrations.types import EventLifecycleOutcome
from sentry.models.rule import Rule
from sentry.shared_integrations.exceptions import ApiRateLimitedError, ApiUnauthorized
from sentry.testutils.asserts import assert_slo_metric, assert_success_metric
from sentry.testutils.cases import APITestCase, IntegrationTestCase
from sentry.testutils.helpers.features import with_feature
from sentry.testutils.silo import assume_test_silo_mode_of, control_silo_test
from sentry_plugins.opsgenie.plugin import OpsGeniePlugin

EXTERNAL_ID = "test-app"
METADATA = {
    "api_key": "1234-ABCD",
    "base_url": "https://api.opsgenie.com/",
    "domain_name": "test-app.app.opsgenie.com",
}


@control_silo_test
class OpsgenieIntegrationTest(IntegrationTestCase):
    provider = OpsgenieIntegrationProvider
    config_no_key = {
        "base_url": "https://api.opsgenie.com/",
        "provider": "cool-name",
        "api_key": "",
    }
    config_with_key = {
        "base_url": "https://api.opsgenie.com/",
        "provider": "cool-name",
        "api_key": "123-key",
    }
    eu_config_no_key = {
        "base_url": "https://api.eu.opsgenie.com/",
        "provider": "chill-name",
        "api_key": "",
    }
    eu_config_with_key = {
        "base_url": "https://api.eu.opsgenie.com/",
        "provider": "chill-name",
        "api_key": "123-key",
    }

    def setUp(self) -> None:
        super().setUp()
        self.init_path_without_guide = f"{self.init_path}?completed_installation_guide"

    def assert_setup_flow(self, config):
        resp = self.client.get(self.init_path)
        assert resp.status_code == 200

        resp = self.client.post(self.init_path, data=config)
        assert resp.status_code == 200

    @patch("sentry.integrations.utils.metrics.EventLifecycle.record_event")
    def test_installation_no_key(self, mock_record: MagicMock) -> None:
        self.assert_setup_flow(self.config_no_key)

        # SLO assertions
        assert_success_metric(mock_record)

        integration = Integration.objects.get(provider=self.provider.key)
        org_integration = OrganizationIntegration.objects.get(integration_id=integration.id)

        assert org_integration.config["team_table"] == []
        assert org_integration.organization_id == self.organization.id
        assert org_integration.config == {"team_table": []}
        assert integration.external_id == "cool-name"
        assert integration.name == "cool-name"
        assert integration.metadata["domain_name"] == "cool-name.app.opsgenie.com"

    def test_eu_installation_no_key(self) -> None:
        self.assert_setup_flow(self.eu_config_no_key)

        integration = Integration.objects.get(provider=self.provider.key)
        org_integration = OrganizationIntegration.objects.get(integration_id=integration.id)

        assert org_integration.config["team_table"] == []
        assert org_integration.organization_id == self.organization.id
        assert org_integration.config == {"team_table": []}
        assert integration.external_id == "chill-name"
        assert integration.name == "chill-name"
        assert integration.metadata["domain_name"] == "chill-name.app.eu.opsgenie.com"

    def test_installation_with_key(self) -> None:
        self.assert_setup_flow(self.config_with_key)

        integration = Integration.objects.get(provider=self.provider.key)
        org_integration = OrganizationIntegration.objects.get(integration_id=integration.id)

        assert org_integration.config["team_table"] == [
            {
                "team": "my-first-key",
                "id": f"{org_integration.id}-my-first-key",
                "integration_key": "123-key",
            }
        ]
        assert org_integration.organization_id == self.organization.id
        assert integration.external_id == "cool-name"
        assert integration.name == "cool-name"
        assert integration.metadata["domain_name"] == "cool-name.app.opsgenie.com"

    def test_eu_installation_with_key(self) -> None:
        self.assert_setup_flow(self.eu_config_with_key)

        integration = Integration.objects.get(provider=self.provider.key)
        org_integration = OrganizationIntegration.objects.get(integration_id=integration.id)

        assert org_integration.config["team_table"] == [
            {
                "team": "my-first-key",
                "id": f"{org_integration.id}-my-first-key",
                "integration_key": "123-key",
            }
        ]
        assert org_integration.organization_id == self.organization.id
        assert integration.external_id == "chill-name"
        assert integration.name == "chill-name"
        assert integration.metadata["domain_name"] == "chill-name.app.eu.opsgenie.com"

    @responses.activate
    def test_update_config_valid(self) -> None:
        integration = self.create_provider_integration(
            provider="opsgenie", name="test-app", external_id=EXTERNAL_ID, metadata=METADATA
        )

        integration.add_organization(self.organization, self.user)
        installation = integration.get_installation(self.organization.id)

        integration = Integration.objects.get(provider=self.provider.key)
        org_integration = OrganizationIntegration.objects.get(integration_id=integration.id)

        responses.add(
            responses.GET, url="https://api.opsgenie.com/v2/alerts?limit=1", status=200, json={}
        )

        data = {"team_table": [{"id": "", "team": "cool-team", "integration_key": "1234-5678"}]}
        installation.update_organization_config(data)
        team_id = str(org_integration.id) + "-" + "cool-team"
        assert installation.get_config_data() == {
            "team_table": [{"id": team_id, "team": "cool-team", "integration_key": "1234-5678"}]
        }

    @responses.activate
    def test_update_config_invalid(self) -> None:
        integration = self.create_provider_integration(
            provider="opsgenie", name="test-app", external_id=EXTERNAL_ID, metadata=METADATA
        )

        integration.add_organization(self.organization, self.user)
        installation = integration.get_installation(self.organization.id)

        org_integration = OrganizationIntegration.objects.get(integration_id=integration.id)
        team_id = str(org_integration.id) + "-" + "cool-team"

        responses.add(
            responses.GET, url="https://api.opsgenie.com/v2/alerts?limit=1", status=200, json={}
        )

        # valid
        data = {"team_table": [{"id": "", "team": "cool-team", "integration_key": "1234"}]}
        installation.update_organization_config(data)
        assert installation.get_config_data() == {
            "team_table": [{"id": team_id, "team": "cool-team", "integration_key": "1234"}]
        }

        # try duplicate name
        data = {
            "team_table": [
                {"id": team_id, "team": "cool-team", "integration_key": "1234"},
                {"id": "", "team": "cool-team", "integration_key": "1234"},
            ]
        }
        with pytest.raises(ValidationError):
            installation.update_organization_config(data)
        assert installation.get_config_data() == {
            "team_table": [{"id": team_id, "team": "cool-team", "integration_key": "1234"}]
        }

    @responses.activate
    def test_update_config_invalid_rate_limited(self) -> None:
        integration = self.create_provider_integration(
            provider="opsgenie", name="test-app", external_id=EXTERNAL_ID, metadata=METADATA
        )
        integration.add_organization(self.organization, self.user)
        installation = integration.get_installation(self.organization.id)

        data = {
            "team_table": [
                {"id": "", "team": "rad-team", "integration_key": "4321"},
                {"id": "cool-team", "team": "cool-team", "integration_key": "1234"},
            ]
        }
        responses.add(responses.GET, url="https://api.opsgenie.com/v2/alerts?limit=1", status=429)

        with pytest.raises(ApiRateLimitedError):
            installation.update_organization_config(data)

    @responses.activate
    def test_update_config_invalid_integration_key(self) -> None:
        integration = self.create_provider_integration(
            provider="opsgenie", name="test-app", external_id=EXTERNAL_ID, metadata=METADATA
        )
        integration.add_organization(self.organization, self.user)
        installation = integration.get_installation(self.organization.id)

        data = {
            "team_table": [
                {"id": "cool-team", "team": "cool-team", "integration_key": "1234"},
                {"id": "", "team": "rad-team", "integration_key": "4321"},
            ]
        }
        responses.add(responses.GET, url="https://api.opsgenie.com/v2/alerts?limit=1", status=401)

        with pytest.raises(ApiUnauthorized):
            installation.update_organization_config(data)

    @with_feature(
        {
            "organizations:integrations-enterprise-alert-rule": False,
            "organizations:integrations-enterprise-incident-management": False,
        }
    )
    def test_disallow_when_no_business_plan(self) -> None:
        resp = self.client.get(self.init_path)
        assert resp.status_code == 200
        assert (
            b"At least one feature from this list has to be enabled in order to setup the integration"
            in resp.content
        )


class OpsgenieMigrationIntegrationTest(APITestCase):
    @cached_property
    def integration(self):
        integration = self.create_provider_integration(
            provider="opsgenie", name="test-app", external_id=EXTERNAL_ID, metadata=METADATA
        )
        integration.add_organization(self.organization, self.user)
        return integration

    def setUp(self) -> None:
        super().setUp()
        self.project = self.create_project(
            name="thonk", organization=self.organization, teams=[self.team]
        )
        self.plugin = OpsGeniePlugin()
        self.plugin.set_option("enabled", True, self.project)
        self.plugin.set_option("alert_url", "https://api.opsgenie.com/v2/alerts/", self.project)
        self.plugin.set_option("api_key", "123-key", self.project)
        with assume_test_silo_mode_of(Integration):
            self.installation = self.integration.get_installation(self.organization.id)
        self.login_as(self.user)

    @patch("sentry.integrations.utils.metrics.EventLifecycle.record_event")
    def test_migrate_plugin(self, mock_record: MagicMock) -> None:
        """
        Test that 2 projects with the Opsgenie plugin activated that have one alert rule each
        and distinct API keys are successfully migrated.
        """
        with assume_test_silo_mode_of(OrganizationIntegration):
            org_integration = OrganizationIntegration.objects.get(
                integration_id=self.integration.id
            )
            org_integration.config = {"team_table": []}
            org_integration.save()

        project2 = self.create_project(
            name="thinkies", organization=self.organization, teams=[self.team]
        )
        plugin2 = OpsGeniePlugin()
        plugin2.set_option("enabled", True, project2)
        plugin2.set_option("alert_url", "https://api.opsgenie.com/v2/alerts/", project2)
        plugin2.set_option("api_key", "456-key", project2)

        Rule.objects.create(
            label="rule",
            project=self.project,
            data={"match": "all", "actions": [ALERT_LEGACY_INTEGRATIONS]},
        )

        Rule.objects.create(
            label="rule2",
            project=project2,
            data={"match": "all", "actions": [ALERT_LEGACY_INTEGRATIONS]},
        )

        with self.tasks():
            self.installation.schedule_migrate_opsgenie_plugin()

        with assume_test_silo_mode_of(OrganizationIntegration):
            org_integration = OrganizationIntegration.objects.get(
                integration_id=self.integration.id
            )
        id1 = str(self.organization_integration.id) + "-thonk"
        id2 = str(self.organization_integration.id) + "-thinkies"
        # Don't assert order to prevent test flakiness
        assert len(org_integration.config["team_table"]) == 2
        assert {
            "id": id1,
            "team": "thonk [MIGRATED]",
            "integration_key": "123-key",
        } in org_integration.config["team_table"]
        assert {
            "id": id2,
            "team": "thinkies [MIGRATED]",
            "integration_key": "456-key",
        } in org_integration.config["team_table"]

        rule_updated = Rule.objects.get(label="rule", project=self.project)

        assert rule_updated.data["actions"] == [
            ALERT_LEGACY_INTEGRATIONS,
            {
                "id": "sentry.integrations.opsgenie.notify_action.OpsgenieNotifyTeamAction",
                "account": self.integration.id,
                "team": id1,
            },
        ]

        rule2_updated = Rule.objects.get(label="rule2", project=project2)
        assert rule2_updated.data["actions"] == [
            ALERT_LEGACY_INTEGRATIONS,
            {
                "id": "sentry.integrations.opsgenie.notify_action.OpsgenieNotifyTeamAction",
                "account": self.integration.id,
                "team": id2,
            },
        ]

        assert self.plugin.is_enabled(self.project) is False
        assert self.plugin.is_configured(self.project) is False
        assert plugin2.is_enabled(project2) is False
        assert plugin2.is_configured(self.project) is False

        assert_slo_metric(mock_record, EventLifecycleOutcome.SUCCESS)

    def test_no_duplicate_keys(self) -> None:
        """
        Keys should not be migrated twice.
        """
        with assume_test_silo_mode_of(OrganizationIntegration):
            org_integration = OrganizationIntegration.objects.get(
                integration_id=self.integration.id
            )
            org_integration.config = {"team_table": []}
            org_integration.save()

        project2 = self.create_project(
            name="thinkies", organization=self.organization, teams=[self.team]
        )
        plugin2 = OpsGeniePlugin()
        plugin2.set_option("enabled", True, project2)
        plugin2.set_option("alert_url", "https://api.opsgenie.com/v2/alerts/", project2)
        plugin2.set_option("api_key", "123-key", project2)

        with self.tasks():
            self.installation.schedule_migrate_opsgenie_plugin()

        with assume_test_silo_mode_of(OrganizationIntegration):
            org_integration = OrganizationIntegration.objects.get(
                integration_id=self.integration.id
            )
        id1 = str(self.organization_integration.id) + "-thonk"

        assert org_integration.config == {
            "team_table": [
                {"id": id1, "team": "thonk [MIGRATED]", "integration_key": "123-key"},
            ]
        }

    def test_existing_key(self) -> None:
        """
        Test that migration works if a key has already been added to config.
        """
        with assume_test_silo_mode_of(OrganizationIntegration):
            org_integration = OrganizationIntegration.objects.get(
                integration_id=self.integration.id
            )
            org_integration.config = {
                "team_table": [
                    {
                        "id": str(self.organization_integration.id) + "-pikachu",
                        "team": "pikachu",
                        "integration_key": "123-key",
                    },
                ]
            }
            org_integration.save()

        Rule.objects.create(
            label="rule",
            project=self.project,
            data={"match": "all", "actions": [ALERT_LEGACY_INTEGRATIONS]},
        )
        with self.tasks():
            self.installation.schedule_migrate_opsgenie_plugin()

        with assume_test_silo_mode_of(OrganizationIntegration):
            org_integration = OrganizationIntegration.objects.get(
                integration_id=self.integration.id
            )
        assert org_integration.config == {
            "team_table": [
                {
                    "id": str(self.organization_integration.id) + "-pikachu",
                    "team": "pikachu",
                    "integration_key": "123-key",
                },
            ]
        }

        rule_updated = Rule.objects.get(
            label="rule",
            project=self.project,
        )

        assert rule_updated.data["actions"] == [
            ALERT_LEGACY_INTEGRATIONS,
            {
                "id": "sentry.integrations.opsgenie.notify_action.OpsgenieNotifyTeamAction",
                "account": self.integration.id,
                "team": str(self.organization_integration.id) + "-pikachu",
            },
        ]

    def test_multiple_rules(self) -> None:
        """
        Test multiple rules, some of which send notifications to legacy integrations.
        """
        with assume_test_silo_mode_of(OrganizationIntegration):
            org_integration = OrganizationIntegration.objects.get(
                integration_id=self.integration.id
            )
            org_integration.config = {"team_table": []}
            org_integration.save()

        Rule.objects.create(
            label="rule",
            project=self.project,
            data={"match": "all", "actions": [ALERT_LEGACY_INTEGRATIONS]},
        )

        Rule.objects.create(
            label="rule2",
            project=self.project,
            data={"match": "all", "actions": []},
        )

        with self.tasks():
            self.installation.schedule_migrate_opsgenie_plugin()

        with assume_test_silo_mode_of(OrganizationIntegration):
            org_integration = OrganizationIntegration.objects.get(
                integration_id=self.integration.id
            )
        id1 = str(org_integration.id) + "-thonk"
        rule_updated = Rule.objects.get(
            label="rule",
            project=self.project,
        )

        assert rule_updated.data["actions"] == [
            ALERT_LEGACY_INTEGRATIONS,
            {
                "id": "sentry.integrations.opsgenie.notify_action.OpsgenieNotifyTeamAction",
                "account": self.integration.id,
                "team": id1,
            },
        ]

        rule2_updated = Rule.objects.get(
            label="rule2",
            project=self.project,
        )

        assert rule2_updated.data["actions"] == []

    def test_existing_rule(self) -> None:
        """
        Don't add a new recipient from an API key if the recipient already exists.
        """
        with assume_test_silo_mode_of(OrganizationIntegration):
            org_integration = OrganizationIntegration.objects.get(
                integration_id=self.integration.id
            )
            org_integration.config = {
                "team_table": [
                    {
                        "id": str(self.organization_integration.id) + "-pikachu",
                        "team": "pikachu",
                        "integration_key": "123-key",
                    },
                ]
            }
            org_integration.save()

        Rule.objects.create(
            label="rule",
            project=self.project,
            data={
                "match": "all",
                "actions": [
                    ALERT_LEGACY_INTEGRATIONS,
                    {
                        "id": "sentry.integrations.opsgenie.notify_action.OpsgenieNotifyTeamAction",
                        "account": self.integration.id,
                        "team": str(self.organization_integration.id) + "-pikachu",
                    },
                ],
            },
        )
        with self.tasks():
            self.installation.schedule_migrate_opsgenie_plugin()

        with assume_test_silo_mode_of(OrganizationIntegration):
            org_integration = OrganizationIntegration.objects.get(
                integration_id=self.integration.id
            )
        assert org_integration.config == {
            "team_table": [
                {
                    "id": str(self.organization_integration.id) + "-pikachu",
                    "team": "pikachu",
                    "integration_key": "123-key",
                },
            ]
        }

        rule_updated = Rule.objects.get(
            label="rule",
            project=self.project,
        )

        assert rule_updated.data["actions"] == [
            ALERT_LEGACY_INTEGRATIONS,
            {
                "id": "sentry.integrations.opsgenie.notify_action.OpsgenieNotifyTeamAction",
                "account": self.integration.id,
                "team": str(self.organization_integration.id) + "-pikachu",
            },
        ]

    def test_migrate_plugin_with_name(self) -> None:
        """
        Test that the Opsgenie plugin is migrated correctly if the legacy alert action has a name field.
        """
        with assume_test_silo_mode_of(OrganizationIntegration):
            org_integration = OrganizationIntegration.objects.get(
                integration_id=self.integration.id
            )
            org_integration.config = {"team_table": []}
            org_integration.save()

        Rule.objects.create(
            label="rule",
            project=self.project,
            data={"match": "all", "actions": [ALERT_LEGACY_INTEGRATIONS_WITH_NAME]},
        )

        with self.tasks():
            self.installation.schedule_migrate_opsgenie_plugin()

        with assume_test_silo_mode_of(OrganizationIntegration):
            org_integration = OrganizationIntegration.objects.get(
                integration_id=self.integration.id
            )
        id1 = str(self.organization_integration.id) + "-thonk"
        assert org_integration.config == {
            "team_table": [
                {"id": id1, "team": "thonk [MIGRATED]", "integration_key": "123-key"},
            ]
        }

        rule_updated = Rule.objects.get(
            label="rule",
            project=self.project,
        )

        assert rule_updated.data["actions"] == [
            ALERT_LEGACY_INTEGRATIONS,
            {
                "id": "sentry.integrations.opsgenie.notify_action.OpsgenieNotifyTeamAction",
                "account": self.integration.id,
                "team": id1,
            },
        ]

        assert self.plugin.is_enabled(self.project) is False
        assert self.plugin.is_configured(self.project) is False
