from sentry.integrations.models.external_actor import ExternalActor
from sentry.integrations.utils.providers import get_provider_string
from sentry.testutils.cases import APITestCase


class ExternalTeamTest(APITestCase):
    endpoint = "sentry-api-0-external-team"
    method = "post"

    def setUp(self) -> None:
        super().setUp()
        self.login_as(self.user)
        self.integration = self.create_integration(
            organization=self.organization, provider="github", name="GitHub", external_id="github:1"
        )
        self.slack_integration = self.create_integration(
            organization=self.organization, provider="slack", name="Slack", external_id="slack:2"
        )

    def test_basic_post(self) -> None:
        data = {
            "externalName": "@getsentry/ecosystem",
            "provider": "github",
            "integrationId": self.integration.id,
        }
        with self.feature({"organizations:integrations-codeowners": True}):
            response = self.get_success_response(
                self.organization.slug, self.team.slug, status_code=201, **data
            )
        assert response.data == {
            **data,
            "id": str(response.data["id"]),
            "teamId": str(self.team.id),
            "integrationId": str(self.integration.id),
        }

    def test_ignore_camelcase_teamid(self) -> None:
        other_team = self.create_team(organization=self.organization)
        data = {
            "externalName": "@getsentry/ecosystem",
            "provider": "github",
            "integrationId": self.integration.id,
            "teamId": other_team.id,
        }
        with self.feature({"organizations:integrations-codeowners": True}):
            response = self.get_success_response(
                self.organization.slug, self.team.slug, status_code=201, **data
            )
        assert response.data == {
            **data,
            "id": str(response.data["id"]),
            "teamId": str(self.team.id),
            "integrationId": str(self.integration.id),
        }

    def test_without_feature_flag(self) -> None:
        data = {
            "externalName": "@getsentry/ecosystem",
            "provider": "github",
            "integrationId": self.integration.id,
        }
        with self.feature({"organizations:integrations-codeowners": False}):
            response = self.get_error_response(
                self.organization.slug, self.team.slug, status_code=403, **data
            )
        assert response.data == {"detail": "You do not have permission to perform this action."}

    def test_missing_provider(self) -> None:
        data = {
            "externalName": "@getsentry/ecosystem",
            "integrationId": self.integration.id,
        }
        with self.feature({"organizations:integrations-codeowners": True}):
            response = self.get_error_response(
                self.organization.slug, self.team.slug, status_code=400, **data
            )
        assert response.data == {"provider": ["This field is required."]}

    def test_missing_externalName(self) -> None:
        data = {
            "provider": "github",
            "integrationId": self.integration.id,
        }
        with self.feature({"organizations:integrations-codeowners": True}):
            response = self.get_error_response(
                self.organization.slug, self.team.slug, status_code=400, **data
            )
        assert response.data == {"externalName": ["This field is required."]}

    def test_missing_integrationId(self) -> None:
        data = {
            "externalName": "@getsentry/ecosystem",
            "provider": "github",
        }
        with self.feature({"organizations:integrations-codeowners": True}):
            response = self.get_error_response(
                self.organization.slug, self.team.slug, status_code=400, **data
            )
        assert response.data == {"integrationId": ["This field is required."]}

    def test_invalid_provider(self) -> None:
        data = {
            "externalName": "@getsentry/ecosystem",
            "provider": "git",
            "integrationId": self.integration.id,
        }
        with self.feature({"organizations:integrations-codeowners": True}):
            response = self.get_error_response(
                self.organization.slug, self.team.slug, status_code=400, **data
            )
        assert response.data == {"provider": ['"git" is not a valid choice.']}

    def test_create_existing_association(self) -> None:
        self.external_team = self.create_external_team(
            self.team, external_name="@getsentry/ecosystem", integration=self.integration
        )

        data = {
            "externalName": self.external_team.external_name,
            "provider": get_provider_string(self.external_team.provider),
            "integrationId": self.integration.id,
        }
        with self.feature({"organizations:integrations-codeowners": True}):
            response = self.get_success_response(
                self.organization.slug, self.team.slug, status_code=200, **data
            )
        assert response.data == {
            **data,
            "id": str(self.external_team.id),
            "teamId": str(self.team.id),
            "integrationId": str(self.integration.id),
        }

    def test_create_with_invalid_integration_id(self) -> None:
        self.org2 = self.create_organization(owner=self.user, name="org2")
        self.integration = self.create_integration(
            organization=self.org2, provider="gitlab", name="Gitlab", external_id="gitlab:1"
        )

        data = {
            "externalName": "@getsentry/ecosystem",
            "provider": "github",
            "integrationId": self.integration.id,
        }
        with self.feature({"organizations:integrations-codeowners": True}):
            response = self.get_error_response(
                self.organization.slug, self.team.slug, status_code=400, **data
            )
        assert response.data == {
            "integrationId": ["Integration does not exist for this organization"]
        }

    def test_create_with_external_id(self) -> None:
        data = {
            "externalId": "YU287RFO30",
            "externalName": "@getsentry/ecosystem",
            "provider": "slack",
            "integrationId": self.slack_integration.id,
        }
        with self.feature({"organizations:integrations-codeowners": True}):
            response = self.get_success_response(self.organization.slug, self.team.slug, **data)
        assert response.data == {
            **data,
            "id": str(response.data["id"]),
            "teamId": str(self.team.id),
            "integrationId": str(self.slack_integration.id),
        }
        assert ExternalActor.objects.get(id=response.data["id"]).external_id == "YU287RFO30"

    def test_create_with_invalid_external_id(self) -> None:
        data = {
            "externalId": "",
            "externalName": "@getsentry/ecosystem",
            "provider": "slack",
            "integrationId": self.slack_integration.id,
        }
        with self.feature({"organizations:integrations-codeowners": True}):
            self.get_error_response(self.organization.slug, self.team.slug, **data)
