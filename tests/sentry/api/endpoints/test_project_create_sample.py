import orjson
from django.urls import reverse

from sentry.models.groupinbox import GroupInbox
from sentry.testutils.cases import APITestCase
from sentry.testutils.skips import requires_snuba

pytestmark = [requires_snuba]


class ProjectCreateSampleTest(APITestCase):
    def setUp(self) -> None:
        self.login_as(user=self.user)
        self.team = self.create_team()

    def test_simple(self) -> None:
        project = self.create_project(teams=[self.team], name="foo")

        url = reverse(
            "sentry-api-0-project-create-sample",
            kwargs={
                "organization_id_or_slug": project.organization.slug,
                "project_id_or_slug": project.slug,
            },
        )
        response = self.client.post(url, format="json")

        assert response.status_code == 200, response.content
        assert "groupID" in orjson.loads(response.content)
        assert GroupInbox.objects.filter(group=response.data["groupID"]).exists()

    def test_project_platform(self) -> None:
        project = self.create_project(teams=[self.team], name="foo", platform="javascript-react")

        url = reverse(
            "sentry-api-0-project-create-sample",
            kwargs={
                "organization_id_or_slug": project.organization.slug,
                "project_id_or_slug": project.slug,
            },
        )
        response = self.client.post(url, format="json")

        assert response.status_code == 200, response.content
        assert "groupID" in orjson.loads(response.content)

    def test_cocoa(self) -> None:
        project = self.create_project(teams=[self.team], name="foo", platform="cocoa")

        url = reverse(
            "sentry-api-0-project-create-sample",
            kwargs={
                "organization_id_or_slug": project.organization.slug,
                "project_id_or_slug": project.slug,
            },
        )
        response = self.client.post(url, format="json")

        assert response.status_code == 200, response.content
        assert "groupID" in orjson.loads(response.content)

    def test_java(self) -> None:
        project = self.create_project(teams=[self.team], name="foo", platform="java")

        url = reverse(
            "sentry-api-0-project-create-sample",
            kwargs={
                "organization_id_or_slug": project.organization.slug,
                "project_id_or_slug": project.slug,
            },
        )
        response = self.client.post(url, format="json")

        assert response.status_code == 200, response.content
        assert "groupID" in orjson.loads(response.content)

    def test_javascript(self) -> None:
        project = self.create_project(teams=[self.team], name="foo", platform="javascript")

        url = reverse(
            "sentry-api-0-project-create-sample",
            kwargs={
                "organization_id_or_slug": project.organization.slug,
                "project_id_or_slug": project.slug,
            },
        )
        response = self.client.post(url, format="json")

        assert response.status_code == 200, response.content
        assert "groupID" in orjson.loads(response.content)

    def test_php(self) -> None:
        project = self.create_project(teams=[self.team], name="foo", platform="php")

        url = reverse(
            "sentry-api-0-project-create-sample",
            kwargs={
                "organization_id_or_slug": project.organization.slug,
                "project_id_or_slug": project.slug,
            },
        )
        response = self.client.post(url, format="json")

        assert response.status_code == 200, response.content
        assert "groupID" in orjson.loads(response.content)

    def test_python(self) -> None:
        project = self.create_project(teams=[self.team], name="foo", platform="python")

        url = reverse(
            "sentry-api-0-project-create-sample",
            kwargs={
                "organization_id_or_slug": project.organization.slug,
                "project_id_or_slug": project.slug,
            },
        )
        response = self.client.post(url, format="json")

        assert response.status_code == 200, response.content
        assert "groupID" in orjson.loads(response.content)

    def test_reactnative(self) -> None:
        project = self.create_project(teams=[self.team], name="foo", platform="react-native")

        url = reverse(
            "sentry-api-0-project-create-sample",
            kwargs={
                "organization_id_or_slug": project.organization.slug,
                "project_id_or_slug": project.slug,
            },
        )
        response = self.client.post(url, format="json")

        assert response.status_code == 200, response.content
        assert "groupID" in orjson.loads(response.content)

    def test_ruby(self) -> None:
        project = self.create_project(teams=[self.team], name="foo", platform="ruby")

        url = reverse(
            "sentry-api-0-project-create-sample",
            kwargs={
                "organization_id_or_slug": project.organization.slug,
                "project_id_or_slug": project.slug,
            },
        )
        response = self.client.post(url, format="json")

        assert response.status_code == 200, response.content
        assert "groupID" in orjson.loads(response.content)

    def test_attempted_path_traversal_returns_400(self) -> None:
        project = self.create_project(teams=[self.team], name="foo", platform="../../../etc/passwd")

        url = reverse(
            "sentry-api-0-project-create-sample",
            kwargs={
                "organization_id_or_slug": project.organization.slug,
                "project_id_or_slug": project.slug,
            },
        )

        response = self.client.post(url, format="json")
        assert response.status_code == 400
