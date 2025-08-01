from __future__ import annotations

from collections.abc import Generator
from unittest.mock import patch

import pytest
from django.db import router
from django.http.response import HttpResponse

from sentry.integrations.example import AliasedIntegrationProvider, ExampleIntegrationProvider
from sentry.integrations.gitlab.integration import GitlabIntegrationProvider
from sentry.integrations.models.integration import Integration
from sentry.integrations.models.organization_integration import OrganizationIntegration
from sentry.integrations.pipeline import IntegrationPipeline
from sentry.integrations.types import EventLifecycleOutcome
from sentry.models.organizationmapping import OrganizationMapping
from sentry.models.organizationmember import OrganizationMember
from sentry.models.repository import Repository
from sentry.organizations.absolute_url import generate_organization_url
from sentry.organizations.services.organization.serial import serialize_rpc_organization
from sentry.plugins.base import plugins
from sentry.plugins.bases.issue2 import IssuePlugin2
from sentry.signals import receivers_raise_on_send
from sentry.silo.base import SiloMode
from sentry.silo.safety import unguarded_write
from sentry.testutils.asserts import assert_count_of_metric, assert_success_metric
from sentry.testutils.cases import IntegrationTestCase
from sentry.testutils.helpers import override_options
from sentry.testutils.outbox import outbox_runner
from sentry.testutils.region import override_regions
from sentry.testutils.silo import assume_test_silo_mode, assume_test_silo_mode_of, control_silo_test
from sentry.types.region import Region, RegionCategory
from sentry.users.models.identity import Identity


class ExamplePlugin(IssuePlugin2):
    slug = "example"


def naive_build_integration(data):
    return data


