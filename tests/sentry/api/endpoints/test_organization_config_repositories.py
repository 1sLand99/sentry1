from django.urls import reverse

from sentry.testutils.cases import APITestCase


class OrganizationConfigRepositoriesTest(APITestCase):
    def test_simple(self) -> None:
        self.login_as(user=self.user)

        org = self.create_organization(owner=self.user, name="baz")

        url = reverse("sentry-api-0-organization-config-repositories", args=[org.slug])
        response = self.client.get(url, format="json")

        assert response.status_code == 200, response.content
        provider = list(filter(lambda x: x["id"] == "dummy", response.data["providers"]))[0]
        assert provider["name"] == "Example"
        assert provider["config"]
