from django.test.client import RequestFactory
from django.urls import reverse

from fixtures.apidocs_test_case import APIDocsTestCase
from sentry.sentry_apps.models.sentry_app_installation import SentryAppInstallation
from sentry.silo.base import SiloMode
from sentry.testutils.silo import assume_test_silo_mode


class SentryAppDocsTest(APIDocsTestCase):
    def setUp(self):
        self.org = self.create_organization(owner=self.user, name="Rowdy Tiger")
        self.project = self.create_project(organization=self.org)
        self.group = self.create_group(project=self.project)
        self.sentry_app = self.create_sentry_app(
            name="Hellboy App", published=True, organization=self.org
        )
        with assume_test_silo_mode(SiloMode.CONTROL):
            self.install = SentryAppInstallation(
                sentry_app=self.sentry_app, organization_id=self.org.id
            )
            self.install.save()
        self.url = reverse(
            "sentry-api-0-sentry-app-installation-external-issues",
            kwargs={"uuid": self.install.uuid},
        )

        self.login_as(user=self.user)

    def test_post(self) -> None:
        data = {
            "issueId": self.group.id,
            "webUrl": "https://somerandom.io/project/issue-id",
            "project": "ExternalProj",
            "identifier": "issue-1",
        }
        response = self.client.post(self.url, data)
        request = RequestFactory().post(self.url, data)

        self.validate_schema(request, response)
