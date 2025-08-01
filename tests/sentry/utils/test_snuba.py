import unittest
from datetime import datetime, timedelta
from unittest import mock

import pytest
from django.utils import timezone
from snuba_sdk import Column, Condition, Entity, Function, Op, Query, Request
from urllib3 import HTTPConnectionPool
from urllib3.exceptions import HTTPError, ReadTimeoutError
from urllib3.response import HTTPResponse

from sentry.models.grouprelease import GroupRelease
from sentry.models.project import Project
from sentry.models.release import Release
from sentry.snuba.dataset import Dataset
from sentry.testutils.cases import TestCase
from sentry.testutils.helpers import override_options
from sentry.utils import json
from sentry.utils.snuba import (
    ROUND_UP,
    RateLimitExceeded,
    RetrySkipTimeout,
    SnubaQueryParams,
    SnubaRequest,
    UnqualifiedQueryError,
    _bulk_snuba_query,
    _prepare_query_params,
    get_json_type,
    get_query_params_to_update_for_projects,
    get_snuba_column_name,
    get_snuba_translators,
    quantize_time,
)


class SnubaUtilsTest(TestCase):
    def setUp(self) -> None:
        self.now = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        self.proj1 = self.create_project()
        self.proj1env1 = self.create_environment(project=self.proj1, name="prod")
        self.proj1group1 = self.create_group(self.proj1)
        self.proj1group2 = self.create_group(self.proj1)

        self.release1 = Release.objects.create(
            organization_id=self.organization.id, version="1" * 10, date_added=self.now
        )
        self.release1.add_project(self.proj1)
        self.release2 = Release.objects.create(
            organization_id=self.organization.id, version="2" * 10, date_added=self.now
        )
        self.release2.add_project(self.proj1)

        self.group1release1 = GroupRelease.objects.create(
            project_id=self.proj1.id, group_id=self.proj1group1.id, release_id=self.release1.id
        )
        self.group1release2 = GroupRelease.objects.create(
            project_id=self.proj1.id, group_id=self.proj1group1.id, release_id=self.release2.id
        )
        self.group2release1 = GroupRelease.objects.create(
            project_id=self.proj1.id, group_id=self.proj1group2.id, release_id=self.release1.id
        )

    def test_translation_no_translation(self) -> None:
        # Case 1: No translation
        filter_keys = {"sdk": ["python", "js"]}
        forward, reverse = get_snuba_translators(filter_keys)
        assert forward(filter_keys) == filter_keys
        result = [{"sdk": "python", "count": 123}, {"sdk": "js", "count": 234}]
        assert all(reverse(row) == row for row in result)

    def test_translation_environment_id_to_name_and_back(self) -> None:
        # Case 2: Environment ID -> Name and back
        filter_keys = {"environment": [self.proj1env1.id]}
        forward, reverse = get_snuba_translators(filter_keys)
        assert forward(filter_keys) == {"environment": [self.proj1env1.name]}
        row = {"environment": self.proj1env1.name, "count": 123}
        assert reverse(row) == {"environment": self.proj1env1.id, "count": 123}

    def test_translation_both_environment_and_release(self) -> None:
        # Case 3, both Environment and Release
        filter_keys = {
            "environment": [self.proj1env1.id],
            "tags[sentry:release]": [self.release1.id],
        }
        forward, reverse = get_snuba_translators(filter_keys)
        assert forward(filter_keys) == {
            "environment": [self.proj1env1.name],
            "tags[sentry:release]": [self.release1.version],
        }
        row = {
            "environment": self.proj1env1.name,
            "tags[sentry:release]": self.release1.version,
            "count": 123,
        }
        assert reverse(row) == {
            "environment": self.proj1env1.id,
            "tags[sentry:release]": self.release1.id,
            "count": 123,
        }

    def test_translation_two_groups_many_to_many_of_groups(self) -> None:
        # Case 4: 2 Groups, many-to-many mapping of Groups
        # to Releases. Reverse translation depends on multiple
        # fields.
        filter_keys = {
            "group_id": [self.proj1group1.id, self.proj1group2.id],
            "tags[sentry:release]": [
                self.group1release1.id,
                self.group1release2.id,
                self.group2release1.id,
            ],
        }
        forward, reverse = get_snuba_translators(filter_keys, is_grouprelease=True)
        assert forward(filter_keys) == {
            "group_id": [self.proj1group1.id, self.proj1group2.id],
            "tags[sentry:release]": [
                self.release1.version,
                self.release2.version,
                self.release1.version,  # Duplicated because 2 GroupReleases refer to it
            ],
        }
        result = [
            {
                "group_id": self.proj1group1.id,
                "tags[sentry:release]": self.release1.version,
                "count": 1,
            },
            {
                "group_id": self.proj1group1.id,
                "tags[sentry:release]": self.release2.version,
                "count": 2,
            },
            {
                "group_id": self.proj1group2.id,
                "tags[sentry:release]": self.release1.version,
                "count": 3,
            },
        ]

        result = [reverse(r) for r in result]
        assert result == [
            {
                "group_id": self.proj1group1.id,
                "tags[sentry:release]": self.group1release1.id,
                "count": 1,
            },
            {
                "group_id": self.proj1group1.id,
                "tags[sentry:release]": self.group1release2.id,
                "count": 2,
            },
            {
                "group_id": self.proj1group2.id,
                "tags[sentry:release]": self.group2release1.id,
                "count": 3,
            },
        ]

    def test_get_json_type(self) -> None:
        assert get_json_type(None) == "string"
        assert get_json_type("UInt8") == "boolean"
        assert get_json_type("UInt16") == "integer"
        assert get_json_type("UInt32") == "integer"
        assert get_json_type("UInt64") == "integer"
        assert get_json_type("Float32") == "number"
        assert get_json_type("Float64") == "number"
        assert get_json_type("Nullable(Float64)") == "number"
        assert get_json_type("Array(String)") == "array"
        assert get_json_type("DateTime") == "date"
        assert get_json_type("DateTime('UTC')") == "date"
        assert get_json_type("Char") == "string"
        assert get_json_type("unknown") == "string"
        assert get_json_type("") == "string"

    def test_get_snuba_column_name(self) -> None:
        assert get_snuba_column_name("project_id") == "project_id"
        assert get_snuba_column_name("start") == "start"
        assert get_snuba_column_name("'thing'") == "'thing'"
        assert get_snuba_column_name("id") == "event_id"
        assert get_snuba_column_name("geo.region") == "geo_region"
        assert get_snuba_column_name("tags[sentry:user]") == "tags[sentry:user]"
        assert get_snuba_column_name("organization") == "tags[organization]"
        assert get_snuba_column_name("unknown-key") == "tags[unknown-key]"

        # measurements are not available on the Events dataset, so it's seen as a tag
        assert get_snuba_column_name("measurements_key", Dataset.Events) == "tags[measurements_key]"
        assert get_snuba_column_name("measurements.key", Dataset.Events) == "tags[measurements.key]"

        # measurements are available on the Discover and Transactions dataset, so its parsed as such
        assert get_snuba_column_name("measurements_key", Dataset.Discover) == "measurements.key"
        assert get_snuba_column_name("measurements_key", Dataset.Transactions) == "measurements.key"
        assert get_snuba_column_name("measurements.key", Dataset.Discover) == "measurements[key]"
        assert (
            get_snuba_column_name("measurements.key", Dataset.Transactions) == "measurements[key]"
        )
        assert get_snuba_column_name("measurements.KEY", Dataset.Discover) == "measurements[key]"
        assert (
            get_snuba_column_name("measurements.KEY", Dataset.Transactions) == "measurements[key]"
        )

        # span op breakdowns are not available on the Events dataset, so it's seen as a tag
        assert (
            get_snuba_column_name("span_op_breakdowns_key", Dataset.Events)
            == "tags[span_op_breakdowns_key]"
        )
        assert (
            get_snuba_column_name("span_op_breakdowns.key", Dataset.Events)
            == "tags[span_op_breakdowns.key]"
        )

        # span op breakdowns are available on the Discover and Transactions dataset, so its parsed as such
        assert (
            get_snuba_column_name("span_op_breakdowns_key", Dataset.Discover)
            == "span_op_breakdowns.key"
        )
        assert (
            get_snuba_column_name("span_op_breakdowns_key", Dataset.Transactions)
            == "span_op_breakdowns.key"
        )
        assert get_snuba_column_name("spans.key", Dataset.Discover) == "span_op_breakdowns[ops.key]"
        assert (
            get_snuba_column_name("spans.key", Dataset.Transactions)
            == "span_op_breakdowns[ops.key]"
        )
        assert (
            get_snuba_column_name("spans.total.time", Dataset.Transactions)
            == "span_op_breakdowns[total.time]"
        )
        assert get_snuba_column_name("spans.KEY", Dataset.Discover) == "span_op_breakdowns[ops.key]"
        assert (
            get_snuba_column_name("spans.KEY", Dataset.Transactions)
            == "span_op_breakdowns[ops.key]"
        )


