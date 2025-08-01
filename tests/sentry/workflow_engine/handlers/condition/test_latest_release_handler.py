from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from jsonschema import ValidationError

from sentry.models.release import Release
from sentry.rules.filters.latest_release import LatestReleaseFilter, get_project_release_cache_key
from sentry.testutils.skips import requires_snuba
from sentry.utils.cache import cache
from sentry.workflow_engine.models.data_condition import Condition
from sentry.workflow_engine.types import WorkflowEventData
from tests.sentry.workflow_engine.handlers.condition.test_base import ConditionTestCase

pytestmark = [requires_snuba, pytest.mark.sentry_metrics]


class TestLatestReleaseCondition(ConditionTestCase):
    condition = Condition.LATEST_RELEASE
    payload = {
        "id": LatestReleaseFilter.id,
    }

    def setUp(self) -> None:
        super().setUp()
        self.event_data = WorkflowEventData(event=self.group_event, group=self.group_event.group)
        self.dc = self.create_data_condition(
            type=self.condition,
            comparison=True,
            condition_result=True,
        )

    def test_dual_write(self) -> None:
        dcg = self.create_data_condition_group()
        dc = self.translate_to_data_condition(self.payload, dcg)

        assert dc.type == self.condition
        assert dc.comparison is True
        assert dc.condition_result is True
        assert dc.condition_group == dcg

    def test_json_schema(self) -> None:
        self.dc.comparison = False
        self.dc.save()

        self.dc.comparison = {"time": "asdf"}
        with pytest.raises(ValidationError):
            self.dc.save()

        self.dc.comparison = "hello"
        with pytest.raises(ValidationError):
            self.dc.save()

    def test_latest_release(self) -> None:
        old_release = Release.objects.create(
            organization_id=self.organization.id,
            version="1",
            date_added=datetime(2020, 9, 1, 3, 8, 24, 880386, tzinfo=UTC),
        )
        old_release.add_project(self.project)

        new_release = Release.objects.create(
            organization_id=self.organization.id,
            version="2",
            date_added=datetime(2020, 9, 2, 3, 8, 24, 880386, tzinfo=UTC),
        )
        new_release.add_project(self.project)

        self.event.data["tags"] = (("release", new_release.version),)
        self.assert_passes(self.dc, self.event_data)

    def test_latest_release_no_match(self) -> None:
        old_release = Release.objects.create(
            organization_id=self.organization.id,
            version="1",
            date_added=datetime(2020, 9, 1, 3, 8, 24, 880386, tzinfo=UTC),
        )
        old_release.add_project(self.project)

        new_release = Release.objects.create(
            organization_id=self.organization.id,
            version="2",
            date_added=datetime(2020, 9, 2, 3, 8, 24, 880386, tzinfo=UTC),
        )
        new_release.add_project(self.project)

        self.event.data["tags"] = (("release", old_release.version),)
        self.assert_does_not_pass(self.dc, self.event_data)

    def test_caching(self) -> None:
        old_release = Release.objects.create(
            organization_id=self.organization.id,
            version="1",
            date_added=datetime(2020, 9, 1, 3, 8, 24, 880386, tzinfo=UTC),
        )
        old_release.add_project(self.project)
        self.event.data["tags"] = (("release", old_release.version),)
        self.assert_passes(self.dc, self.event_data)

        new_release = Release.objects.create(
            organization_id=self.organization.id,
            version="2",
            date_added=datetime(2020, 9, 2, 3, 8, 24, 880386, tzinfo=UTC),
        )
        new_release.add_project(self.project)

        # ensure we clear the cache after creating a new release
        cache_key = get_project_release_cache_key(self.event.group.project_id)
        assert cache.get(cache_key) is None

        self.assert_does_not_pass(self.dc, self.event_data)

        # ensure we clear the cache when a release is deleted
        new_release.safe_delete()
        cache_key = get_project_release_cache_key(self.event.group.project_id)
        assert cache.get(cache_key) is None

        # rule should pass again because the latest release is oldRelease
        self.assert_passes(self.dc, self.event_data)

    def test_latest_release_with_environment(self) -> None:
        self.create_release(
            project=self.event.group.project,
            version="1",
            date_added=datetime(2020, 9, 1, 3, 8, 24, 880386, tzinfo=UTC),
            environments=[self.environment],
        )

        new_release = self.create_release(
            project=self.event.group.project,
            version="2",
            date_added=datetime(2020, 9, 2, 3, 8, 24, 880386, tzinfo=UTC),
            environments=[self.environment],
        )

        other_env_release = self.create_release(
            project=self.event.group.project,
            version="4",
            date_added=datetime(2020, 9, 3, 3, 8, 24, 880386, tzinfo=UTC),
        )

        self.event_data = WorkflowEventData(
            event=self.group_event, workflow_env=self.environment, group=self.group_event.group
        )

        self.event.data["tags"] = (("release", new_release.version),)
        self.assert_passes(self.dc, self.event_data)

        self.event.data["tags"] = (("release", other_env_release.version),)
        self.assert_does_not_pass(self.dc, self.event_data)

    @patch("sentry.search.utils.get_latest_release")
    def test_release_does_not_exist(self, mock_get_latest_release: MagicMock) -> None:
        mock_get_latest_release.side_effect = Release.DoesNotExist
        self.assert_does_not_pass(self.dc, self.event_data)

    @patch.object(Release.objects, "get", return_value=None)
    def test_no_release_object(self, mock_get: MagicMock) -> None:
        newRelease = Release.objects.create(
            organization_id=self.organization.id,
            version="2",
            date_added=datetime(2020, 9, 2, 3, 8, 24, 880386, tzinfo=UTC),
        )
        newRelease.add_project(self.project)

        self.assert_does_not_pass(self.dc, self.event_data)
