from datetime import UTC, datetime, timedelta
from typing import cast
from unittest import mock
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.db import DEFAULT_DB_ALIAS, connections
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from sentry import buffer
from sentry.constants import ObjectStatus
from sentry.models.group import Group, GroupStatus
from sentry.models.grouprulestatus import GroupRuleStatus
from sentry.models.project import Project
from sentry.models.projectownership import ProjectOwnership
from sentry.models.rule import Rule
from sentry.models.rulefirehistory import RuleFireHistory
from sentry.notifications.types import ActionTargetType
from sentry.rules import init_registry
from sentry.rules.conditions import EventCondition
from sentry.rules.filters.base import EventFilter
from sentry.rules.processing.processor import PROJECT_ID_BUFFER_LIST_KEY, RuleProcessor
from sentry.testutils.cases import PerformanceIssueTestCase, TestCase
from sentry.testutils.helpers import install_slack
from sentry.testutils.helpers.redis import mock_redis_buffer
from sentry.testutils.skips import requires_snuba
from sentry.utils import json

pytestmark = [requires_snuba]

EMAIL_ACTION_DATA = {
    "id": "sentry.mail.actions.NotifyEmailAction",
    "targetType": ActionTargetType.ISSUE_OWNERS.value,
    "targetIdentifier": None,
}

EVERY_EVENT_COND_DATA = {"id": "sentry.rules.conditions.every_event.EveryEventCondition"}
ESCALATING_EVENT_COND_DATA = {
    "id": "sentry.rules.conditions.reappeared_event.ReappearedEventCondition"
}


class MockConditionTrue(EventCondition):
    id = "tests.sentry.rules.processing.test_processor.MockConditionTrue"
    label = "Mock condition which always passes."

    def passes(self, event, state):
        return True