class PrepareQueryParamsTest(TestCase):
    def test_events_dataset_with_project_id(self) -> None:
        query_params = SnubaQueryParams(
            dataset=Dataset.Events, filter_keys={"project_id": [self.project.id]}
        )

        kwargs, _, _ = _prepare_query_params(query_params)
        assert kwargs["project"] == [self.project.id]

    def test_with_deleted_project(self) -> None:
        query_params = SnubaQueryParams(
            dataset=Dataset.Events, filter_keys={"project_id": [self.project.id]}
        )

        self.project.delete()
        with pytest.raises(UnqualifiedQueryError):
            get_query_params_to_update_for_projects(query_params)

    @mock.patch("sentry.models.Project.objects.get_from_cache", side_effect=Project.DoesNotExist)
    def test_with_some_deleted_projects(self, mock_project: mock.MagicMock) -> None:
        other_project = self.create_project(organization=self.organization, slug="a" * 32)
        query_params = SnubaQueryParams(
            dataset=Dataset.Events, filter_keys={"project_id": [self.project.id, other_project.id]}
        )

        other_project.delete()
        organization_id, _ = get_query_params_to_update_for_projects(query_params)
        assert organization_id == self.organization.id

    def test_outcomes_dataset_with_org_id(self) -> None:
        query_params = SnubaQueryParams(
            dataset=Dataset.Outcomes, filter_keys={"org_id": [self.organization.id]}
        )

        kwargs, _, _ = _prepare_query_params(query_params)
        assert kwargs["organization"] == self.organization.id

    def test_outcomes_dataset_with_key_id(self) -> None:
        key = self.create_project_key(project=self.project)
        query_params = SnubaQueryParams(dataset=Dataset.Outcomes, filter_keys={"key_id": [key.id]})

        kwargs, _, _ = _prepare_query_params(query_params)
        assert kwargs["organization"] == self.organization.id

    def test_outcomes_dataset_with_no_org_id_given(self) -> None:
        query_params = SnubaQueryParams(dataset=Dataset.Outcomes)

        with pytest.raises(UnqualifiedQueryError):
            _prepare_query_params(query_params)

    def test_invalid_dataset_provided(self) -> None:
        query_params = SnubaQueryParams(dataset="invalid_dataset")

        with pytest.raises(UnqualifiedQueryError):
            _prepare_query_params(query_params)

    def test_original_query_params_does_not_get_mutated(self) -> None:
        snuba_params = SnubaQueryParams(
            dataset=Dataset.Sessions,
            start=datetime.now() - timedelta(hours=1),
            end=datetime.now(),
            groupby=[],
            conditions=[[["environment", "IN", {"development", "abc"}]]],
            filter_keys={"release": [self.create_release(version="1.0.0").id]},
            aggregations=[],
            rollup=86400,
            is_grouprelease=False,
            **{"selected_columns": ["sessions"]},
        )
        conditions = [[["environment", "IN", {"development", "abc"}]]]
        kwargs = {"selected_columns": ["sessions"]}
        _prepare_query_params(snuba_params)
        assert conditions == snuba_params.conditions
        assert kwargs == snuba_params.kwargs


class QuantizeTimeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.now = timezone.now().replace(microsecond=0)

    def test_quantizes_with_duration(self) -> None:
        key_hash = 0
        time = datetime(2023, 12, 27, 4, 4, 24)

        assert quantize_time(time, key_hash, 60) == datetime(2023, 12, 27, 4, 4, 0)
        assert quantize_time(time, key_hash, 120) == datetime(2023, 12, 27, 4, 4, 0)
        assert quantize_time(time, key_hash, 900) == datetime(2023, 12, 27, 4, 0, 0)

    def test_quantizes_with_key_hash(self) -> None:
        key_hash = 12
        time = datetime(2023, 12, 27, 4, 4, 24)

        assert quantize_time(time, key_hash, 60) == datetime(2023, 12, 27, 4, 4, 12)
        assert quantize_time(time, key_hash, 900) == datetime(2023, 12, 27, 4, 0, 12)

    def test_quantizes_if_already_quantized(self) -> None:
        key_hash = 1
        duration = 10
        time = datetime(2023, 12, 27, 21, 22, 41)

        assert quantize_time(time, key_hash, duration) == datetime(2023, 12, 27, 21, 22, 31)

    def test_quantizes_with_rounding_up(self) -> None:
        assert quantize_time(datetime(2023, 12, 27, 4, 4, 0), 0, 60, ROUND_UP) == datetime(
            2023, 12, 27, 4, 4, 0
        )
        assert quantize_time(datetime(2023, 12, 27, 4, 4, 24), 0, 60, ROUND_UP) == datetime(
            2023, 12, 27, 4, 5, 0
        )

    def test_cache_suffix_time(self) -> None:
        starting_key = quantize_time(self.now, 0)
        finishing_key = quantize_time(self.now + timedelta(seconds=300), 0)

        assert starting_key != finishing_key

    def test_quantize_hour_edges(self) -> None:
        """a suffix should still behave correctly around the end of the hour

        At a duration of 10 only one key between 0-10 should flip on the hour, the other 9
        should flip at different times.
        """
        before = datetime(2019, 9, 5, 17, 59, 59)
        on_hour = datetime(2019, 9, 5, 18, 0, 0)
        changed_on_hour = 0
        # Check multiple keyhashes so that this test doesn't depend on implementation
        for key_hash in range(10):
            before_key = quantize_time(before, key_hash, duration=10)
            on_key = quantize_time(on_hour, key_hash, duration=10)
            if before_key != on_key:
                changed_on_hour += 1

        assert changed_on_hour == 1

    def test_quantize_day_edges(self) -> None:
        """a suffix should still behave correctly around the end of a day

        This test is nearly identical to test_quantize_hour_edges, but is to confirm that date changes don't
        cause a different behaviour
        """
        before = datetime(2019, 9, 5, 23, 59, 59)
        next_day = datetime(2019, 9, 6, 0, 0, 0)
        changed_on_hour = 0
        for key_hash in range(10):
            before_key = quantize_time(before, key_hash, duration=10)
            next_key = quantize_time(next_day, key_hash, duration=10)
            if before_key != next_key:
                changed_on_hour += 1

        assert changed_on_hour == 1

    def test_quantize_time_matches_duration(self) -> None:
        """The number of seconds between keys changing should match duration"""
        previous_key = quantize_time(self.now, 0, duration=10)
        changes = []
        for i in range(21):
            current_time = self.now + timedelta(seconds=i)
            current_key = quantize_time(current_time, 0, duration=10)
            if current_key != previous_key:
                changes.append(current_time)
                previous_key = current_key

        assert len(changes) == 2
        assert (changes[1] - changes[0]).total_seconds() == 10

    def test_quantize_time_jitter(self) -> None:
        """Different key hashes should change keys at different times

        While starting_key and other_key might begin as the same values they should change at different times
        """
        i = j = None
        starting_key = quantize_time(self.now, 0, duration=10)
        for i in range(11):
            current_key = quantize_time(self.now + timedelta(seconds=i), 0, duration=10)
            if current_key != starting_key:
                break

        other_key = quantize_time(self.now, 5, duration=10)
        for j in range(11):
            current_key = quantize_time(self.now + timedelta(seconds=j), 5, duration=10)
            if current_key != other_key:
                break

        assert i != j


