import hashlib
import hmac
from copy import deepcopy
from unittest.mock import patch

from django.urls import reverse

from sentry.constants import ObjectStatus
from sentry.prevent.models import PreventAIConfiguration
from sentry.prevent.types.config import PREVENT_AI_CONFIG_DEFAULT
from sentry.silo.base import SiloMode
from sentry.testutils.cases import APITestCase
from sentry.testutils.silo import assume_test_silo_mode

VALID_ORG_CONFIG = {
    "schema_version": "v1",
    "org_defaults": {
        "bug_prediction": {
            "enabled": True,
            "sensitivity": "medium",
            "triggers": {"on_command_phrase": True, "on_ready_for_review": True},
        },
        "test_generation": {
            "enabled": False,
            "triggers": {"on_command_phrase": True, "on_ready_for_review": False},
        },
        "vanilla": {
            "enabled": False,
            "sensitivity": "medium",
            "triggers": {"on_command_phrase": True, "on_ready_for_review": False},
        },
    },
    "repo_overrides": {},
}


class TestPreventPrReviewResolvedConfigsEndpoint(APITestCase):
    def _auth_header_for_get(self, url: str, params: dict[str, str], secret: str) -> str:
        # For GET we sign an empty JSON array body per Rpcsignature rpc0
        message = b"[]"
        signature = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
        return f"Rpcsignature rpc0:{signature}"

    @patch(
        "sentry.overwatch.endpoints.overwatch_rpc.settings.OVERWATCH_RPC_SHARED_SECRET",
        ["test-secret"],
    )
    def test_requires_auth(self):
        url = reverse("sentry-api-0-prevent-pr-review-configs-resolved")
        # Missing auth
        resp = self.client.get(url, {"sentryOrgId": "123"})
        assert resp.status_code == 403

    @patch(
        "sentry.overwatch.endpoints.overwatch_rpc.settings.OVERWATCH_RPC_SHARED_SECRET",
        ["test-secret"],
    )
    def test_missing_sentry_org_id_returns_400(self):
        """Test that missing sentryOrgId parameter returns 400."""
        url = reverse("sentry-api-0-prevent-pr-review-configs-resolved")
        auth = self._auth_header_for_get(url, {}, "test-secret")
        resp = self.client.get(url, HTTP_AUTHORIZATION=auth)
        assert resp.status_code == 400
        assert "sentryOrgId" in resp.data["detail"]

    @patch(
        "sentry.overwatch.endpoints.overwatch_rpc.settings.OVERWATCH_RPC_SHARED_SECRET",
        ["test-secret"],
    )
    def test_invalid_sentry_org_id_returns_400(self):
        """Test that invalid sentryOrgId (non-integer) returns 400."""
        url = reverse("sentry-api-0-prevent-pr-review-configs-resolved")
        params = {"sentryOrgId": "not-a-number", "gitOrgName": "test-org", "provider": "github"}
        auth = self._auth_header_for_get(url, params, "test-secret")
        resp = self.client.get(url, params, HTTP_AUTHORIZATION=auth)
        assert resp.status_code == 400
        assert "must be a valid integer" in resp.data["detail"]

    @patch(
        "sentry.overwatch.endpoints.overwatch_rpc.settings.OVERWATCH_RPC_SHARED_SECRET",
        ["test-secret"],
    )
    def test_negative_sentry_org_id_returns_400(self):
        """Test that negative sentryOrgId returns 400."""
        url = reverse("sentry-api-0-prevent-pr-review-configs-resolved")
        params = {"sentryOrgId": "-123", "gitOrgName": "test-org", "provider": "github"}
        auth = self._auth_header_for_get(url, params, "test-secret")
        resp = self.client.get(url, params, HTTP_AUTHORIZATION=auth)
        assert resp.status_code == 400
        assert "must be a positive integer" in resp.data["detail"]

    @patch(
        "sentry.overwatch.endpoints.overwatch_rpc.settings.OVERWATCH_RPC_SHARED_SECRET",
        ["test-secret"],
    )
    def test_zero_sentry_org_id_returns_400(self):
        """Test that zero sentryOrgId returns 400."""
        url = reverse("sentry-api-0-prevent-pr-review-configs-resolved")
        params = {"sentryOrgId": "0", "gitOrgName": "test-org", "provider": "github"}
        auth = self._auth_header_for_get(url, params, "test-secret")
        resp = self.client.get(url, params, HTTP_AUTHORIZATION=auth)
        assert resp.status_code == 400
        assert "must be a positive integer" in resp.data["detail"]

    @patch(
        "sentry.overwatch.endpoints.overwatch_rpc.settings.OVERWATCH_RPC_SHARED_SECRET",
        ["test-secret"],
    )
    def test_missing_git_org_name_returns_400(self):
        """Test that missing gitOrgName parameter returns 400."""
        url = reverse("sentry-api-0-prevent-pr-review-configs-resolved")
        params = {"sentryOrgId": "123"}
        auth = self._auth_header_for_get(url, params, "test-secret")
        resp = self.client.get(url, params, HTTP_AUTHORIZATION=auth)
        assert resp.status_code == 400
        assert "gitOrgName" in resp.data["detail"]

    @patch(
        "sentry.overwatch.endpoints.overwatch_rpc.settings.OVERWATCH_RPC_SHARED_SECRET",
        ["test-secret"],
    )
    def test_missing_provider_returns_400(self):
        """Test that missing provider parameter returns 400."""
        url = reverse("sentry-api-0-prevent-pr-review-configs-resolved")
        params = {"sentryOrgId": "123", "gitOrgName": "test-org"}
        auth = self._auth_header_for_get(url, params, "test-secret")
        resp = self.client.get(url, params, HTTP_AUTHORIZATION=auth)
        assert resp.status_code == 400
        assert "provider" in resp.data["detail"]

    @patch(
        "sentry.overwatch.endpoints.overwatch_rpc.settings.OVERWATCH_RPC_SHARED_SECRET",
        ["test-secret"],
    )
    def test_returns_default_when_no_config(self):
        """Test that default config is returned when no configuration exists."""
        org = self.create_organization()
        git_org_name = "test-github-org"

        with assume_test_silo_mode(SiloMode.CONTROL):
            self.create_integration(
                organization=org,
                provider="github",
                name=git_org_name,
                external_id=f"github:{git_org_name}",
                status=ObjectStatus.ACTIVE,
            )

        url = reverse("sentry-api-0-prevent-pr-review-configs-resolved")
        params = {
            "sentryOrgId": str(org.id),
            "gitOrgName": git_org_name,
            "provider": "github",
        }
        auth = self._auth_header_for_get(url, params, "test-secret")
        resp = self.client.get(url, params, HTTP_AUTHORIZATION=auth)
        assert resp.status_code == 200
        assert resp.data == PREVENT_AI_CONFIG_DEFAULT
        assert resp.data["organization"] == {}

    @patch(
        "sentry.overwatch.endpoints.overwatch_rpc.settings.OVERWATCH_RPC_SHARED_SECRET",
        ["test-secret"],
    )
    def test_returns_config_when_exists(self):
        """Test that saved configuration is returned when it exists."""
        org = self.create_organization()
        git_org_name = "test-github-org"

        with assume_test_silo_mode(SiloMode.CONTROL):
            integration = self.create_integration(
                organization=org,
                provider="github",
                name=git_org_name,
                external_id=f"github:{git_org_name}",
                status=ObjectStatus.ACTIVE,
            )

        PreventAIConfiguration.objects.create(
            organization_id=org.id,
            integration_id=integration.id,
            data=VALID_ORG_CONFIG,
        )

        url = reverse("sentry-api-0-prevent-pr-review-configs-resolved")
        params = {
            "sentryOrgId": str(org.id),
            "gitOrgName": git_org_name,
            "provider": "github",
        }
        auth = self._auth_header_for_get(url, params, "test-secret")
        resp = self.client.get(url, params, HTTP_AUTHORIZATION=auth)
        assert resp.status_code == 200
        assert resp.data["organization"][git_org_name] == VALID_ORG_CONFIG

    @patch(
        "sentry.overwatch.endpoints.overwatch_rpc.settings.OVERWATCH_RPC_SHARED_SECRET",
        ["test-secret"],
    )
    def test_returns_404_when_integration_not_found(self):
        """Test that 404 is returned when GitHub integration doesn't exist."""
        org = self.create_organization()

        url = reverse("sentry-api-0-prevent-pr-review-configs-resolved")
        params = {
            "sentryOrgId": str(org.id),
            "gitOrgName": "nonexistent-org",
            "provider": "github",
        }
        auth = self._auth_header_for_get(url, params, "test-secret")
        resp = self.client.get(url, params, HTTP_AUTHORIZATION=auth)
        assert resp.status_code == 404
        assert resp.data["detail"] == "GitHub integration not found"

    @patch(
        "sentry.overwatch.endpoints.overwatch_rpc.settings.OVERWATCH_RPC_SHARED_SECRET",
        ["test-secret"],
    )
    def test_config_with_repo_overrides(self):
        """Test that configuration with repo overrides is properly retrieved."""
        org = self.create_organization()
        git_org_name = "test-github-org"

        with assume_test_silo_mode(SiloMode.CONTROL):
            integration = self.create_integration(
                organization=org,
                provider="github",
                name=git_org_name,
                external_id=f"github:{git_org_name}",
                status=ObjectStatus.ACTIVE,
            )

        config_with_overrides = deepcopy(VALID_ORG_CONFIG)
        config_with_overrides["repo_overrides"] = {
            "my-repo": {
                "bug_prediction": {
                    "enabled": True,
                    "sensitivity": "high",
                    "triggers": {"on_command_phrase": True, "on_ready_for_review": False},
                },
                "test_generation": {
                    "enabled": True,
                    "triggers": {"on_command_phrase": True, "on_ready_for_review": True},
                },
                "vanilla": {
                    "enabled": False,
                    "sensitivity": "low",
                    "triggers": {"on_command_phrase": False, "on_ready_for_review": False},
                },
            }
        }

        PreventAIConfiguration.objects.create(
            organization_id=org.id,
            integration_id=integration.id,
            data=config_with_overrides,
        )

        url = reverse("sentry-api-0-prevent-pr-review-configs-resolved")
        params = {
            "sentryOrgId": str(org.id),
            "gitOrgName": git_org_name,
            "provider": "github",
        }
        auth = self._auth_header_for_get(url, params, "test-secret")
        resp = self.client.get(url, params, HTTP_AUTHORIZATION=auth)
        assert resp.status_code == 200
        assert (
            resp.data["organization"][git_org_name]["repo_overrides"]["my-repo"]["bug_prediction"][
                "sensitivity"
            ]
            == "high"
        )


