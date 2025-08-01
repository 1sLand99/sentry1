from sentry.integrations.types import ExternalProviders
from sentry.models.organizationmember import OrganizationMember
from sentry.notifications.notifications.organization_request import OrganizationRequestNotification
from sentry.notifications.notifications.strategies.role_based_recipient_strategy import (
    RoleBasedRecipientStrategy,
)
from sentry.testutils.cases import TestCase
from sentry.types.actor import Actor


class DummyRoleBasedRecipientStrategy(RoleBasedRecipientStrategy):
    def determine_member_recipients(self):
        return OrganizationMember.objects.filter(organization=self.organization)


class DummyRequestNotification(OrganizationRequestNotification):
    metrics_key = "dummy"
    template_path = ""
    RoleBasedRecipientStrategyClass = DummyRoleBasedRecipientStrategy


class GetParticipantsTest(TestCase):
    def setUp(self) -> None:
        self.user2 = self.create_user()
        self.create_member(user=self.user2, organization=self.organization)
        self.user_actors = {Actor.from_orm_user(user) for user in (self.user, self.user2)}

    def test_default_to_slack(self) -> None:
        notification = DummyRequestNotification(self.organization, self.user)

        assert notification.get_participants() == {
            ExternalProviders.EMAIL: self.user_actors,
            ExternalProviders.SLACK: self.user_actors,
        }

    def test_turn_off_settings(self) -> None:
        notification = DummyRequestNotification(self.organization, self.user)

        assert notification.get_participants() == {
            ExternalProviders.EMAIL: self.user_actors,
            ExternalProviders.SLACK: self.user_actors,
        }
