import time
from unittest.mock import MagicMock, patch

import orjson
import responses

from sentry.integrations.msteams.link_identity import build_linking_url
from sentry.testutils.cases import TestCase
from sentry.testutils.silo import control_silo_test
from sentry.users.models.identity import Identity, IdentityStatus


@control_silo_test
class MsTeamsIntegrationLinkIdentityTest(TestCase):
    def setUp(self) -> None:
        super(TestCase, self).setUp()
        self.user1 = self.create_user(is_superuser=False)
        self.user2 = self.create_user(is_superuser=False)
        self.org = self.create_organization(owner=None)
        self.create_member(user=self.user1, organization=self.org)
        self.create_member(user=self.user2, organization=self.org)
        self.team = self.create_team(organization=self.org, members=[self.user1, self.user2])

        self.login_as(self.user1)

        self.integration = self.create_provider_integration(
            provider="msteams",
            name="Hogwarts",
            external_id="1_50l3mnly_5w34r",
            metadata={
                "service_url": "https://smba.trafficmanager.net/amer",
                "access_token": "3ld3rw4nd",
                "expires_at": int(time.time()) + 86400,
            },
        )
        self.create_organization_integration(
            organization_id=self.org.id, integration=self.integration
        )

        self.idp = self.create_identity_provider(type="msteams", external_id="1_50l3mnly_5w34r")

    @responses.activate
    @patch("sentry.integrations.messaging.linkage.unsign")
    def test_basic_flow(self, unsign: MagicMock) -> None:
        unsign.return_value = {
            "integration_id": self.integration.id,
            "organization_id": self.org.id,
            "teams_user_id": "a_p_w_b_d",
            "team_id": "1_50l3mnly_5w34r",
            "tenant_id": "h0g5m34d3",
        }

        linking_url = build_linking_url(
            self.integration,
            self.org,
            "a_p_w_b_d",
            "1_50l3mnly_5w34r",
            "h0g5m34d3",
        )

        resp = self.client.get(linking_url)

        assert resp.status_code == 200
        self.assertTemplateUsed(resp, "sentry/auth-link-identity.html")

        def user_conversation_id_callback(request):
            payload = orjson.loads(request.body)
            if payload["members"] == [{"id": "a_p_w_b_d"}] and payload["channelData"] == {
                "tenant": {"id": "h0g5m34d3"}
            }:
                return 200, {}, orjson.dumps({"id": "dumbl3d0r3"}).decode()

        responses.add_callback(
            method=responses.POST,
            url="https://smba.trafficmanager.net/amer/v3/conversations",
            callback=user_conversation_id_callback,
        )

        responses.add(
            method=responses.POST,
            url="https://smba.trafficmanager.net/amer/v3/conversations/dumbl3d0r3/activities",
            status=200,
            json={},
        )

        resp = self.client.post(linking_url)

        identity = Identity.objects.filter(external_id="a_p_w_b_d", user=self.user1)

        assert len(identity) == 1
        assert identity[0].idp == self.idp
        assert identity[0].status == IdentityStatus.VALID
        assert len(responses.calls) == 2

    @responses.activate
    @patch("sentry.integrations.messaging.linkage.unsign")
    def test_overwrites_existing_identities(self, unsign: MagicMock) -> None:
        Identity.objects.create(
            user=self.user1, idp=self.idp, external_id="h_p", status=IdentityStatus.VALID
        )
        Identity.objects.create(
            user=self.user2, idp=self.idp, external_id="g_w", status=IdentityStatus.VALID
        )

        unsign.return_value = {
            "integration_id": self.integration.id,
            "organization_id": self.org.id,
            "teams_user_id": "g_w",
            "team_id": "1_50l3mnly_5w34r",
            "tenant_id": "th3_burr0w",
        }

        linking_url = build_linking_url(
            self.integration,
            self.org,
            "g_w",
            "1_50l3mnly_5w34r",
            "th3_burr0w",
        )

        def user_conversation_id_callback(request):
            payload = orjson.loads(request.body)
            if payload["members"] == [{"id": "g_w"}] and payload["channelData"] == {
                "tenant": {"id": "th3_burr0w"}
            }:
                return 200, {}, orjson.dumps({"id": "g1nny_w345l3y"}).decode()
            return 404, {}, orjson.dumps({}).decode()

        responses.add_callback(
            method=responses.POST,
            url="https://smba.trafficmanager.net/amer/v3/conversations",
            callback=user_conversation_id_callback,
        )

        responses.add(
            method=responses.POST,
            url="https://smba.trafficmanager.net/amer/v3/conversations/g1nny_w345l3y/activities",
            status=200,
            json={},
        )

        self.client.post(linking_url)

        Identity.objects.get(external_id="g_w", user=self.user1)
        assert not Identity.objects.filter(external_id="h_p", user=self.user1).exists()
        assert not Identity.objects.filter(external_id="g_w", user=self.user2).exists()
