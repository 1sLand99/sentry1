from unittest import mock

import orjson
import responses
from requests.exceptions import ReadTimeout

from sentry.integrations.jira_server import JiraServerIntegrationProvider
from sentry.integrations.models.integration import Integration
from sentry.integrations.models.organization_integration import OrganizationIntegration
from sentry.testutils.cases import IntegrationTestCase
from sentry.testutils.silo import control_silo_test
from sentry.users.models.identity import Identity, IdentityProvider
from sentry.utils import jwt

from . import EXAMPLE_PRIVATE_KEY


@control_silo_test
class JiraServerInstallationTest(IntegrationTestCase):
    provider = JiraServerIntegrationProvider

    def test_config_view(self) -> None:
        resp = self.client.get(self.init_path)
        assert resp.status_code == 200

        resp = self.client.get(self.setup_path)
        assert resp.status_code == 200
        self.assertContains(resp, "Connect Sentry")
        self.assertContains(resp, "Submit</button>")

    @responses.activate
    def test_validate_url(self) -> None:
        # Start pipeline and go to setup page.
        self.client.get(self.setup_path)

        # Submit credentials
        data = {
            "url": "jira.example.com/",
            "verify_ssl": False,
            "consumer_key": "sentry-bot",
            "private_key": EXAMPLE_PRIVATE_KEY,
        }
        resp = self.client.post(self.setup_path, data=data)
        assert resp.status_code == 200
        self.assertContains(resp, "Enter a valid URL")

    @responses.activate
    def test_validate_private_key(self) -> None:
        responses.add(
            responses.POST,
            "https://jira.example.com/plugins/servlet/oauth/request-token",
            status=503,
        )

        # Start pipeline and go to setup page.
        self.client.get(self.setup_path)

        # Submit credentials
        data = {
            "url": "https://jira.example.com/",
            "verify_ssl": False,
            "consumer_key": "sentry-bot",
            "private_key": "hot-garbage",
        }
        resp = self.client.post(self.setup_path, data=data)
        assert resp.status_code == 200
        self.assertContains(
            resp, "Private key must be a valid SSH private key encoded in a PEM format."
        )

    @responses.activate
    def test_validate_consumer_key_length(self) -> None:
        # Start pipeline and go to setup page.
        self.client.get(self.setup_path)

        # Submit credentials
        data = {
            "url": "jira.example.com/",
            "verify_ssl": False,
            "consumer_key": "x" * 201,
            "private_key": EXAMPLE_PRIVATE_KEY,
        }
        resp = self.client.post(self.setup_path, data=data)
        assert resp.status_code == 200
        self.assertContains(resp, "Consumer key is limited to 200")

    @responses.activate
    def test_authentication_request_token_timeout(self) -> None:
        timeout = ReadTimeout("Read timed out. (read timeout=30)")
        responses.add(
            responses.POST,
            "https://jira.example.com/plugins/servlet/oauth/request-token",
            body=timeout,
        )

        # Start pipeline and go to setup page.
        self.client.get(self.setup_path)

        # Submit credentials
        data = {
            "url": "https://jira.example.com/",
            "verify_ssl": False,
            "consumer_key": "sentry-bot",
            "private_key": EXAMPLE_PRIVATE_KEY,
        }
        resp = self.client.post(self.setup_path, data=data)
        assert resp.status_code == 200
        self.assertContains(resp, "Setup Error")
        self.assertContains(resp, "request token from Jira")
        self.assertContains(resp, "Timed out")

    @responses.activate
    def test_authentication_request_token_fails(self) -> None:
        responses.add(
            responses.POST,
            "https://jira.example.com/plugins/servlet/oauth/request-token",
            status=503,
        )

        # Start pipeline and go to setup page.
        self.client.get(self.setup_path)

        # Submit credentials
        data = {
            "url": "https://jira.example.com/",
            "verify_ssl": False,
            "consumer_key": "sentry-bot",
            "private_key": EXAMPLE_PRIVATE_KEY,
        }
        resp = self.client.post(self.setup_path, data=data)
        assert resp.status_code == 200
        self.assertContains(resp, "Setup Error")
        self.assertContains(resp, "request token from Jira")

    @responses.activate
    @mock.patch("sentry.integrations.jira_server.integration.logger")
    def test_authentication_request_token_fails_with_no_oauth_token(
        self, logger: mock.MagicMock
    ) -> None:
        responses.add(
            responses.POST,
            "https://jira.example.com/plugins/servlet/oauth/request-token",
            status=200,
            body="no_token=oops&foo=bar",
        )
        self.client.get(self.setup_path)

        data = {
            "url": "https://jira.example.com/",
            "verify_ssl": False,
            "consumer_key": "sentry-bot",
            "private_key": EXAMPLE_PRIVATE_KEY,
        }
        resp = self.client.post(self.setup_path, data=data)
        assert resp.status_code == 200
        self.assertContains(resp, "Setup Error")
        self.assertContains(resp, "Missing oauth_token")

        assert logger.info.call_count == 1
        logger.info.assert_any_call(
            "identity.jira-server.oauth-token",
            extra={"url": "https://jira.example.com", "data_keys": ["no_token", "foo"]},
        )

    @responses.activate
    def test_authentication_request_token_redirect(self) -> None:
        responses.add(
            responses.POST,
            "https://jira.example.com/plugins/servlet/oauth/request-token",
            status=200,
            content_type="text/plain",
            body="oauth_token=abc123&oauth_token_secret=def456",
        )

        # Start pipeline
        self.client.get(self.init_path)

        # Submit credentials
        data = {
            "url": "https://jira.example.com/",
            "verify_ssl": False,
            "consumer_key": "sentry-bot",
            "private_key": EXAMPLE_PRIVATE_KEY,
        }
        resp = self.client.post(self.setup_path, data=data)
        assert resp.status_code == 302
        redirect = "https://jira.example.com/plugins/servlet/oauth/authorize?oauth_token=abc123"
        assert redirect == resp["Location"]

    @responses.activate
    def test_authentication_access_token_failure(self) -> None:
        responses.add(
            responses.POST,
            "https://jira.example.com/plugins/servlet/oauth/request-token",
            status=200,
            content_type="text/plain",
            body="oauth_token=abc123&oauth_token_secret=def456",
        )
        responses.add(
            responses.POST,
            "https://jira.example.com/plugins/servlet/oauth/access-token",
            status=500,
            content_type="text/plain",
            body="<html>it broke</html>",
        )

        # Get config page
        resp = self.client.get(self.init_path)
        assert resp.status_code == 200

        # Submit credentials
        data = {
            "url": "https://jira.example.com/",
            "verify_ssl": False,
            "consumer_key": "sentry-bot",
            "private_key": EXAMPLE_PRIVATE_KEY,
        }
        resp = self.client.post(self.setup_path, data=data)
        assert resp.status_code == 302
        assert resp["Location"]

        resp = self.client.get(self.setup_path + "?oauth_token=xyz789")
        assert resp.status_code == 200
        self.assertContains(resp, "Setup Error")
        self.assertContains(resp, "access token from Jira")

    def install_integration(self):
        # Get config page
        resp = self.client.get(self.setup_path)
        assert resp.status_code == 200

        # Submit credentials
        data = {
            "url": "https://jira.example.com/",
            "verify_ssl": False,
            "consumer_key": "sentry-bot",
            "private_key": EXAMPLE_PRIVATE_KEY,
        }
        resp = self.client.post(self.setup_path, data=data)
        assert resp.status_code == 302
        assert resp["Location"]

        resp = self.client.get(self.setup_path + "?oauth_token=xyz789")
        assert resp.status_code == 200

        return resp

    @responses.activate
    def test_authentication_verifier_expired(self) -> None:
        responses.add(
            responses.POST,
            "https://jira.example.com/plugins/servlet/oauth/request-token",
            status=200,
            content_type="text/plain",
            body="oauth_token=abc123&oauth_token_secret=def456",
        )
        responses.add(
            responses.POST,
            "https://jira.example.com/plugins/servlet/oauth/access-token",
            status=404,
            content_type="text/plain",
            body="oauth_error=token+expired",
        )

        # Try getting the token but it has expired for some reason,
        # perhaps a stale reload/history navigate.
        resp = self.install_integration()

        self.assertContains(resp, "Setup Error")
        self.assertContains(resp, "access token from Jira")

    @responses.activate
    def test_authentication_success(self) -> None:
        responses.add(
            responses.POST,
            "https://jira.example.com/plugins/servlet/oauth/request-token",
            status=200,
            content_type="text/plain",
            body="oauth_token=abc123&oauth_token_secret=def456",
        )
        responses.add(
            responses.POST,
            "https://jira.example.com/plugins/servlet/oauth/access-token",
            status=200,
            content_type="text/plain",
            body="oauth_token=valid-token&oauth_token_secret=valid-secret",
        )
        responses.add(
            responses.GET,
            "https://jira.example.com/rest/api/2/serverInfo",
            status=200,
            json={
                "baseUrl": "https://jira.example.com",
                "version": "9.9.9",
            },
        )
        responses.add(
            responses.POST,
            "https://jira.example.com/rest/webhooks/1.0/webhook",
            status=204,
            body="",
        )

        self.install_integration()

        integration = Integration.objects.get()
        assert integration.name == "sentry-bot"
        assert integration.metadata["domain_name"] == "jira.example.com"
        assert integration.metadata["base_url"] == "https://jira.example.com"
        assert integration.metadata["verify_ssl"] is False
        assert integration.metadata["webhook_secret"]

        org_integration = OrganizationIntegration.objects.get(
            integration=integration, organization_id=self.organization.id
        )
        assert org_integration.config == {}

        idp = IdentityProvider.objects.get(type="jira_server")
        identity = Identity.objects.get(
            idp=idp, user=self.user, external_id="jira.example.com:sentry-bot"
        )
        assert identity.data["consumer_key"] == "sentry-bot"
        assert identity.data["access_token"] == "valid-token"
        assert identity.data["access_token_secret"] == "valid-secret"
        assert identity.data["private_key"] == EXAMPLE_PRIVATE_KEY

    @responses.activate
    def test_setup_create_webhook(self) -> None:
        responses.add(
            responses.POST,
            "https://jira.example.com/plugins/servlet/oauth/request-token",
            status=200,
            content_type="text/plain",
            body="oauth_token=abc123&oauth_token_secret=def456",
        )
        responses.add(
            responses.POST,
            "https://jira.example.com/plugins/servlet/oauth/access-token",
            status=200,
            content_type="text/plain",
            body="oauth_token=valid-token&oauth_token_secret=valid-secret",
        )
        responses.add(
            responses.GET,
            "https://jira.example.com/rest/api/2/serverInfo",
            status=200,
            json={
                "baseUrl": "https://jira.example.com",
                "version": "9.9.9",
            },
        )
        expected_id = "jira.example.com:sentry-bot"

        def webhook_response(request):
            # Ensure the webhook token contains our integration
            # external id
            data = orjson.loads(request.body)
            url = data["url"]
            token = url.split("/")[-2]
            token_data = jwt.peek_claims(token)
            assert "id" in token_data
            assert token_data["id"] == expected_id

            return 204, {}, ""

        responses.add_callback(
            responses.POST,
            "https://jira.example.com/rest/webhooks/1.0/webhook",
            callback=webhook_response,
        )
        self.install_integration()

        integration = Integration.objects.get()
        assert integration.external_id == expected_id

    @responses.activate
    def test_setup_create_webhook_with_new_endpoint(self) -> None:
        responses.add(
            responses.POST,
            "https://jira.example.com/plugins/servlet/oauth/request-token",
            status=200,
            content_type="text/plain",
            body="oauth_token=abc123&oauth_token_secret=def456",
        )
        responses.add(
            responses.POST,
            "https://jira.example.com/plugins/servlet/oauth/access-token",
            status=200,
            content_type="text/plain",
            body="oauth_token=valid-token&oauth_token_secret=valid-secret",
        )
        responses.add(
            responses.GET,
            "https://jira.example.com/rest/api/2/serverInfo",
            status=200,
            json={
                "baseUrl": "https://jira.example.com",
                "version": "10.0.1",
            },
        )
        expected_id = "jira.example.com:sentry-bot"

        def webhook_response(request):
            # Ensure the webhook token contains our integration
            # external id
            data = orjson.loads(request.body)
            url = data["url"]
            token = url.split("/")[-2]
            token_data = jwt.peek_claims(token)
            assert "id" in token_data
            assert token_data["id"] == expected_id

            return 204, {}, ""

        responses.add_callback(
            responses.POST,
            "https://jira.example.com/rest/jira-webhook/1.0/webhooks",
            callback=webhook_response,
        )
        self.install_integration()

        integration = Integration.objects.get()
        assert integration.external_id == expected_id

    @responses.activate
    def test_setup_external_id_length(self) -> None:
        responses.add(
            responses.POST,
            "https://jira.example.com/plugins/servlet/oauth/request-token",
            status=200,
            content_type="text/plain",
            body="oauth_token=abc123&oauth_token_secret=def456",
        )
        responses.add(
            responses.POST,
            "https://jira.example.com/plugins/servlet/oauth/access-token",
            status=200,
            content_type="text/plain",
            body="oauth_token=valid-token&oauth_token_secret=valid-secret",
        )
        responses.add(
            responses.POST,
            "https://jira.example.com/rest/webhooks/1.0/webhook",
            status=204,
            body="",
        )
        responses.add(
            responses.GET,
            "https://jira.example.com/rest/api/2/serverInfo",
            status=200,
            json={
                "baseUrl": "https://jira.example.com",
                "version": "9.9.9",
            },
        )
        # Start pipeline and go to setup page.
        self.client.get(self.setup_path)

        # Submit credentials
        data = {
            "url": "https://jira.example.com/",
            "verify_ssl": False,
            "consumer_key": "a-very-long-consumer-key-that-when-combined-with-host-would-overflow",
            "private_key": EXAMPLE_PRIVATE_KEY,
        }
        resp = self.client.post(self.setup_path, data=data)
        assert resp.status_code == 302
        redirect = "https://jira.example.com/plugins/servlet/oauth/authorize?oauth_token=abc123"
        assert redirect == resp["Location"]

        resp = self.client.get(self.setup_path + "?oauth_token=xyz789")
        assert resp.status_code == 200

        integration = Integration.objects.get(provider="jira_server")
        assert (
            integration.external_id
            == "jira.example.com:a-very-long-consumer-key-that-when-combined-wit"
        )

    @responses.activate
    def test_setup_create_webhook_failure(self) -> None:
        responses.add(
            responses.POST,
            "https://jira.example.com/plugins/servlet/oauth/request-token",
            status=200,
            content_type="text/plain",
            body="oauth_token=abc123&oauth_token_secret=def456",
        )
        responses.add(
            responses.POST,
            "https://jira.example.com/plugins/servlet/oauth/access-token",
            status=200,
            content_type="text/plain",
            body="oauth_token=valid-token&oauth_token_secret=valid-secret",
        )
        responses.add(
            responses.POST,
            "https://jira.example.com/rest/webhooks/1.0/webhook",
            status=502,
            body="Bad things",
        )
        responses.add(
            responses.GET,
            "https://jira.example.com/rest/api/2/serverInfo",
            status=200,
            json={
                "baseUrl": "https://jira.example.com",
                "version": "9.9.9",
            },
        )
        resp = self.install_integration()
        self.assertContains(resp, "webhook")

        assert Integration.objects.count() == 0

    @responses.activate
    def test_setup_create_webhook_failure_forbidden(self) -> None:
        responses.add(
            responses.POST,
            "https://jira.example.com/plugins/servlet/oauth/request-token",
            status=200,
            content_type="text/plain",
            body="oauth_token=abc123&oauth_token_secret=def456",
        )
        responses.add(
            responses.POST,
            "https://jira.example.com/plugins/servlet/oauth/access-token",
            status=200,
            content_type="text/plain",
            body="oauth_token=valid-token&oauth_token_secret=valid-secret",
        )
        responses.add(
            responses.POST,
            "https://jira.example.com/rest/webhooks/1.0/webhook",
            status=403,
            json={
                "messages": [
                    {"key": "You do not have permission to create WebHook 'Sentry Issue Sync'."}
                ]
            },
        )
        responses.add(
            responses.GET,
            "https://jira.example.com/rest/api/2/serverInfo",
            status=200,
            json={
                "baseUrl": "https://jira.example.com",
                "version": "9.9.9",
            },
        )

        resp = self.install_integration()
        self.assertContains(resp, "You do not have permission to create")
        self.assertContains(resp, "Could not create issue webhook")

        assert Integration.objects.count() == 0