class TestPreventPrReviewSentryOrgEndpoint(APITestCase):
    def _auth_header_for_get(self, url: str, params: dict[str, str], secret: str) -> str:
        message = b"[]"
        signature = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
        return f"Rpcsignature rpc0:{signature}"

    @patch(
        "sentry.overwatch.endpoints.overwatch_rpc.settings.OVERWATCH_RPC_SHARED_SECRET",
        ["test-secret"],
    )
    def test_requires_auth(self):
        url = reverse("sentry-api-0-prevent-pr-review-github-sentry-org")
        resp = self.client.get(url, {"repoId": "456"})
        assert resp.status_code == 403

    @patch(
        "sentry.overwatch.endpoints.overwatch_rpc.settings.OVERWATCH_RPC_SHARED_SECRET",
        ["test-secret"],
    )
    def test_missing_required_params_returns_400(self):
        url = reverse("sentry-api-0-prevent-pr-review-github-sentry-org")
        auth = self._auth_header_for_get(url, {}, "test-secret")

        resp = self.client.get(url, HTTP_AUTHORIZATION=auth)
        assert resp.status_code == 400

    @patch(
        "sentry.overwatch.endpoints.overwatch_rpc.settings.OVERWATCH_RPC_SHARED_SECRET",
        ["test-secret"],
    )
    def test_returns_empty_list_when_no_repos_found(self):
        url = reverse("sentry-api-0-prevent-pr-review-github-sentry-org")
        params = {"repoId": "456"}
        auth = self._auth_header_for_get(url, params, "test-secret")

        resp = self.client.get(url, params, HTTP_AUTHORIZATION=auth)
        assert resp.status_code == 200
        assert resp.data == {"organizations": []}

    @patch(
        "sentry.overwatch.endpoints.overwatch_rpc.settings.OVERWATCH_RPC_SHARED_SECRET",
        ["test-secret"],
    )
    def test_returns_org_ids_with_consent(self):

        org_with_consent = self.create_organization()
        org_with_consent.update_option("sentry:hide_ai_features", False)
        org_with_consent.update_option("sentry:enable_pr_review_test_generation", True)

        org_without_consent = self.create_organization()
        org_without_consent.update_option("sentry:hide_ai_features", True)

        repo_id = "12345"
        project_with_consent = self.create_project(organization=org_with_consent)
        project_without_consent = self.create_project(organization=org_without_consent)

        self.create_repo(
            project=project_with_consent,
            external_id=repo_id,
            name="org/repo",
            provider="integrations:github",
        )
        self.create_repo(
            project=project_without_consent,
            external_id=repo_id,
            name="org/repo",
            provider="integrations:github",
        )

        url = reverse("sentry-api-0-prevent-pr-review-github-sentry-org")
        params = {"repoId": repo_id}
        auth = self._auth_header_for_get(url, params, "test-secret")

        resp = self.client.get(url, params, HTTP_AUTHORIZATION=auth)
        assert resp.status_code == 200
        # Should return both orgs with their consent status
        expected_orgs = [
            {
                "org_id": org_with_consent.id,
                "org_slug": org_with_consent.slug,
                "org_name": org_with_consent.name,
                "has_consent": True,
            },
            {
                "org_id": org_without_consent.id,
                "org_slug": org_without_consent.slug,
                "org_name": org_without_consent.name,
                "has_consent": False,
            },
        ]
        # Sort both lists by org_id to ensure consistent comparison
        expected_orgs = sorted(expected_orgs, key=lambda x: x["org_id"])
        actual_data = {
            "organizations": sorted(resp.data["organizations"], key=lambda x: x["org_id"])
        }
        assert actual_data == {"organizations": expected_orgs}

    @patch(
        "sentry.overwatch.endpoints.overwatch_rpc.settings.OVERWATCH_RPC_SHARED_SECRET",
        ["test-secret"],
    )
    def test_filters_inactive_repositories(self):
        org = self.create_organization()
        org.update_option("sentry:hide_ai_features", False)
        org.update_option("sentry:enable_pr_review_test_generation", True)

        repo_id = "12345"
        project = self.create_project(organization=org)

        # Note: create_repo doesn't support status parameter, so we need to update it after creation
        repo = self.create_repo(
            project=project,
            external_id=repo_id,
            name="org/repo",
            provider="integrations:github",
        )
        repo.status = ObjectStatus.DISABLED
        repo.save()

        url = reverse("sentry-api-0-prevent-pr-review-github-sentry-org")
        params = {"repoId": repo_id}
        auth = self._auth_header_for_get(url, params, "test-secret")

        resp = self.client.get(url, params, HTTP_AUTHORIZATION=auth)
        assert resp.status_code == 200
        # Should return empty list as the repository is inactive
        assert resp.data == {"organizations": []}
