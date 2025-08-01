import orjson
from django.urls import reverse

from sentry.sentry_apps.models.sentry_app import SentryApp
from sentry.testutils.cases import APITestCase
from sentry.testutils.silo import control_silo_test


def assert_response_json(response, data):
    """
    Normalizes unicode strings by encoding/decoding expected output
    """
    assert orjson.loads(response.content) == orjson.loads(orjson.dumps(data))


class OrganizationSentryAppsTest(APITestCase):
    def setUp(self) -> None:
        self.superuser = self.create_user(email="a@example.com", is_superuser=True)
        self.user = self.create_user(email="boop@example.com")
        self.org = self.create_organization(owner=self.user)
        self.super_org = self.create_organization(owner=self.superuser)
        self.published_app = self.create_sentry_app(
            name="Test", organization=self.super_org, published=True
        )
        self.unpublished_app = self.create_sentry_app(name="Testin", organization=self.org)
        self.url = reverse("sentry-api-0-organization-sentry-apps", args=[self.org.slug])


@control_silo_test
class GetOrganizationSentryAppsTest(OrganizationSentryAppsTest):
    def test_gets_all_apps_in_own_org(self) -> None:
        self.login_as(user=self.user)
        response = self.client.get(self.url, format="json")

        assert response.status_code == 200

        assert_response_json(
            response,
            [
                {
                    "name": self.unpublished_app.name,
                    "author": self.unpublished_app.author,
                    "slug": self.unpublished_app.slug,
                    "scopes": [],
                    "events": [],
                    "uuid": self.unpublished_app.uuid,
                    "status": self.unpublished_app.get_status_display(),
                    "webhookUrl": self.unpublished_app.webhook_url,
                    "redirectUrl": self.unpublished_app.redirect_url,
                    "isAlertable": self.unpublished_app.is_alertable,
                    "verifyInstall": self.unpublished_app.verify_install,
                    "clientId": self.unpublished_app.application.client_id,
                    "clientSecret": self.unpublished_app.application.client_secret,
                    "overview": self.unpublished_app.overview,
                    "allowedOrigins": [],
                    "schema": {},
                    "owner": {"id": self.org.id, "slug": self.org.slug},
                    "featureData": [
                        {
                            "featureId": 0,
                            "featureGate": "integrations-api",
                            "description": "Testin can **utilize the Sentry API** to pull data or update resources in Sentry (with permissions granted, of course).",
                        }
                    ],
                    "popularity": SentryApp._meta.get_field("popularity").default,
                    "avatars": [],
                    "metadata": {},
                }
            ],
        )

    def test_includes_internal_integrations(self) -> None:
        self.create_project(organization=self.org)
        internal_integration = self.create_internal_integration(organization=self.org)

        self.login_as(self.user)
        response = self.client.get(self.url, format="json")

        assert response.status_code == 200
        assert internal_integration.uuid in [a["uuid"] for a in response.data]

    def test_cannot_see_apps_in_other_orgs(self) -> None:
        self.login_as(user=self.user)
        url = reverse("sentry-api-0-organization-sentry-apps", args=[self.super_org.slug])
        response = self.client.get(url, format="json")

        assert response.status_code == 403

    def test_filter_for_internal(self) -> None:
        self.login_as(user=self.user)
        self.create_project(organization=self.org)
        internal_integration = self.create_internal_integration(organization=self.org)
        response = self.client.get(f"{self.url}?status=internal", format="json")
        assert len(response.data) == 1
        assert response.data[0]["uuid"] == internal_integration.uuid