@control_silo_test
@patch(
    "sentry.integrations.example.ExampleIntegrationProvider.build_integration",
    side_effect=naive_build_integration,
)
class FinishPipelineTestCase(IntegrationTestCase):
    provider = ExampleIntegrationProvider
    regions = (
        Region("na", 0, "North America", RegionCategory.MULTI_TENANT),
        Region("eu", 5, "Europe", RegionCategory.MULTI_TENANT),
    )
    external_id = "dummy_id-123"

    @pytest.fixture(autouse=True)
    def _register_example_plugin(self) -> Generator[None]:
        plugins.register(ExamplePlugin)
        yield
        plugins.unregister(ExamplePlugin)

    @pytest.fixture(autouse=True)
    def _modify_provider(self):
        with patch.multiple(
            self.provider,
            needs_default_identity=False,
            is_region_restricted=False,
        ):
            yield

    def _setup_region_restriction(self):
        self.provider.is_region_restricted = True
        na_orgs = [
            self.create_organization(name="na_org"),
            self.create_organization(name="na_org_2"),
        ]
        integration = self.create_provider_integration(
            name="test", external_id=self.external_id, provider=self.provider.key
        )
        with (
            receivers_raise_on_send(),
            outbox_runner(),
            unguarded_write(using=router.db_for_write(OrganizationMapping)),
        ):
            for org in na_orgs:
                integration.add_organization(org)
                mapping = OrganizationMapping.objects.get(organization_id=org.id)
                mapping.update(region_name="na")

    def test_with_data(self, *args) -> None:
        data = {
            "external_id": self.external_id,
            "name": "Name",
            "metadata": {"url": "https://example.com"},
        }
        self.pipeline.state.data = data
        resp = self.pipeline.finish_pipeline()

        assert isinstance(resp, HttpResponse)
        self.assertDialogSuccess(resp)
        assert b"document.origin);" in resp.content

        integration = Integration.objects.get(
            provider=self.provider.key, external_id=self.external_id
        )
        assert integration.name == data["name"]
        assert integration.metadata == data["metadata"]
        assert OrganizationIntegration.objects.filter(
            organization_id=self.organization.id, integration_id=integration.id
        ).exists()

    def test_with_customer_domain(self, *args) -> None:
        with self.feature({"system:multi-region": True}):
            data = {
                "external_id": self.external_id,
                "name": "Name",
                "metadata": {"url": "https://example.com"},
            }
            self.pipeline.state.data = data
            resp = self.pipeline.finish_pipeline()

            assert isinstance(resp, HttpResponse)
            self.assertDialogSuccess(resp)
            assert (
                f', "{generate_organization_url(self.organization.slug)}");'.encode()
                in resp.content
            )

            integration = Integration.objects.get(
                provider=self.provider.key, external_id=self.external_id
            )
            assert integration.name == data["name"]
            assert integration.metadata == data["metadata"]
            assert OrganizationIntegration.objects.filter(
                organization_id=self.organization.id, integration_id=integration.id
            ).exists()

    @patch("sentry.signals.integration_added.send_robust")
    def test_provider_should_check_region_violation(self, *args) -> None:
        """Ensures we validate regions if `provider.is_region_restricted` is set to True"""
        self.provider.is_region_restricted = True
        self.pipeline.state.data = {"external_id": self.external_id}
        with patch(
            "sentry.integrations.pipeline.is_violating_region_restriction"
        ) as mock_check_violation:
            self.pipeline.finish_pipeline()
            assert mock_check_violation.called

    @patch("sentry.signals.integration_added.send_robust")
    def test_provider_should_not_check_region_violation(self, *args) -> None:
        """Ensures we don't reject regions if `provider.is_region_restricted` is set to False"""
        self.pipeline.state.data = {"external_id": self.external_id}
        with patch(
            "sentry.integrations.pipeline.is_violating_region_restriction"
        ) as mock_check_violation:
            self.pipeline.finish_pipeline()
            assert not mock_check_violation.called

    @patch("sentry.signals.integration_added.send_robust")
    def test_is_violating_region_restriction_success(self, *args) -> None:
        """Ensures pipeline can complete if all integration organizations reside in one region."""
        self._setup_region_restriction()

        # Installing organization is from the same region
        mapping = OrganizationMapping.objects.get(organization_id=self.organization.id)

        with unguarded_write(using=router.db_for_write(OrganizationMapping)):
            mapping.update(region_name="na")

        self.pipeline.state.data = {"external_id": self.external_id}
        with (
            override_regions(self.regions),
            patch("sentry.integrations.pipeline.IntegrationPipeline._dialog_response") as resp,
        ):
            self.pipeline.finish_pipeline()
            _data, success = resp.call_args[0]
            assert success

    @patch("sentry.signals.integration_added.send_robust")
    def test_is_violating_region_restriction_failure(self, *args) -> None:
        """Ensures pipeline can produces an error if all integration organizations do not reside in one region."""
        self._setup_region_restriction()

        # Installing organization is from a different region
        mapping = OrganizationMapping.objects.get(organization_id=self.organization.id)

        with unguarded_write(using=router.db_for_write(OrganizationMapping)):
            mapping.update(region_name="eu")

        self.pipeline.state.data = {"external_id": self.external_id}
        with override_regions(self.regions):
            response = self.pipeline.finish_pipeline()
            assert isinstance(response, HttpResponse)
            error_message = "This integration has already been installed on another Sentry organization which resides in a different region. Installation could not be completed."
            assert error_message in response.content.decode()

            if SiloMode.get_current_mode() == SiloMode.MONOLITH:
                assert error_message not in response.content.decode()
            if SiloMode.get_current_mode() == SiloMode.CONTROL:
                assert error_message in response.content.decode()

    def test_aliased_integration_key(self, *args) -> None:
        self.provider = AliasedIntegrationProvider
        self.setUp()

        data = {
            "external_id": self.external_id,
            "name": "Name",
            "metadata": {"url": "https://example.com"},
        }
        self.pipeline.state.data = data
        resp = self.pipeline.finish_pipeline()

        self.assertDialogSuccess(resp)

        # Creates the Integration using ``integration_key`` instead of ``key``
        assert Integration.objects.filter(
            provider=self.provider.integration_key, external_id=self.external_id
        ).exists()

    def test_with_expect_exists(self, *args) -> None:
        old_integration = self.create_provider_integration(
            provider=self.provider.key, external_id=self.external_id, name="Tester"
        )
        self.pipeline.state.data = {"expect_exists": True, "external_id": self.external_id}
        resp = self.pipeline.finish_pipeline()

        self.assertDialogSuccess(resp)
        integration = Integration.objects.get(
            provider=self.provider.key, external_id=self.external_id
        )
        assert integration.name == old_integration.name
        assert OrganizationIntegration.objects.filter(
            organization_id=self.organization.id, integration_id=integration.id
        ).exists()

    def test_expect_exists_does_not_update(self, *args) -> None:
        old_integration = self.create_provider_integration(
            provider=self.provider.key,
            external_id=self.external_id,
            name="Tester",
            metadata={"url": "https://example.com"},
        )
        self.pipeline.state.data = {
            "expect_exists": True,
            "external_id": self.external_id,
            "name": "Should Not Update",
            "metadata": {"url": "https://wrong.com"},
        }
        resp = self.pipeline.finish_pipeline()

        self.assertDialogSuccess(resp)
        integration = Integration.objects.get(
            provider=self.provider.key, external_id=self.external_id
        )
        assert integration.name == old_integration.name
        assert integration.metadata == old_integration.metadata
        assert OrganizationIntegration.objects.filter(
            organization_id=self.organization.id, integration_id=integration.id
        ).exists()

    def test_with_default_id(self, *args) -> None:
        self.provider.needs_default_identity = True
        data = {
            "external_id": self.external_id,
            "name": "Name",
            "metadata": {"url": "https://example.com"},
            "user_identity": {
                "type": "plugin",
                "external_id": "AccountId",
                "scopes": [],
                "data": {
                    "access_token": "token12345",
                    "expires_in": "123456789",
                    "refresh_token": "refresh12345",
                    "token_type": "typetype",
                },
            },
        }
        self.pipeline.state.data = data
        resp = self.pipeline.finish_pipeline()

        self.assertDialogSuccess(resp)

        integration = Integration.objects.get(
            provider=self.provider.key, external_id=self.external_id
        )
        org_integration = OrganizationIntegration.objects.get(
            organization_id=self.organization.id, integration_id=integration.id
        )
        assert org_integration.default_auth_id is not None
        assert Identity.objects.filter(id=org_integration.default_auth_id).exists()

    @patch("sentry.integrations.utils.metrics.EventLifecycle.record_event")
    def test_default_identity_does_update(self, mock_record, *args) -> None:
        self.provider.needs_default_identity = True
        old_identity_id = 234567
        integration = self.create_provider_integration(
            provider=self.provider.key,
            external_id=self.external_id,
            metadata={"url": "https://example.com"},
        )
        self.create_organization_integration(
            organization_id=self.organization.id,
            integration=integration,
            default_auth_id=old_identity_id,
        )
        self.pipeline.state.data = {
            "external_id": self.external_id,
            "name": "Name",
            "metadata": {"url": "https://example.com"},
            "user_identity": {
                "type": "plugin",
                "external_id": "AccountId",
                "scopes": [],
                "data": {
                    "access_token": "token12345",
                    "expires_in": "123456789",
                    "refresh_token": "refresh12345",
                    "token_type": "typetype",
                },
            },
        }

        resp = self.pipeline.finish_pipeline()
        self.assertDialogSuccess(resp)

        org_integration = OrganizationIntegration.objects.get(
            organization_id=self.organization.id, integration_id=integration.id
        )
        identity = Identity.objects.get(external_id="AccountId")
        assert org_integration.default_auth_id == identity.id

        # SLO assertions
        assert_success_metric(mock_record)

        assert_count_of_metric(
            mock_record=mock_record, outcome=EventLifecycleOutcome.STARTED, outcome_count=1
        )
        assert_count_of_metric(
            mock_record=mock_record, outcome=EventLifecycleOutcome.SUCCESS, outcome_count=1
        )

    def test_existing_identity_becomes_default_auth_on_new_orgintegration(self, *args) -> None:
        # The reinstall flow will result in an existing identity provider, identity
        # and integration records. Ensure that the new organizationintegration gets
        # a default_auth_id set.
        self.provider.needs_default_identity = True
        integration = self.create_provider_integration(
            provider=self.provider.key,
            external_id=self.external_id,
            metadata={"url": "https://example.com"},
        )
        identity_provider = self.create_identity_provider(
            external_id=self.external_id, type="plugin"
        )
        identity = Identity.objects.create(
            idp_id=identity_provider.id, external_id="AccountId", user_id=self.user.id
        )
        self.pipeline.state.data = {
            "external_id": self.external_id,
            "name": "Name",
            "metadata": {"url": "https://example.com"},
            "user_identity": {
                "type": "plugin",
                "external_id": "AccountId",
                "scopes": [],
                "data": {
                    "access_token": "token12345",
                    "expires_in": "123456789",
                    "refresh_token": "refresh12345",
                    "token_type": "typetype",
                },
            },
        }
        resp = self.pipeline.finish_pipeline()
        self.assertDialogSuccess(resp)

        org_integration = OrganizationIntegration.objects.get(
            organization_id=self.organization.id, integration_id=integration.id
        )
        assert org_integration.default_auth_id == identity.id

    def test_new_external_id_same_user(self, *args) -> None:
        # we need to make sure any other org_integrations have the same
        # identity that we use for the new one
        self.provider.needs_default_identity = True
        integration = self.create_provider_integration(
            provider=self.provider.key,
            external_id=self.external_id,
            metadata={"url": "https://example.com"},
        )
        identity_provider = self.create_identity_provider(
            external_id=self.external_id, type="plugin"
        )
        identity = Identity.objects.create(
            idp_id=identity_provider.id, external_id="AccountId", user_id=self.user.id
        )
        org2 = self.create_organization(owner=self.user)
        integration.add_organization(org2, default_auth_id=identity.id)
        self.pipeline.state.data = {
            "external_id": self.external_id,
            "name": "Name",
            "metadata": {"url": "https://example.com"},
            "user_identity": {
                "type": "plugin",
                "external_id": "new_external_id",
                "scopes": [],
                "data": {
                    "access_token": "token12345",
                    "expires_in": "123456789",
                    "refresh_token": "refresh12345",
                    "token_type": "typetype",
                },
            },
        }
        resp = self.pipeline.finish_pipeline()
        self.assertDialogSuccess(resp)

        org_integrations = OrganizationIntegration.objects.filter(integration_id=integration.id)
        identity = Identity.objects.get(idp_id=identity_provider.id, external_id="new_external_id")
        for org_integration in org_integrations:
            assert org_integration.default_auth_id == identity.id

    def test_different_user_same_external_id_no_default_needed(self, *args) -> None:
        new_user = self.create_user()
        integration = self.create_provider_integration(
            provider=self.provider.key,
            external_id=self.external_id,
            metadata={"url": "https://example.com"},
        )
        identity_provider = self.create_identity_provider(
            external_id=self.external_id, type=self.provider.key
        )
        Identity.objects.create(
            idp_id=identity_provider.id, external_id="AccountId", user_id=new_user.id
        )
        self.pipeline.state.data = {
            "external_id": self.external_id,
            "name": "Name",
            "metadata": {"url": "https://example.com"},
            "user_identity": {
                "type": self.provider.key,
                "external_id": "AccountId",
                "scopes": [],
                "data": {},
            },
        }
        resp = self.pipeline.finish_pipeline()
        self.assertDialogSuccess(resp)
        assert OrganizationIntegration.objects.filter(
            integration_id=integration.id, organization_id=self.organization.id
        ).exists()

    @patch("sentry.plugins.migrator.Migrator.run")
    def test_disabled_plugin_when_fully_migrated(self, run, *args) -> None:
        with assume_test_silo_mode(SiloMode.REGION):
            Repository.objects.create(
                organization_id=self.organization.id,
                name="user/repo",
                url="https://example.org/user/repo",
                provider=self.provider.key,
                external_id=self.external_id,
            )

        self.pipeline.state.data = {
            "external_id": self.external_id,
            "name": "Name",
            "metadata": {"url": "https://example.com"},
        }

        self.pipeline.finish_pipeline()

        assert run.called

    @patch("sentry.integrations.pipeline.logger")
    def test_disallow_with_no_permission(self, mock_logger, *args) -> None:
        member_user = self.create_user()
        self.create_member(user=member_user, organization=self.organization, role="member")
        self.login_as(member_user)

        # partially copied from IntegrationTestCase.setUp()
        # except the user is not an owner
        with assume_test_silo_mode(SiloMode.REGION):
            rpc_organization = serialize_rpc_organization(self.organization)

        self.request = self.make_request(member_user)

        self.pipeline = IntegrationPipeline(
            request=self.request,
            organization=rpc_organization,
            provider_key=self.provider.key,
        )
        self.pipeline.initialize()
        self.save_session()

        data = {
            "external_id": self.external_id,
            "name": "Name",
            "metadata": {"url": "https://example.com"},
        }
        self.pipeline.state.data = data

        # attempt to finish pipeline with no 'org:integrations' scope
        resp = self.pipeline.finish_pipeline()
        assert isinstance(resp, HttpResponse)
        assert (
            "You must be an organization owner, manager or admin to install this integration."
            in resp.content.decode()
        )

        extra = {
            "error_message": "You must be an organization owner, manager or admin to install this integration.",
            "organization_id": self.organization.id,
            "user_id": member_user.id,
            "provider_key": "example",
        }
        mock_logger.info.assert_called_with("build-integration.permission_error", extra=extra)

    def test_allow_with_superuser(self, *args) -> None:
        member_user = self.create_user(is_superuser=True)
        self.create_member(user=member_user, organization=self.organization, role="member")
        self.login_as(member_user, superuser=True)

        with assume_test_silo_mode(SiloMode.REGION):
            rpc_organization = serialize_rpc_organization(self.organization)

        self.request = self.make_request(member_user, is_superuser=True)

        self.pipeline = IntegrationPipeline(
            request=self.request,
            organization=rpc_organization,
            provider_key=self.provider.key,
        )
        self.pipeline.initialize()
        self.save_session()

        data = {
            "external_id": self.external_id,
            "name": "Name",
            "metadata": {"url": "https://example.com"},
        }
        self.pipeline.state.data = data

        # should be allowed to install integration because of superuser
        resp = self.pipeline.finish_pipeline()
        self.assertDialogSuccess(resp)

    @override_options({"superuser.read-write.ga-rollout": True})
    def test_allow_with_superuser_su_split(self, *args) -> None:
        member_user = self.create_user(is_superuser=True)
        self.create_member(user=member_user, organization=self.organization, role="member")
        self.login_as(member_user, superuser=True)

        with assume_test_silo_mode(SiloMode.REGION):
            rpc_organization = serialize_rpc_organization(self.organization)

        self.request = self.make_request(member_user, is_superuser=True)

        self.pipeline = IntegrationPipeline(
            request=self.request,
            organization=rpc_organization,
            provider_key=self.provider.key,
        )
        self.pipeline.initialize()
        self.save_session()

        data = {
            "external_id": self.external_id,
            "name": "Name",
            "metadata": {"url": "https://example.com"},
        }
        self.pipeline.state.data = data

        # should be allowed to install integration because of superuser
        resp = self.pipeline.finish_pipeline()
        self.assertDialogSuccess(resp)

    @patch("sentry.integrations.utils.metrics.EventLifecycle.record_event")
    @patch("sentry.integrations.pipeline.logger")
    def test_disallow_with_removed_membership(self, mock_logger, mock_record, *args) -> None:
        member_user = self.create_user()
        om = self.create_member(user=member_user, organization=self.organization, role="manager")
        self.login_as(member_user)

        # partially copied from IntegrationTestCase.setUp()
        # except the user is not an owner
        with assume_test_silo_mode(SiloMode.REGION):
            rpc_organization = serialize_rpc_organization(self.organization)

        self.request = self.make_request(member_user)

        self.pipeline = IntegrationPipeline(
            request=self.request,
            organization=rpc_organization,
            provider_key=self.provider.key,
        )
        self.pipeline.initialize()
        self.save_session()

        data = {
            "external_id": self.external_id,
            "name": "Name",
            "metadata": {"url": "https://example.com"},
        }
        self.pipeline.state.data = data
        with outbox_runner(), assume_test_silo_mode_of(OrganizationMember):
            om.delete()

        # attempt to finish pipeline without org membership
        resp = self.pipeline.finish_pipeline()
        assert isinstance(resp, HttpResponse)
        assert (
            "You must be an organization owner, manager or admin to install this integration."
            in resp.content.decode()
        )

        extra = {
            "error_message": "You must be an organization owner, manager or admin to install this integration.",
            "organization_id": self.organization.id,
            "user_id": member_user.id,
            "provider_key": "example",
        }
        mock_logger.info.assert_called_with("build-integration.permission_error", extra=extra)

        # SLO assertions
        assert_success_metric(mock_record)

        assert_count_of_metric(
            mock_record=mock_record, outcome=EventLifecycleOutcome.STARTED, outcome_count=1
        )
        assert_count_of_metric(
            mock_record=mock_record, outcome=EventLifecycleOutcome.SUCCESS, outcome_count=1
        )


