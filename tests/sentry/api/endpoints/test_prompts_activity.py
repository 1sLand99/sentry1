from django.urls import reverse

from sentry.testutils.cases import APITestCase


class PromptsActivityTest(APITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.login_as(user=self.user)
        self.org = self.create_organization(owner=self.user, name="baz")
        self.team = self.create_team(organization=self.org, name="Mariachi Band")
        self.project = self.create_project(
            organization=self.org, teams=[self.team], name="Bengal-Elephant-Giraffe-Tree-House"
        )
        self.path = reverse("sentry-api-0-organization-prompts-activity", args=[self.org.slug])

    def test_invalid_feature(self) -> None:
        # Invalid feature prompt name
        resp = self.client.put(
            self.path,
            {
                "organization_id": self.org.id,
                "project_id": self.project.id,
                "feature": "gibberish",
                "status": "dismissed",
            },
        )

        assert resp.status_code == 400

    def test_batched_invalid_feature(self) -> None:
        # Invalid feature prompt name
        resp = self.client.put(
            self.path,
            {
                "organization_id": self.org.id,
                "project_id": self.project.id,
                "feature": ["releases", "gibberish"],
                "status": "dismissed",
            },
        )

        assert resp.status_code == 400

    def test_invalid_project(self) -> None:
        # Invalid project id
        data = {
            "organization_id": self.org.id,
            "project_id": self.project.id,
            "feature": "releases",
        }
        resp = self.client.get(self.path, data)
        assert resp.status_code == 200
        self.project.delete()
        # project doesn't exist
        resp = self.client.put(
            self.path,
            {
                "organization_id": self.org.id,
                "project_id": self.project.id,
                "feature": "releases",
                "status": "dismissed",
            },
        )
        assert resp.status_code == 400

    def test_dismiss(self) -> None:
        data = {
            "organization_id": self.org.id,
            "project_id": self.project.id,
            "feature": "releases",
        }
        resp = self.client.get(self.path, data)
        assert resp.status_code == 200
        assert resp.data.get("data", None) is None

        self.client.put(
            self.path,
            {
                "organization_id": self.org.id,
                "project_id": self.project.id,
                "feature": "releases",
                "status": "dismissed",
            },
        )

        resp = self.client.get(self.path, data)
        assert resp.status_code == 200
        assert "data" in resp.data
        assert "dismissed_ts" in resp.data["data"]

    def test_dismiss_legacy_path(self) -> None:
        self.path = reverse("sentry-api-0-prompts-activity")
        self.test_dismiss()

    def test_snooze(self) -> None:
        data = {
            "organization_id": self.org.id,
            "project_id": self.project.id,
            "feature": "releases",
        }
        resp = self.client.get(self.path, data)
        assert resp.status_code == 200
        assert resp.data.get("data", None) is None

        self.client.put(
            self.path,
            {
                "organization_id": self.org.id,
                "project_id": self.project.id,
                "feature": "releases",
                "status": "snoozed",
            },
        )

        resp = self.client.get(self.path, data)

        assert resp.status_code == 200
        assert "data" in resp.data
        assert "snoozed_ts" in resp.data["data"]

    def test_snooze_legacy_path(self) -> None:
        self.path = reverse("sentry-api-0-prompts-activity")
        self.test_snooze()

    def test_visible(self) -> None:
        data = {
            "organization_id": self.org.id,
            "project_id": self.project.id,
            "feature": "releases",
        }
        resp = self.client.get(self.path, data)
        assert resp.status_code == 200
        assert resp.data.get("data", None) is None

        self.client.put(
            self.path,
            {
                "organization_id": self.org.id,
                "project_id": self.project.id,
                "feature": "releases",
                "status": "visible",
            },
        )

        resp = self.client.get(self.path, data)
        assert resp.status_code == 200
        assert "data" in resp.data
        assert resp.data["data"].get("dismissed_ts") is None
        assert resp.data["data"].get("snoozed_ts") is None

    def test_visible_legacy_path(self) -> None:
        self.path = reverse("sentry-api-0-prompts-activity")
        self.test_visible()

    def test_visible_after_dismiss(self) -> None:
        data = {
            "organization_id": self.org.id,
            "project_id": self.project.id,
            "feature": "releases",
        }
        resp = self.client.get(self.path, data)
        assert resp.status_code == 200
        assert resp.data.get("data", None) is None

        self.client.put(
            self.path,
            {
                "organization_id": self.org.id,
                "project_id": self.project.id,
                "feature": "releases",
                "status": "dismiss",
            },
        )

        self.client.put(
            self.path,
            {
                "organization_id": self.org.id,
                "project_id": self.project.id,
                "feature": "releases",
                "status": "visible",
            },
        )

        resp = self.client.get(self.path, data)
        assert resp.status_code == 200
        assert "data" in resp.data
        assert resp.data["data"].get("dismissed_ts") is None
        assert resp.data["data"].get("snoozed_ts") is None

    def test_batched(self) -> None:
        data = {
            "organization_id": self.org.id,
            "project_id": self.project.id,
            "feature": ["releases", "alert_stream"],
        }
        resp = self.client.get(self.path, data)
        assert resp.status_code == 200
        assert resp.data["features"].get("releases", None) is None
        assert resp.data["features"].get("alert_stream", None) is None

        self.client.put(
            self.path,
            {
                "organization_id": self.org.id,
                "project_id": self.project.id,
                "feature": "releases",
                "status": "dismissed",
            },
        )

        resp = self.client.get(self.path, data)
        assert resp.status_code == 200
        assert "dismissed_ts" in resp.data["features"]["releases"]
        assert resp.data["features"].get("alert_stream", None) is None

        self.client.put(
            self.path,
            {
                "organization_id": self.org.id,
                "project_id": self.project.id,
                "feature": "alert_stream",
                "status": "snoozed",
            },
        )

        resp = self.client.get(self.path, data)
        assert resp.status_code == 200
        assert "dismissed_ts" in resp.data["features"]["releases"]
        assert "snoozed_ts" in resp.data["features"]["alert_stream"]