class FakeConnectionPool(HTTPConnectionPool):
    def __init__(self, connection, **kwargs):
        self.connection = connection
        super().__init__(**kwargs)

    def _new_conn(self):
        return self.connection


def test_retries() -> None:
    """
    Tests that, even if I set up 5 retries, there is only one request
    made since it times out.
    """
    connection_mock = mock.Mock()

    snuba_pool = FakeConnectionPool(
        connection=connection_mock,
        host="www.test.com",
        port=80,
        retries=RetrySkipTimeout(total=5, allowed_methods={"GET", "POST"}),
        timeout=30,
        maxsize=10,
    )

    connection_mock.request.side_effect = ReadTimeoutError(snuba_pool, "test.com", "Timeout")

    with pytest.raises(HTTPError):
        snuba_pool.urlopen("POST", "/query", body="{}")

    assert connection_mock.request.call_count == 1


class SnubaQueryRateLimitTest(TestCase):
    def setUp(self):
        mock_request = Request(
            dataset="events",
            app_id="test",
            query=Query(
                match=Entity("events"),
                select=[Function("count", parameters=[], alias="count")],
                where=[
                    Condition(Column("project_id"), Op.EQ, self.project.id),
                    Condition(Column("timestamp"), Op.GTE, datetime.now() - timedelta(hours=1)),
                    Condition(Column("timestamp"), Op.LT, datetime.now()),
                ],
            ),
        )
        self.snuba_request = SnubaRequest(
            request=mock_request,
            referrer="test_referrer",
            forward=lambda x: x,
            reverse=lambda x: x,
        )

    @mock.patch("sentry.utils.snuba._snuba_query")
    @override_options({"issues.use-snuba-error-data": 1.0})
    def test_rate_limit_error_handling(self, mock_snuba_query) -> None:
        """
        Test error handling for rate limit errors creates a RateLimitExceeded exception
        with the correct quota used and rejection threshold
        """
        mock_response = mock.Mock(spec=HTTPResponse)
        mock_response.status = 429
        mock_response.data = json.dumps(
            {
                "error": {
                    "message": "Query on could not be run due to allocation policies, info: ...",
                    "stats": {
                        "quota_allowance": {
                            "details": {
                                "summary": {
                                    "rejected_by": {
                                        "policy": "ConcurrentRateLimitAllocationPolicy",
                                        "quota_used": 1000,
                                        "rejection_threshold": 100,
                                        "quota_unit": "no_units",
                                        "storage_key": "test_storage_key",
                                    },
                                    "throttled_by": {},
                                }
                            }
                        }
                    },
                }
            }
        ).encode()

        mock_snuba_query.return_value = ("test_referrer", mock_response, lambda x: x, lambda x: x)

        with pytest.raises(RateLimitExceeded) as exc_info:
            _bulk_snuba_query([self.snuba_request])

        assert exc_info.value.quota_used == 1000
        assert exc_info.value.rejection_threshold == 100
        assert (
            str(exc_info.value) == "Query on could not be run due to allocation policies, info: ..."
        )

    @mock.patch("sentry.utils.snuba._snuba_query")
    @override_options({"issues.use-snuba-error-data": 1.0})
    def test_rate_limit_error_handling_without_quota_details(self, mock_snuba_query) -> None:
        """
        Test that error handling gracefully handles missing quota details
        """
        mock_response = mock.Mock(spec=HTTPResponse)
        mock_response.status = 429
        mock_response.data = json.dumps(
            {
                "error": {
                    "message": "Query on could not be run due to allocation policies, info: ...",
                }
            }
        ).encode()

        mock_snuba_query.return_value = ("test_referrer", mock_response, lambda x: x, lambda x: x)

        with pytest.raises(RateLimitExceeded) as exc_info:
            _bulk_snuba_query([self.snuba_request])

        assert exc_info.value.quota_used is None
        assert exc_info.value.rejection_threshold is None
        assert (
            str(exc_info.value) == "Query on could not be run due to allocation policies, info: ..."
        )

    @mock.patch("sentry.utils.snuba._snuba_query")
    @override_options({"issues.use-snuba-error-data": 1.0})
    def test_rate_limit_error_handling_with_stats_but_no_quota_details(
        self, mock_snuba_query
    ) -> None:
        """
        Test that error handling gracefully handles stats but no quota details
        """
        mock_response = mock.Mock(spec=HTTPResponse)
        mock_response.status = 429
        mock_response.data = json.dumps(
            {
                "error": {
                    "message": "Query on could not be run due to allocation policies, info: ...",
                    "stats": {"quota_allowance": {"details": {"summary": {}}}},
                }
            }
        ).encode()

        mock_snuba_query.return_value = ("test_referrer", mock_response, lambda x: x, lambda x: x)

        with pytest.raises(RateLimitExceeded) as exc_info:
            _bulk_snuba_query([self.snuba_request])

        assert exc_info.value.quota_used is None
        assert exc_info.value.rejection_threshold is None
        assert (
            str(exc_info.value) == "Query on could not be run due to allocation policies, info: ..."
        )