@mock_redis_buffer()
class RuleProcessorTest(TestCase, PerformanceIssueTestCase):
    def setUp(self) -> None:
        event = self.store_event(data={}, project_id=self.project.id)
        self.group_event = event.for_group(cast(Group, event.group))

        Rule.objects.filter(project=self.group_event.project).delete()
        ProjectOwnership.objects.create(project_id=self.project.id, fallthrough=True)
        self.rule = Rule.objects.create(
            project=self.group_event.project,
            data={"conditions": [EVERY_EVENT_COND_DATA], "actions": [EMAIL_ACTION_DATA]},
        )
        self.user_count_condition = {
            "interval": "1h",
            "id": "sentry.rules.conditions.event_frequency.EventUniqueUserFrequencyCondition",
            "value": 100,
        }
        self.event_frequency_condition = {
            "id": "sentry.rules.conditions.event_frequency.EventFrequencyCondition",
            "interval": "1h",
            "value": 1,
        }

    # this test relies on a few other tests passing
    def test_integrated(self) -> None:
        rp = RuleProcessor(
            self.group_event,
            is_new=True,
            is_regression=True,
            is_new_group_environment=True,
            has_reappeared=True,
        )
        results = list(rp.apply())
        assert len(results) == 1
        callback, futures = results[0]
        assert len(futures) == 1
        assert futures[0].rule == self.rule
        assert futures[0].kwargs == {}
        assert (
            RuleFireHistory.objects.filter(rule=self.rule, group=self.group_event.group).count()
            == 1
        )

        # should not apply twice due to default frequency
        results = list(rp.apply())
        assert len(results) == 0
        assert (
            RuleFireHistory.objects.filter(rule=self.rule, group=self.group_event.group).count()
            == 1
        )

        # now ensure that moving the last update backwards
        # in time causes the rule to trigger again
        GroupRuleStatus.objects.filter(rule=self.rule).update(
            last_active=timezone.now() - timedelta(minutes=Rule.DEFAULT_FREQUENCY + 1)
        )

        results = list(rp.apply())
        assert len(results) == 1
        rule_fire_histories = RuleFireHistory.objects.filter(
            rule=self.rule, group=self.group_event.group
        )
        assert rule_fire_histories.count() == 2
        for rule_fire_history in rule_fire_histories:
            assert getattr(rule_fire_history, "notification_uuid", None) is not None

    def test_escalating_event_condition_with_reappeared(self) -> None:
        self.rule.update(
            data={
                "conditions": [ESCALATING_EVENT_COND_DATA],
                "actions": [EMAIL_ACTION_DATA],
            },
        )

        rp = RuleProcessor(
            self.group_event,
            is_new=False,
            is_regression=False,
            is_new_group_environment=False,
            has_reappeared=True,
            has_escalated=False,
        )
        results = list(rp.apply())
        assert len(results) == 0
        assert (
            RuleFireHistory.objects.filter(rule=self.rule, group=self.group_event.group).count()
            == 0
        )

    def test_escalating_event_condition_with_escalated(self) -> None:
        self.rule.update(
            data={
                "conditions": [ESCALATING_EVENT_COND_DATA],
                "actions": [EMAIL_ACTION_DATA],
            },
        )

        rp = RuleProcessor(
            self.group_event,
            is_new=False,
            is_regression=False,
            is_new_group_environment=False,
            has_escalated=True,
            has_reappeared=False,
        )
        results = list(rp.apply())
        assert len(results) == 1
        callback, futures = results[0]
        assert len(futures) == 1
        assert futures[0].rule == self.rule
        assert (
            RuleFireHistory.objects.filter(rule=self.rule, group=self.group_event.group).count()
            == 1
        )

    def test_escalating_event_condition_with_escalated_and_reappeared(self) -> None:
        self.rule.update(
            data={
                "conditions": [ESCALATING_EVENT_COND_DATA],
                "actions": [EMAIL_ACTION_DATA],
            },
        )
        rp = RuleProcessor(
            self.group_event,
            is_new=False,
            is_regression=False,
            is_new_group_environment=False,
            has_reappeared=True,
            has_escalated=True,
        )

        results = list(rp.apply())
        assert len(results) == 1
        callback, futures = results[0]
        assert len(futures) == 1
        assert futures[0].rule == self.rule
        assert (
            RuleFireHistory.objects.filter(rule=self.rule, group=self.group_event.group).count()
            == 1
        )

    def test_escalating_event_condition_not_escalated_or_reappeared(self) -> None:
        self.rule.update(
            data={
                "conditions": [ESCALATING_EVENT_COND_DATA],
                "actions": [EMAIL_ACTION_DATA],
            },
        )
        rp = RuleProcessor(
            self.group_event,
            is_new=False,
            is_regression=False,
            is_new_group_environment=False,
            has_reappeared=False,
            has_escalated=False,
        )
        results = list(rp.apply())

        assert len(results) == 0
        assert (
            RuleFireHistory.objects.filter(rule=self.rule, group=self.group_event.group).count()
            == 0
        )

    def test_delayed_rule_match_any_slow_conditions(self) -> None:
        """
        Test that a rule with only 'slow' conditions and action match of 'any' for a performance issue gets added to the Redis buffer and does not immediately fire when the 'fast' condition fails to pass
        """
        self.rule.update(
            data={
                "conditions": [self.user_count_condition, self.event_frequency_condition],
                "action_match": "any",
                "actions": [EMAIL_ACTION_DATA],
            },
        )
        tags = [["foo", "guux"], ["sentry:release", "releaseme"]]
        contexts = {"trace": {"trace_id": "b" * 32, "span_id": "c" * 16, "op": ""}}
        for i in range(3):
            perf_event = self.create_performance_issue(
                tags=tags,
                fingerprint="group-5",
                contexts=contexts,
            )

        rp = RuleProcessor(
            perf_event,
            is_new=True,
            is_regression=True,
            is_new_group_environment=True,
            has_reappeared=True,
        )
        results = list(rp.apply())
        assert len(results) == 0
        project_ids = buffer.backend.get_sorted_set(
            PROJECT_ID_BUFFER_LIST_KEY, 0, timezone.now().timestamp()
        )
        assert len(project_ids) == 1
        assert project_ids[0][0] == self.project.id
        rulegroup_to_events = buffer.backend.get_hash(
            model=Project, field={"project_id": self.project.id}
        )
        assert rulegroup_to_events == {
            f"{self.rule.id}:{perf_event.group.id}": json.dumps(
                {"event_id": perf_event.event_id, "occurrence_id": perf_event.occurrence_id}
            )
        }

    def test_delayed_rule_match_any_slow_fast_conditions(self) -> None:
        """
        Test that a rule with a 'slow' condition, a 'fast' condition, and action match of 'any' gets added to the Redis buffer and does not immediately fire when the 'fast' condition fails to pass
        """
        first_seen_condition = {
            "id": "sentry.rules.conditions.reappeared_event.ReappearedEventCondition"
        }
        self.rule.update(
            data={
                "conditions": [first_seen_condition, self.event_frequency_condition],
                "action_match": "any",
                "actions": [EMAIL_ACTION_DATA],
            },
        )
        rp = RuleProcessor(
            self.group_event,
            is_new=True,
            is_regression=True,
            is_new_group_environment=True,
            has_reappeared=False,
        )
        results = list(rp.apply())
        assert len(results) == 0
        project_ids = buffer.backend.get_sorted_set(
            PROJECT_ID_BUFFER_LIST_KEY, 0, timezone.now().timestamp()
        )
        assert len(project_ids) == 1
        assert project_ids[0][0] == self.project.id
        rulegroup_to_events = buffer.backend.get_hash(
            model=Project, field={"project_id": self.project.id}
        )
        assert rulegroup_to_events == {
            f"{self.rule.id}:{self.group_event.group.id}": json.dumps(
                {"event_id": self.group_event.event_id, "occurrence_id": None}
            )
        }

    def test_delayed_rule_match_error_slow_fast_conditions(self) -> None:
        """
        Test that a rule with a 'slow' condition, a 'fast' condition, and action match of 'garbage' errors and does not fire or get added to the Redis queue
        """
        first_seen_condition = {
            "id": "sentry.rules.conditions.reappeared_event.ReappearedEventCondition"
        }
        self.rule.update(
            data={
                "conditions": [first_seen_condition, self.event_frequency_condition],
                "action_match": "garbage",
                "actions": [EMAIL_ACTION_DATA],
            },
        )
        rp = RuleProcessor(
            self.group_event,
            is_new=True,
            is_regression=True,
            is_new_group_environment=True,
            has_reappeared=False,
        )
        results = list(rp.apply())
        assert len(results) == 0

    def test_rule_match_any_slow_fast_conditions_fast_passes(self) -> None:
        """
        Test that a rule with both 'slow' and 'fast' conditions and action match of 'any' where a fast condition passes fires and doesn't get enqueued
        """
        self.rule.update(
            data={
                "conditions": [EVERY_EVENT_COND_DATA, self.event_frequency_condition],
                "action_match": "any",
                "actions": [EMAIL_ACTION_DATA],
            },
        )
        rp = RuleProcessor(
            self.group_event,
            is_new=True,
            is_regression=True,
            is_new_group_environment=True,
            has_reappeared=True,
        )
        results = list(rp.apply())
        assert len(results) == 1

    def test_delayed_rule_match_all(self) -> None:
        """
        Test that a rule with a 'slow' condition and action match of 'all' gets added to the Redis buffer and does not immediately fire
        """
        self.rule.update(
            data={
                "conditions": [
                    EVERY_EVENT_COND_DATA,
                    {
                        "id": "sentry.rules.conditions.event_frequency.EventFrequencyCondition",
                        "interval": "1h",
                        "value": 1,
                    },
                ],
                "action_match": "all",
                "actions": [EMAIL_ACTION_DATA],
            },
        )
        rp = RuleProcessor(
            self.group_event,
            is_new=True,
            is_regression=True,
            is_new_group_environment=True,
            has_reappeared=True,
        )
        results = list(rp.apply())
        assert len(results) == 0
        project_ids = buffer.backend.get_sorted_set(
            PROJECT_ID_BUFFER_LIST_KEY, 0, timezone.now().timestamp()
        )
        assert len(project_ids) == 1
        assert project_ids[0][0] == self.project.id
        rulegroup_to_events = buffer.backend.get_hash(
            model=Project, field={"project_id": self.project.id}
        )
        assert rulegroup_to_events == {
            f"{self.rule.id}:{self.group_event.group.id}": json.dumps(
                {"event_id": self.group_event.event_id, "occurrence_id": None}
            )
        }

    def test_ignored_issue(self) -> None:
        self.group_event.group.status = GroupStatus.IGNORED
        self.group_event.group.substatus = None
        self.group_event.group.save()
        rp = RuleProcessor(
            self.group_event,
            is_new=True,
            is_regression=True,
            is_new_group_environment=True,
            has_reappeared=True,
        )
        results = list(rp.apply())
        assert len(results) == 0

    def test_resolved_issue(self) -> None:
        self.group_event.group.status = GroupStatus.RESOLVED
        self.group_event.group.substatus = None
        self.group_event.group.save()
        rp = RuleProcessor(
            self.group_event,
            is_new=True,
            is_regression=True,
            is_new_group_environment=True,
            has_reappeared=True,
        )
        results = list(rp.apply())
        assert len(results) == 0

    def test_disabled_rule(self) -> None:
        self.rule.status = ObjectStatus.DISABLED
        self.rule.save()
        rp = RuleProcessor(
            self.group_event,
            is_new=True,
            is_regression=True,
            is_new_group_environment=True,
            has_reappeared=True,
        )
        results = list(rp.apply())
        assert len(results) == 0
        assert (
            RuleFireHistory.objects.filter(rule=self.rule, group=self.group_event.group).count()
            == 0
        )

    def test_muted_slack_rule(self) -> None:
        """Test that we don't sent a notification for a muted Slack rule"""
        integration = install_slack(self.organization)
        action_data = [
            {
                "channel": "#my-channel",
                "id": "sentry.integrations.slack.notify_action.SlackNotifyServiceAction",
                "workspace": integration.id,
            },
        ]
        slack_rule = self.create_project_rule(self.project, action_data)
        action_data[0].update({"channel": "#my-other-channel"})
        muted_slack_rule = self.create_project_rule(self.project, action_data)
        self.snooze_rule(
            owner_id=self.user.id,
            rule=muted_slack_rule,
        )
        rp = RuleProcessor(
            self.group_event,
            is_new=True,
            is_regression=True,
            is_new_group_environment=True,
            has_reappeared=True,
        )
        results = list(rp.apply())
        # this indicates that both email and slack notifs were sent, though there could be more than one of each type
        assert len(results) == 2
        # this checks that there was only 1 slack notification sent
        slack_notifs = results[1][1]
        assert len(slack_notifs) == 1
        assert slack_notifs[0].rule == slack_rule

        email_notifs = results[0][1]
        # this checks that there was only 1 email notification sent
        assert len(email_notifs) == 1
        assert results[0][1][0].rule == self.rule
        assert (
            RuleFireHistory.objects.filter(
                rule=muted_slack_rule, group=self.group_event.group
            ).count()
            == 0
        )
        slack_rule_fire_history = RuleFireHistory.objects.filter(
            rule=slack_rule, group=self.group_event.group
        )
        assert slack_rule_fire_history.count() == 1
        assert getattr(slack_rule_fire_history[0], "notification_uuid", None) is not None
        rule_fire_history = RuleFireHistory.objects.filter(
            rule=self.rule, group=self.group_event.group
        )
        assert rule_fire_history.count() == 1
        assert getattr(rule_fire_history[0], "notification_uuid", None) is not None

    def test_muted_msteams_rule(self) -> None:
        """Test that we don't sent a notification for a muted MSTeams rule"""
        tenant_id = "50cccd00-7c9c-4b32-8cda-58a084f9334a"
        integration = self.create_integration(
            self.organization,
            tenant_id,
            metadata={
                "access_token": "xoxb-xxxxxxxxx-xxxxxxxxxx-xxxxxxxxxxxx",
                "service_url": "https://testserviceurl.com/testendpoint/",
                "installation_type": "tenant",
                "expires_at": 1234567890,
                "tenant_id": tenant_id,
            },
            name="Personal Installation",
            provider="msteams",
        )

        action_data = [
            {
                "channel": "secrets",
                "id": "sentry.integrations.msteams.notify_action.MsTeamsNotifyServiceAction",
                "team": integration.id,
            },
        ]
        msteams_rule = self.create_project_rule(self.project, action_data, [])
        action_data[0].update({"channel": "#secreter-secrets"})
        muted_msteams_rule = self.create_project_rule(self.project, action_data, [])
        self.snooze_rule(
            owner_id=self.user.id,
            rule=muted_msteams_rule,
        )
        rp = RuleProcessor(
            self.group_event,
            is_new=True,
            is_regression=True,
            is_new_group_environment=True,
            has_reappeared=True,
        )
        results = list(rp.apply())
        # this indicates that both email and msteams notifs were sent, though there could be more than one of each type
        assert len(results) == 2
        slack_notifs = results[1][1]
        # this checks that there was only 1 msteams notification sent
        assert len(slack_notifs) == 1
        assert slack_notifs[0].rule == msteams_rule

        email_notifs = results[0][1]
        # this checks that there was only 1 email notification sent
        assert len(email_notifs) == 1
        assert results[0][1][0].rule == self.rule
        assert (
            RuleFireHistory.objects.filter(
                rule=muted_msteams_rule, group=self.group_event.group
            ).count()
            == 0
        )
        msteams_rule_fire_history = RuleFireHistory.objects.filter(
            rule=msteams_rule, group=self.group_event.group
        )
        assert (
            RuleFireHistory.objects.filter(rule=msteams_rule, group=self.group_event.group).count()
            == 1
        )
        assert getattr(msteams_rule_fire_history[0], "notification_uuid", None) is not None
        rule_fire_history = RuleFireHistory.objects.filter(
            rule=self.rule, group=self.group_event.group
        )
        assert rule_fire_history.count() == 1
        assert getattr(rule_fire_history[0], "notification_uuid", None) is not None

    def run_query_test(self, rp, expected_queries):
        with CaptureQueriesContext(connections[DEFAULT_DB_ALIAS]) as queries:
            results = list(rp.apply())
        status_queries = [
            q
            for q in queries.captured_queries
            if "grouprulestatus" in str(q) and "UPDATE" not in str(q)
        ]
        assert len(status_queries) == expected_queries, "\n".join(
            "%d. %s" % (i, query["sql"]) for i, query in enumerate(status_queries, start=1)
        )
        assert len(results) == 2

    def test_multiple_rules(self) -> None:
        rule_2 = Rule.objects.create(
            project=self.group_event.project,
            data={"conditions": [EVERY_EVENT_COND_DATA], "actions": [EMAIL_ACTION_DATA]},
        )
        rp = RuleProcessor(
            self.group_event,
            is_new=True,
            is_regression=True,
            is_new_group_environment=True,
            has_reappeared=True,
        )
        self.run_query_test(rp, 3)

        GroupRuleStatus.objects.filter(rule__in=[self.rule, rule_2]).update(
            last_active=timezone.now() - timedelta(minutes=Rule.DEFAULT_FREQUENCY + 1)
        )

        # GroupRuleStatus queries should be cached
        self.run_query_test(rp, 0)

        cache.clear()
        GroupRuleStatus.objects.filter(rule__in=[self.rule, rule_2]).update(
            last_active=timezone.now() - timedelta(minutes=Rule.DEFAULT_FREQUENCY + 1)
        )

        # GroupRuleStatus rows should be created, so we should perform two fewer queries since we
        # don't need to create/fetch the rows
        self.run_query_test(rp, 1)

        cache.clear()
        GroupRuleStatus.objects.filter(rule__in=[self.rule, rule_2]).update(
            last_active=timezone.now() - timedelta(minutes=Rule.DEFAULT_FREQUENCY + 1)
        )

        # Test that we don't get errors if we try to create statuses that already exist due to a
        # race condition
        with mock.patch(
            "sentry.rules.processing.processor.GroupRuleStatus"
        ) as mocked_GroupRuleStatus:
            call_count = 0

            def mock_filter(*args, **kwargs):
                nonlocal call_count
                if call_count == 0:
                    call_count += 1
                    # Make a query here to not throw the query counts off
                    return GroupRuleStatus.objects.filter(id=-1)
                return GroupRuleStatus.objects.filter(*args, **kwargs)

            mocked_GroupRuleStatus.objects.filter.side_effect = mock_filter
            # Even though the rows already exist, we should go through the creation step and make
            # the extra queries. The conflicting insert doesn't seem to be counted here since it
            # creates no rows.
            self.run_query_test(rp, 2)

    @patch(
        "sentry.constants._SENTRY_RULES",
        [
            "sentry.mail.actions.NotifyEmailAction",
            "sentry.rules.conditions.event_frequency.EventFrequencyCondition",
            "tests.sentry.rules.processing.test_processor.MockConditionTrue",
        ],
    )
    def test_slow_conditions_evaluate_last(self) -> None:
        # Make sure slow/expensive conditions are evaluated last, so that we can skip evaluating
        # them if cheaper conditions satisfy the rule.
        self.rule.update(
            data={
                "conditions": [
                    {"id": "sentry.rules.conditions.event_frequency.EventFrequencyCondition"},
                    {"id": "tests.sentry.rules.processing.test_processor.MockConditionTrue"},
                ],
                "action_match": "any",
                "actions": [EMAIL_ACTION_DATA],
            },
        )
        with (
            patch("sentry.rules.processing.processor.rules", init_registry()),
            patch(
                "sentry.rules.conditions.event_frequency.BaseEventFrequencyCondition.passes"
            ) as passes,
        ):
            rp = RuleProcessor(
                self.group_event,
                is_new=True,
                is_regression=True,
                is_new_group_environment=True,
                has_reappeared=True,
            )
            results = rp.apply()
        assert len(results) == 1
        # We should never call `passes` on the frequency condition since we should run the cheap
        # mock condition first.
        assert passes.call_count == 0