@control_silo_test
@patch(
    "sentry.integrations.gitlab.integration.GitlabIntegrationProvider.build_integration",
    side_effect=naive_build_integration,
)
class GitlabFinishPipelineTest(IntegrationTestCase):
    provider = GitlabIntegrationProvider
    external_id = "dummy_id-123"

    def test_different_user_same_external_id(self, *args) -> None:
        new_user = self.create_user()
        self.setUp()
        integration = self.create_provider_integration(
            provider=self.provider.key,
            external_id=self.external_id,
            metadata={"url": "https://example.com"},
        )
        identity_provider = self.create_identity_provider(
            external_id=self.external_id, type=self.provider.key
        )
        Identity.objects.create(
            idp_id=identity_provider.id, external_id="AccountId", user_id=new_user.id
        )
        self.pipeline.state.data = {
            "external_id": self.external_id,
            "name": "Name",
            "metadata": {"url": "https://example.com"},
            "user_identity": {
                "type": self.provider.key,
                "external_id": "AccountId",
                "scopes": [],
                "data": {},
            },
        }
        resp = self.pipeline.finish_pipeline()
        assert isinstance(resp, HttpResponse)
        assert not OrganizationIntegration.objects.filter(integration_id=integration.id)
        assert "account is linked to a different Sentry user" in resp.content.decode()