class MockFilterTrue(EventFilter):
    id = "tests.sentry.rules.processing.test_processor.MockFilterTrue"
    label = "Mock filter which always passes."

    def passes(self, event, state):
        return True


class MockFilterFalse(EventFilter):
    id = "tests.sentry.rules.processing.test_processor.MockFilterFalse"
    label = "Mock filter which never passes."

    def passes(self, event, state):
        return False


class RuleProcessorTestFilters(TestCase):
    MOCK_SENTRY_RULES_WITH_FILTERS = (
        "sentry.mail.actions.NotifyEmailAction",
        "sentry.rules.conditions.every_event.EveryEventCondition",
        "tests.sentry.rules.processing.test_processor.MockFilterTrue",
        "tests.sentry.rules.processing.test_processor.MockFilterFalse",
    )

    def setUp(self) -> None:
        event = self.store_event(data={}, project_id=self.project.id)
        self.group_event = event.for_group(cast(Group, event.group))

    @patch("sentry.constants._SENTRY_RULES", MOCK_SENTRY_RULES_WITH_FILTERS)
    def test_filter_passes(self) -> None:
        # setup a simple alert rule with 1 condition and 1 filter that always pass
        filter_data = {"id": "tests.sentry.rules.processing.test_processor.MockFilterTrue"}

        Rule.objects.filter(project=self.group_event.project).delete()
        ProjectOwnership.objects.create(project_id=self.project.id, fallthrough=True)
        self.rule = Rule.objects.create(
            project=self.group_event.project,
            data={
                "conditions": [EVERY_EVENT_COND_DATA, filter_data],
                "actions": [EMAIL_ACTION_DATA],
            },
        )
        # patch the rule registry to contain the mocked rules
        with patch("sentry.rules.processing.processor.rules", init_registry()):
            rp = RuleProcessor(
                self.group_event,
                is_new=True,
                is_regression=True,
                is_new_group_environment=True,
                has_reappeared=True,
            )
            results = list(rp.apply())
            assert len(results) == 1
            callback, futures = results[0]
            assert len(futures) == 1
            assert futures[0].rule == self.rule
            assert futures[0].kwargs == {}

    @patch("sentry.constants._SENTRY_RULES", MOCK_SENTRY_RULES_WITH_FILTERS)
    def test_filter_fails(self) -> None:
        # setup a simple alert rule with 1 condition and 1 filter that doesn't pass
        filter_data = {"id": "tests.sentry.rules.processing.test_processor.MockFilterFalse"}

        Rule.objects.filter(project=self.group_event.project).delete()
        self.rule = Rule.objects.create(
            project=self.group_event.project,
            data={
                "conditions": [EVERY_EVENT_COND_DATA, filter_data],
                "actions": [EMAIL_ACTION_DATA],
            },
        )
        # patch the rule registry to contain the mocked rules
        with patch("sentry.rules.processing.processor.rules", init_registry()):
            rp = RuleProcessor(
                self.group_event,
                is_new=True,
                is_regression=True,
                is_new_group_environment=True,
                has_reappeared=True,
            )
            results = list(rp.apply())
            assert len(results) == 0

    def test_no_filters(self) -> None:
        # setup an alert rule with 1 condition and no filters that passes
        Rule.objects.filter(project=self.group_event.project).delete()
        ProjectOwnership.objects.create(project_id=self.project.id, fallthrough=True)
        self.rule = Rule.objects.create(
            project=self.group_event.project,
            data={
                "conditions": [EVERY_EVENT_COND_DATA],
                "actions": [EMAIL_ACTION_DATA],
                "filter_match": "any",
            },
        )

        rp = RuleProcessor(
            self.group_event,
            is_new=True,
            is_regression=True,
            is_new_group_environment=True,
            has_reappeared=True,
        )
        results = list(rp.apply())
        assert len(results) == 1
        callback, futures = results[0]
        assert len(futures) == 1
        assert futures[0].rule == self.rule
        assert futures[0].kwargs == {}

    def test_no_conditions(self) -> None:
        # if a rule has no conditions/triggers it should still pass
        Rule.objects.filter(project=self.group_event.project).delete()
        ProjectOwnership.objects.create(project_id=self.project.id, fallthrough=True)
        self.rule = Rule.objects.create(
            project=self.group_event.project,
            data={"actions": [EMAIL_ACTION_DATA], "action_match": "any"},
        )

        rp = RuleProcessor(
            self.group_event,
            is_new=True,
            is_regression=True,
            is_new_group_environment=True,
            has_reappeared=True,
        )
        results = list(rp.apply())
        assert len(results) == 1
        callback, futures = results[0]
        assert len(futures) == 1
        assert futures[0].rule == self.rule
        assert futures[0].kwargs == {}

    def test_environment_mismatch(self) -> None:
        Rule.objects.filter(project=self.group_event.project).delete()
        env = self.create_environment(project=self.project)
        self.store_event(
            data={"release": "2021-02.newRelease", "environment": env.name},
            project_id=self.project.id,
        )
        self.rule = Rule.objects.create(
            project=self.group_event.project,
            environment_id=env.id,
            data={"actions": [EMAIL_ACTION_DATA], "action_match": "any"},
        )

        rp = RuleProcessor(
            self.group_event,
            is_new=True,
            is_regression=True,
            is_new_group_environment=True,
            has_reappeared=True,
        )
        results = list(rp.apply())
        assert len(results) == 0

    def test_last_active_too_recent(self) -> None:
        Rule.objects.filter(project=self.group_event.project).delete()
        self.rule = Rule.objects.create(
            project=self.group_event.project,
            data={"actions": [EMAIL_ACTION_DATA], "action_match": "any"},
        )

        rp = RuleProcessor(
            self.group_event,
            is_new=True,
            is_regression=True,
            is_new_group_environment=True,
            has_reappeared=True,
        )
        grs = GroupRuleStatus.objects.create(
            rule=self.rule,
            group=self.group,
            project=self.rule.project,
            last_active=timezone.now() - timedelta(minutes=10),
        )

        with mock.patch(
            "sentry.rules.processing.processor.bulk_get_rule_status",
            return_value={self.rule.id: grs},
        ):
            results = list(rp.apply())
            assert len(results) == 0

    @mock.patch("sentry.rules.processing.processor.logger")
    def test_invalid_predicate(self, mock_logger: MagicMock) -> None:
        filter_data = {"id": "tests.sentry.rules.processing.test_processor.MockFilterTrue"}

        Rule.objects.filter(project=self.group_event.project).delete()
        ProjectOwnership.objects.create(project_id=self.project.id, fallthrough=True)
        self.rule = Rule.objects.create(
            project=self.group_event.project,
            data={
                "conditions": [EVERY_EVENT_COND_DATA, filter_data],
                "actions": [EMAIL_ACTION_DATA],
            },
        )

        with patch("sentry.rules.processing.processor.get_match_function", return_value=None):
            rp = RuleProcessor(
                self.group_event,
                is_new=True,
                is_regression=True,
                is_new_group_environment=True,
                has_reappeared=True,
            )
            results = list(rp.apply())
            assert len(results) == 0
            mock_logger.error.assert_called_once()

    def test_latest_release(self) -> None:
        # setup an alert rule with 1 conditions and no filters that passes
        self.create_release(project=self.project, version="2021-02.newRelease")

        event = self.store_event(data={"release": "2021-02.newRelease"}, project_id=self.project.id)
        self.group_event = event.for_group(cast(Group, event.group))

        Rule.objects.filter(project=self.group_event.project).delete()
        ProjectOwnership.objects.create(project_id=self.project.id, fallthrough=True)
        self.rule = Rule.objects.create(
            project=self.group_event.project,
            data={
                "actions": [EMAIL_ACTION_DATA],
                "filter_match": "any",
                "conditions": [
                    {
                        "id": "sentry.rules.filters.latest_release.LatestReleaseFilter",
                        "name": "The event is from the latest release",
                    },
                ],
            },
        )

        rp = RuleProcessor(
            self.group_event,
            is_new=True,
            is_regression=False,
            is_new_group_environment=True,
            has_reappeared=False,
        )
        results = list(rp.apply())
        assert len(results) == 1
        callback, futures = results[0]
        assert len(futures) == 1
        assert futures[0].rule == self.rule
        assert futures[0].kwargs == {}

    def test_latest_release_environment(self) -> None:
        # setup an alert rule with 1 conditions and no filters that passes
        release = self.create_release(
            project=self.project,
            version="2021-02.newRelease",
            date_added=datetime(2020, 9, 1, 3, 8, 24, 880386, tzinfo=UTC),
            environments=[self.environment],
        )

        event = self.store_event(
            data={
                "release": release.version,
                "tags": [["environment", self.environment.name]],
            },
            project_id=self.project.id,
        )
        self.group_event = event.for_group(cast(Group, event.group))

        Rule.objects.filter(project=self.group_event.project).delete()
        ProjectOwnership.objects.create(project_id=self.project.id, fallthrough=True)
        self.rule = Rule.objects.create(
            environment_id=self.environment.id,
            project=self.group_event.project,
            data={
                "actions": [EMAIL_ACTION_DATA],
                "filter_match": "any",
                "conditions": [
                    {
                        "id": "sentry.rules.filters.latest_release.LatestReleaseFilter",
                        "name": "The event is from the latest release",
                    },
                ],
            },
        )

        rp = RuleProcessor(
            self.group_event,
            is_new=True,
            is_regression=False,
            is_new_group_environment=True,
            has_reappeared=False,
        )
        results = list(rp.apply())
        assert len(results) == 1
        callback, futures = results[0]
        assert len(futures) == 1
        assert futures[0].rule == self.rule
        assert futures[0].kwargs == {}

    @patch("sentry.integrations.slack.sdk_client.SlackSdkClient.chat_postMessage")
    def test_slack_title_link_notification_uuid(self, mock_post: MagicMock) -> None:
        """Test that the slack title link includes the notification uuid from apply function"""
        integration = install_slack(self.organization)
        action_data = [
            {
                "channel": "#my-channel",
                "id": "sentry.integrations.slack.notify_action.SlackNotifyServiceAction",
                "workspace": integration.id,
            },
        ]
        self.create_project_rule(self.project, action_data)
        rp = RuleProcessor(
            self.group_event,
            is_new=True,
            is_regression=True,
            is_new_group_environment=True,
            has_reappeared=True,
        )

        for callback, futures in rp.apply():
            callback(self.group_event, futures)
        mock_post.assert_called_once()
        assert (
            "notification_uuid"
            in json.loads(mock_post.call_args.kwargs["blocks"])[0]["elements"][0]["elements"][-1][
                "url"
            ]
        )

    @patch("sentry.shared_integrations.client.base.BaseApiClient.post")
    def test_msteams_title_link_notification_uuid(self, mock_post: MagicMock) -> None:
        """Test that the slack title link includes the notification uuid from apply function"""
        tenant_id = "50cccd00-7c9c-4b32-8cda-58a084f9334a"
        integration = self.create_integration(
            self.organization,
            tenant_id,
            metadata={
                "access_token": "xoxb-xxxxxxxxx-xxxxxxxxxx-xxxxxxxxxxxx",
                "service_url": "https://testserviceurl.com/testendpoint/",
                "installation_type": "tenant",
                "expires_at": 1234567890,
                "tenant_id": tenant_id,
            },
            name="Personal Installation",
            provider="msteams",
        )

        action_data = [
            {
                "channel": "secrets",
                "id": "sentry.integrations.msteams.notify_action.MsTeamsNotifyServiceAction",
                "team": integration.id,
            },
        ]
        self.create_project_rule(self.project, action_data, [])
        rp = RuleProcessor(
            self.group_event,
            is_new=True,
            is_regression=True,
            is_new_group_environment=True,
            has_reappeared=True,
        )

        for callback, futures in rp.apply():
            callback(self.group_event, futures)
        mock_post.assert_called_once()
        assert (
            "notification\\_uuid"
            in mock_post.call_args[1]["data"]["attachments"][0]["content"]["body"][0]["text"]
        )

    @patch("sentry.integrations.discord.message_builder.base.DiscordMessageBuilder._build")
    def test_discord_title_link_notification_uuid(self, mock_build: MagicMock) -> None:
        integration = self.create_integration(
            organization=self.organization,
            external_id="1234567890",
            name="Cool server",
            provider="discord",
        )

        action_data = [
            {
                "channel": "Cool server",
                "id": "sentry.integrations.discord.notify_action.DiscordNotifyServiceAction",
                "server": integration.id,
            },
        ]
        self.create_project_rule(self.project, action_data, [])
        rp = RuleProcessor(
            self.group_event,
            is_new=True,
            is_regression=True,
            is_new_group_environment=True,
            has_reappeared=True,
        )

        for callback, futures in rp.apply():
            callback(self.group_event, futures)
        mock_build.assert_called_once()
        assert "notification_uuid" in mock_build.call_args[1]["embeds"][0].url
