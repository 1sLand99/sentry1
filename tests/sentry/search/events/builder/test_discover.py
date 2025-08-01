from __future__ import annotations

import datetime
import re
from datetime import timezone

import pytest
from snuba_sdk.aliased_expression import AliasedExpression
from snuba_sdk.column import Column
from snuba_sdk.conditions import Condition, Op, Or
from snuba_sdk.function import Function
from snuba_sdk.orderby import Direction, LimitBy, OrderBy

from sentry.exceptions import InvalidSearchQuery
from sentry.search.events import constants
from sentry.search.events.builder.discover import DiscoverQueryBuilder
from sentry.search.events.types import ParamsType, QueryBuilderConfig
from sentry.snuba.dataset import Dataset
from sentry.snuba.referrer import Referrer
from sentry.testutils.cases import TestCase
from sentry.utils.snuba import QueryOutsideRetentionError, UnqualifiedQueryError, bulk_snuba_queries
from sentry.utils.validators import INVALID_ID_DETAILS

pytestmark = pytest.mark.sentry_metrics


class DiscoverQueryBuilderTest(TestCase):
    def setUp(self) -> None:
        self.start = datetime.datetime.now(tz=timezone.utc).replace(
            hour=10, minute=15, second=0, microsecond=0
        ) - datetime.timedelta(days=2)
        self.end = self.start + datetime.timedelta(days=1)
        self.projects = [self.project.id, self.create_project().id, self.create_project().id]
        self.params: ParamsType = {
            "project_id": self.projects,
            "start": self.start,
            "end": self.end,
        }
        # These conditions should always be on a query when self.params is passed
        self.default_conditions = [
            Condition(Column("timestamp"), Op.GTE, self.start),
            Condition(Column("timestamp"), Op.LT, self.end),
            Condition(Column("project_id"), Op.IN, self.projects),
        ]

    @pytest.mark.querybuilder
    def test_simple_query(self) -> None:
        query = DiscoverQueryBuilder(
            Dataset.Discover,
            self.params,
            query="user.email:foo@example.com release:1.2.1",
            selected_columns=["user.email", "release"],
        )

        self.assertCountEqual(
            query.where,
            [
                Condition(Column("email"), Op.EQ, "foo@example.com"),
                Condition(Column("release"), Op.IN, ["1.2.1"]),
                *self.default_conditions,
            ],
        )
        self.assertCountEqual(
            query.columns,
            [
                AliasedExpression(Column("email"), "user.email"),
                Column("release"),
            ],
        )
        query.get_snql_query().validate()

    def test_free_text_search(self) -> None:
        query = DiscoverQueryBuilder(
            Dataset.Discover,
            self.params,
            query="foo",
            selected_columns=["count()"],
        )

        self.assertCountEqual(
            query.where,
            [
                Condition(
                    Function("positionCaseInsensitive", [Column("message"), "foo"]),
                    Op.NEQ,
                    0,
                ),
                *self.default_conditions,
            ],
        )

    def test_query_without_project_ids(self) -> None:
        params: ParamsType = {
            "start": self.params["start"],
            "end": self.params["end"],
            "organization_id": self.organization.id,
        }
        with pytest.raises(UnqualifiedQueryError):
            query = DiscoverQueryBuilder(
                Dataset.Discover, params, query="foo", selected_columns=["id"]
            )
            bulk_snuba_queries([query.get_snql_query()], referrer=Referrer.TESTING_TEST.value)

    def test_query_with_empty_project_ids(self) -> None:
        params: ParamsType = {
            "start": self.params["start"],
            "end": self.params["end"],
            "project_id": [],  # We add an empty project_id list
            "organization_id": self.organization.id,
        }
        with pytest.raises(UnqualifiedQueryError):
            query = DiscoverQueryBuilder(
                Dataset.Discover, params, query="foo", selected_columns=["id"]
            )
            bulk_snuba_queries([query.get_snql_query()], referrer=Referrer.TESTING_TEST.value)

    def test_multiple_wildcards(self) -> None:
        query = DiscoverQueryBuilder(
            Dataset.Discover, self.params, query='title:["*A", "*B", "C", "D"]'
        )

        expected = Or(
            [
                Condition(
                    Function("match", [Column("title"), "(?i)^.*A$"]),
                    Op.EQ,
                    1,
                ),
                Condition(
                    Function("match", [Column("title"), "(?i)^.*B$"]),
                    Op.EQ,
                    1,
                ),
                Condition(Column("title"), Op.IN, ["C", "D"]),
            ]
        )

        self.assertCountEqual(query.where[0].conditions, expected.conditions)

    def test_single_wildcard_set(self) -> None:
        query = DiscoverQueryBuilder(Dataset.Discover, self.params, query='title:["*A", "D"]')

        expected = Or(
            [
                Condition(
                    Function("match", [Column("title"), "(?i)^.*A$"]),
                    Op.EQ,
                    1,
                ),
                Condition(Column("title"), Op.IN, ["D"]),
            ]
        )

        self.assertCountEqual(query.where[0].conditions, expected.conditions)

    def test_single_wildcard(self) -> None:
        query = DiscoverQueryBuilder(Dataset.Discover, self.params, query='title:["*A"]')

        expected = [
            Condition(
                Function("match", [Column("title"), "(?i)^.*A$"]),
                Op.EQ,
                1,
            ),
            *self.default_conditions,
        ]

        self.assertCountEqual(query.where, expected)

    def test_simple_orderby(self) -> None:
        query = DiscoverQueryBuilder(
            Dataset.Discover,
            self.params,
            selected_columns=["user.email", "release"],
            orderby=["user.email"],
        )

        self.assertCountEqual(query.where, self.default_conditions)
        self.assertCountEqual(
            query.orderby,
            [OrderBy(Column("email"), Direction.ASC)],
        )
        query.get_snql_query().validate()

        query = DiscoverQueryBuilder(
            Dataset.Discover,
            self.params,
            selected_columns=["user.email", "release"],
            orderby=["-user.email"],
        )

        self.assertCountEqual(query.where, self.default_conditions)
        self.assertCountEqual(
            query.orderby,
            [OrderBy(Column("email"), Direction.DESC)],
        )
        query.get_snql_query().validate()

    def test_orderby_duplicate_columns(self) -> None:
        query = DiscoverQueryBuilder(
            Dataset.Discover,
            self.params,
            selected_columns=["user.email", "user.email"],
            orderby=["user.email"],
        )
        self.assertCountEqual(
            query.orderby,
            [OrderBy(Column("email"), Direction.ASC)],
        )

    def test_simple_limitby(self) -> None:
        query = DiscoverQueryBuilder(
            dataset=Dataset.Discover,
            params=self.params,
            query="",
            selected_columns=["message"],
            orderby="message",
            limitby=("message", 1),
            limit=4,
        )

        assert query.limitby == LimitBy([Column("message")], 1)

    def test_environment_filter(self) -> None:
        query = DiscoverQueryBuilder(
            Dataset.Discover,
            self.params,
            query="environment:prod",
            selected_columns=["environment"],
        )

        self.assertCountEqual(
            query.where,
            [
                Condition(Column("environment"), Op.EQ, "prod"),
                *self.default_conditions,
            ],
        )
        query.get_snql_query().validate()

        query = DiscoverQueryBuilder(
            Dataset.Discover,
            self.params,
            query="environment:[dev, prod]",
            selected_columns=["environment"],
        )

        self.assertCountEqual(
            query.where,
            [
                Condition(Column("environment"), Op.IN, ["dev", "prod"]),
                *self.default_conditions,
            ],
        )
        query.get_snql_query().validate()

    def test_environment_param(self) -> None:
        self.params["environment"] = ["", self.environment.name]
        query = DiscoverQueryBuilder(
            Dataset.Discover, self.params, selected_columns=["environment"]
        )

        self.assertCountEqual(
            query.where,
            [
                *self.default_conditions,
                Or(
                    [
                        Condition(Column("environment"), Op.IS_NULL),
                        Condition(Column("environment"), Op.EQ, self.environment.name),
                    ]
                ),
            ],
        )
        query.get_snql_query().validate()

        env2 = self.create_environment()
        self.params["environment"] = [self.environment.name, env2.name]
        query = DiscoverQueryBuilder(
            Dataset.Discover, self.params, selected_columns=["environment"]
        )

        self.assertCountEqual(
            query.where,
            [
                *self.default_conditions,
                Condition(Column("environment"), Op.IN, sorted([self.environment.name, env2.name])),
            ],
        )
        query.get_snql_query().validate()

    def test_project_in_condition_filters(self) -> None:
        # TODO(snql-boolean): Update this to match the corresponding test in test_filter
        project1 = self.create_project()
        project2 = self.create_project()
        self.params["project_id"] = [project1.id, project2.id]
        query = DiscoverQueryBuilder(
            Dataset.Discover,
            self.params,
            query=f"project:{project1.slug}",
            selected_columns=["environment"],
        )

        self.assertCountEqual(
            query.where,
            [
                # generated by the search query on project
                Condition(Column("project_id"), Op.EQ, project1.id),
                Condition(Column("timestamp"), Op.GTE, self.start),
                Condition(Column("timestamp"), Op.LT, self.end),
                # default project filter from the params
                Condition(Column("project_id"), Op.IN, [project1.id, project2.id]),
            ],
        )

    def test_project_in_condition_filters_not_in_project_filter(self) -> None:
        # TODO(snql-boolean): Update this to match the corresponding test in test_filter
        project1 = self.create_project()
        project2 = self.create_project()
        # params is assumed to be validated at this point, so this query should be invalid
        self.params["project_id"] = [project2.id]
        with pytest.raises(
            InvalidSearchQuery,
            match=re.escape(
                f"Invalid query. Project(s) {str(project1.slug)} do not exist or are not actively selected."
            ),
        ):
            DiscoverQueryBuilder(
                Dataset.Discover,
                self.params,
                query=f"project:{project1.slug}",
                selected_columns=["environment"],
            )

    def test_project_alias_column(self) -> None:
        # TODO(snql-boolean): Update this to match the corresponding test in test_filter
        project1 = self.create_project()
        project2 = self.create_project()
        self.params["project_id"] = [project1.id, project2.id]
        query = DiscoverQueryBuilder(Dataset.Discover, self.params, selected_columns=["project"])

        self.assertCountEqual(
            query.where,
            [
                Condition(Column("project_id"), Op.IN, [project1.id, project2.id]),
                Condition(Column("timestamp"), Op.GTE, self.start),
                Condition(Column("timestamp"), Op.LT, self.end),
            ],
        )
        self.assertCountEqual(
            query.columns,
            [
                AliasedExpression(
                    Column("project_id"),
                    "project",
                )
            ],
        )

    def test_project_alias_column_with_project_condition(self) -> None:
        project1 = self.create_project()
        project2 = self.create_project()
        self.params["project_id"] = [project1.id, project2.id]
        query = DiscoverQueryBuilder(
            Dataset.Discover,
            self.params,
            query=f"project:{project1.slug}",
            selected_columns=["project"],
        )

        self.assertCountEqual(
            query.where,
            [
                # generated by the search query on project
                Condition(Column("project_id"), Op.EQ, project1.id),
                Condition(Column("timestamp"), Op.GTE, self.start),
                Condition(Column("timestamp"), Op.LT, self.end),
                # default project filter from the params
                Condition(Column("project_id"), Op.IN, [project1.id, project2.id]),
            ],
        )
        # Because of the condition on project there should only be 1 project in the transform
        self.assertCountEqual(
            query.columns,
            [
                AliasedExpression(
                    Column("project_id"),
                    "project",
                )
            ],
        )

    def test_orderby_project_alias(self) -> None:
        project1 = self.create_project(name="zzz")
        project2 = self.create_project(name="aaa")
        self.params["project_id"] = [project1.id, project2.id]
        query = DiscoverQueryBuilder(
            Dataset.Discover, self.params, selected_columns=["project"], orderby=["project"]
        )

        self.assertCountEqual(
            query.orderby,
            [
                OrderBy(
                    Function(
                        "transform",
                        [
                            Column("project_id"),
                            [project1.id, project2.id],
                            [project1.slug, project2.slug],
                            "",
                        ],
                    ),
                    Direction.ASC,
                )
            ],
        )

    def test_count_if(self) -> None:
        query = DiscoverQueryBuilder(
            Dataset.Discover,
            self.params,
            query="",
            selected_columns=[
                "count_if(event.type,equals,transaction)",
                'count_if(event.type,notEquals,"transaction")',
            ],
        )
        self.assertCountEqual(query.where, self.default_conditions)
        self.assertCountEqual(
            query.aggregates,
            [
                Function(
                    "countIf",
                    [
                        Function("equals", [Column("type"), "transaction"]),
                    ],
                    "count_if_event_type_equals_transaction",
                ),
                Function(
                    "countIf",
                    [
                        Function("notEquals", [Column("type"), "transaction"]),
                    ],
                    "count_if_event_type_notEquals__transaction",
                ),
            ],
        )

    def test_count_if_array(self) -> None:
        self.maxDiff = None
        query = DiscoverQueryBuilder(
            Dataset.Discover,
            self.params,
            query="",
            selected_columns=[
                "count_if(error.type,equals,SIGABRT)",
                "count_if(error.type,notEquals,SIGABRT)",
            ],
        )
        self.assertCountEqual(query.where, self.default_conditions)
        self.assertCountEqual(
            query.aggregates,
            [
                Function(
                    "countIf",
                    [
                        Function(
                            "has",
                            [
                                Column("exception_stacks.type"),
                                "SIGABRT",
                            ],
                        ),
                    ],
                    "count_if_error_type_equals_SIGABRT",
                ),
                Function(
                    "countIf",
                    [
                        Function(
                            "equals",
                            [
                                Function(
                                    "has",
                                    [
                                        Column("exception_stacks.type"),
                                        "SIGABRT",
                                    ],
                                ),
                                0,
                            ],
                        ),
                    ],
                    "count_if_error_type_notEquals_SIGABRT",
                ),
            ],
        )

    def test_count_if_with_tags(self) -> None:
        query = DiscoverQueryBuilder(
            Dataset.Discover,
            self.params,
            query="",
            selected_columns=[
                "count_if(foo,equals,bar)",
                'count_if(foo,notEquals,"baz")',
            ],
        )
        self.assertCountEqual(query.where, self.default_conditions)
        self.assertCountEqual(
            query.aggregates,
            [
                Function(
                    "countIf",
                    [
                        Function("equals", [Column("tags[foo]"), "bar"]),
                    ],
                    "count_if_foo_equals_bar",
                ),
                Function(
                    "countIf",
                    [
                        Function("notEquals", [Column("tags[foo]"), "baz"]),
                    ],
                    "count_if_foo_notEquals__baz",
                ),
            ],
        )

    def test_not_empty_measurement(self) -> None:
        query = DiscoverQueryBuilder(
            Dataset.Discover,
            self.params,
            query="has:measurements.lcp",
        )

        lcp = Column("measurements[lcp]")

        self.assertCountEqual(
            query.where,
            [
                Condition(Function("isNull", [lcp]), Op.EQ, 0),
                *self.default_conditions,
            ],
        )

    def test_not_empty_function_measurement(self) -> None:
        query = DiscoverQueryBuilder(
            Dataset.Discover,
            self.params,
            query="has:measurements.frames_frozen_rate",
        )

        frames_total = Column("measurements[frames_total]")
        frames_frozen = Column("measurements[frames_frozen]")

        frames_frozen_rate = Function(
            "if",
            [
                Function("greater", [frames_total, 0]),
                Function("divide", [frames_frozen, frames_total]),
                None,
            ],
            alias="measurements.frames_frozen_rate",
        )

        self.assertCountEqual(
            query.where,
            [
                Condition(Function("isNull", [frames_frozen_rate]), Op.EQ, 0),
                *self.default_conditions,
            ],
        )

    def test_array_join(self) -> None:
        query = DiscoverQueryBuilder(
            Dataset.Discover,
            self.params,
            query="",
            selected_columns=["array_join(measurements_key)", "count()"],
            config=QueryBuilderConfig(
                functions_acl=["array_join"],
            ),
        )
        array_join_column = Function(
            "arrayJoin",
            [Column("measurements.key")],
            "array_join_measurements_key",
        )
        self.assertCountEqual(query.columns, [array_join_column, Function("count", [], "count")])
        # make sure the array join columns are present in gropuby
        self.assertCountEqual(query.groupby, [array_join_column])

    def test_retention(self) -> None:
        old_start = datetime.datetime(2015, 5, 18, 10, 15, 1, tzinfo=timezone.utc)
        old_end = datetime.datetime(2015, 5, 19, 10, 15, 1, tzinfo=timezone.utc)
        old_params: ParamsType = {**self.params, "start": old_start, "end": old_end}
        with self.options({"system.event-retention-days": 10}):
            with pytest.raises(QueryOutsideRetentionError):
                DiscoverQueryBuilder(
                    Dataset.Discover,
                    old_params,
                    query="",
                    selected_columns=[],
                )

    def test_array_combinator(self) -> None:
        query = DiscoverQueryBuilder(
            Dataset.Discover,
            self.params,
            query="",
            selected_columns=["sumArray(measurements_value)"],
            config=QueryBuilderConfig(
                functions_acl=["sumArray"],
            ),
        )
        self.assertCountEqual(
            query.columns,
            [
                Function(
                    "sum",
                    [Function("arrayJoin", [Column("measurements.value")])],
                    "sumArray_measurements_value",
                )
            ],
        )

    def test_array_combinator_is_private(self) -> None:
        with pytest.raises(InvalidSearchQuery, match="sum: no access to private function"):
            DiscoverQueryBuilder(
                Dataset.Discover,
                self.params,
                query="",
                selected_columns=["sumArray(measurements_value)"],
            )

    def test_array_combinator_with_non_array_arg(self) -> None:
        with pytest.raises(InvalidSearchQuery, match="stuff is not a valid array column"):
            DiscoverQueryBuilder(
                Dataset.Discover,
                self.params,
                query="",
                selected_columns=["sumArray(stuff)"],
                config=QueryBuilderConfig(
                    functions_acl=["sumArray"],
                ),
            )

    def test_spans_columns(self) -> None:
        query = DiscoverQueryBuilder(
            Dataset.Discover,
            self.params,
            query="",
            selected_columns=[
                "array_join(spans_op)",
                "array_join(spans_group)",
                "sumArray(spans_exclusive_time)",
            ],
            config=QueryBuilderConfig(
                functions_acl=["array_join", "sumArray"],
            ),
        )
        self.assertCountEqual(
            query.columns,
            [
                Function("arrayJoin", [Column("spans.op")], "array_join_spans_op"),
                Function("arrayJoin", [Column("spans.group")], "array_join_spans_group"),
                Function(
                    "sum",
                    [Function("arrayJoin", [Column("spans.exclusive_time")])],
                    "sumArray_spans_exclusive_time",
                ),
            ],
        )

    def test_array_join_clause(self) -> None:
        query = DiscoverQueryBuilder(
            Dataset.Discover,
            self.params,
            query="",
            selected_columns=[
                "spans_op",
                "count()",
            ],
            array_join="spans_op",
        )
        self.assertCountEqual(
            query.columns,
            [
                AliasedExpression(Column("spans.op"), "spans_op"),
                Function("count", [], "count"),
            ],
        )

        assert query.array_join == [Column("spans.op")]
        query.get_snql_query().validate()

    def test_sample_rate(self) -> None:
        query = DiscoverQueryBuilder(
            Dataset.Discover,
            self.params,
            query="",
            selected_columns=[
                "count()",
            ],
            sample_rate=0.1,
        )
        assert query.sample_rate == 0.1
        snql_query = query.get_snql_query().query
        snql_query.validate()
        assert snql_query.match.sample == 0.1

    def test_turbo(self) -> None:
        query = DiscoverQueryBuilder(
            Dataset.Discover,
            self.params,
            query="",
            selected_columns=[
                "count()",
            ],
            turbo=True,
        )
        assert query.turbo
        snql_query = query.get_snql_query()
        snql_query.validate()
        assert snql_query.flags.turbo

    def test_auto_aggregation(self) -> None:
        query = DiscoverQueryBuilder(
            Dataset.Discover,
            self.params,
            query="count_unique(user):>10",
            selected_columns=[
                "count()",
            ],
            config=QueryBuilderConfig(
                auto_aggregations=True,
                use_aggregate_conditions=True,
            ),
        )
        snql_query = query.get_snql_query().query
        snql_query.validate()
        self.assertCountEqual(
            snql_query.having,
            [
                Condition(Function("uniq", [Column("user")], "count_unique_user"), Op.GT, 10),
            ],
        )
        self.assertCountEqual(
            snql_query.select,
            [
                Function("uniq", [Column("user")], "count_unique_user"),
                Function("count", [], "count"),
            ],
        )

    def test_auto_aggregation_with_boolean(self) -> None:
        query = DiscoverQueryBuilder(
            Dataset.Discover,
            self.params,
            # Nonsense query but doesn't matter
            query="count_unique(user):>10 OR count_unique(user):<10",
            selected_columns=[
                "count()",
            ],
            config=QueryBuilderConfig(
                auto_aggregations=True,
                use_aggregate_conditions=True,
            ),
        )
        snql_query = query.get_snql_query().query
        snql_query.validate()
        self.assertCountEqual(
            snql_query.having,
            [
                Or(
                    [
                        Condition(
                            Function("uniq", [Column("user")], "count_unique_user"), Op.GT, 10
                        ),
                        Condition(
                            Function("uniq", [Column("user")], "count_unique_user"), Op.LT, 10
                        ),
                    ]
                )
            ],
        )
        self.assertCountEqual(
            snql_query.select,
            [
                Function("uniq", [Column("user")], "count_unique_user"),
                Function("count", [], "count"),
            ],
        )

    def test_disable_auto_aggregation(self) -> None:
        query = DiscoverQueryBuilder(
            Dataset.Discover,
            self.params,
            query="count_unique(user):>10",
            selected_columns=[
                "count()",
            ],
            config=QueryBuilderConfig(
                auto_aggregations=False,
                use_aggregate_conditions=True,
            ),
        )
        # With count_unique only in a condition and no auto_aggregations this should raise a invalid search query
        with pytest.raises(InvalidSearchQuery):
            query.get_snql_query()

    def test_query_chained_or_tip(self) -> None:
        query = DiscoverQueryBuilder(
            Dataset.Discover,
            self.params,
            query="field:a OR field:b OR field:c",
            selected_columns=[
                "field",
            ],
        )
        assert constants.QUERY_TIPS["CHAINED_OR"] in query.tips["query"]

    def test_chained_or_with_different_terms(self) -> None:
        query = DiscoverQueryBuilder(
            Dataset.Discover,
            self.params,
            query="field:a or field:b or event.type:transaction or transaction:foo",
            selected_columns=[
                "field",
            ],
        )
        # This query becomes something roughly like:
        # field:a or (field:b or (event.type:transaciton or transaction: foo))
        assert constants.QUERY_TIPS["CHAINED_OR"] in query.tips["query"]

        query = DiscoverQueryBuilder(
            Dataset.Discover,
            self.params,
            query="event.type:transaction or transaction:foo or field:a or field:b",
            selected_columns=[
                "field",
            ],
        )
        assert constants.QUERY_TIPS["CHAINED_OR"] in query.tips["query"]

    def test_chained_or_with_different_terms_with_and(self) -> None:
        query = DiscoverQueryBuilder(
            Dataset.Discover,
            self.params,
            # There's an implicit and between field:b, and event.type:transaction
            query="field:a or field:b event.type:transaction",
            selected_columns=[
                "field",
            ],
        )
        # This query becomes something roughly like:
        # field:a or (field:b and event.type:transaction)
        assert constants.QUERY_TIPS["CHAINED_OR"] not in query.tips["query"]

        query = DiscoverQueryBuilder(
            Dataset.Discover,
            self.params,
            # There's an implicit and between event.type:transaction, and field:a
            query="event.type:transaction field:a or field:b",
            selected_columns=[
                "field",
            ],
        )
        # This query becomes something roughly like:
        # field:a or (field:b and event.type:transaction)
        assert constants.QUERY_TIPS["CHAINED_OR"] not in query.tips["query"]

    def test_group_by_not_in_select(self) -> None:
        query = DiscoverQueryBuilder(
            Dataset.Discover,
            self.params,
            query="",
            selected_columns=[
                "count()",
                "event.type",
            ],
            groupby_columns=[
                "transaction",
            ],
        )
        snql_query = query.get_snql_query().query
        self.assertCountEqual(
            snql_query.select,
            [
                Function("count", [], "count"),
                AliasedExpression(Column("type"), "event.type"),
            ],
        )
        self.assertCountEqual(
            snql_query.groupby,
            [
                AliasedExpression(Column("type"), "event.type"),
                Column("transaction"),
            ],
        )

    def test_group_by_duplicates_select(self) -> None:
        query = DiscoverQueryBuilder(
            Dataset.Discover,
            self.params,
            query="",
            selected_columns=[
                "count()",
                "transaction",
            ],
            groupby_columns=[
                "transaction",
            ],
        )
        snql_query = query.get_snql_query().query
        self.assertCountEqual(
            snql_query.select,
            [
                Function("count", [], "count"),
                Column("transaction"),
            ],
        )
        self.assertCountEqual(
            snql_query.groupby,
            [
                Column("transaction"),
            ],
        )

    def test_missing_function(self) -> None:
        with pytest.raises(InvalidSearchQuery):
            DiscoverQueryBuilder(
                Dataset.Discover,
                self.params,
                query="",
                selected_columns=[
                    "count_all_the_things_that_i_want()",
                    "transaction",
                ],
                groupby_columns=[
                    "transaction",
                ],
            )

    def test_id_filter_non_uuid(self) -> None:
        with pytest.raises(InvalidSearchQuery, match=re.escape(INVALID_ID_DETAILS.format("id"))):
            DiscoverQueryBuilder(
                Dataset.Discover,
                self.params,
                query="id:foo",
                selected_columns=["count()"],
            )

    def test_trace_id_filter_non_uuid(self) -> None:
        with pytest.raises(InvalidSearchQuery, match=re.escape(INVALID_ID_DETAILS.format("trace"))):
            DiscoverQueryBuilder(
                Dataset.Discover,
                self.params,
                query="trace:foo",
                selected_columns=["count()"],
            )

    def test_profile_id_filter_non_uuid(self) -> None:
        with pytest.raises(
            InvalidSearchQuery, match=re.escape(INVALID_ID_DETAILS.format("profile.id"))
        ):
            DiscoverQueryBuilder(
                Dataset.Discover,
                self.params,
                query="profile.id:foo",
                selected_columns=["count()"],
            )

    def test_orderby_raw_empty_equation(self) -> None:
        with pytest.raises(InvalidSearchQuery, match=re.escape("Cannot sort by an empty equation")):
            DiscoverQueryBuilder(
                Dataset.Discover,
                self.params,
                query="",
                selected_columns=["count()"],
                orderby="equation|",
            )

    def test_orderby_salted_column_hash(self) -> None:
        query = DiscoverQueryBuilder(
            Dataset.Discover,
            self.params,
            query="",
            selected_columns=["column_hash(transaction) as sample"],
            orderby=["sample"],
            config=QueryBuilderConfig(
                functions_acl=["column_hash"],
            ),
        )
        snql_query = query.get_snql_query().query
        self.assertCountEqual(
            snql_query.orderby,
            [
                OrderBy(
                    Function("farmFingerprint64", [Column("transaction")], "sample"),
                    Direction.ASC,
                )
            ],
        )

    def test_symbolicated_in_app_parameter(self) -> None:
        query = DiscoverQueryBuilder(
            Dataset.Discover,
            self.params,
            query="symbolicated_in_app:True",
            selected_columns=["symbolicated_in_app"],
        )

        self.assertCountEqual(
            query.where,
            [
                Condition(Column("symbolicated_in_app"), Op.EQ, 1),
                *self.default_conditions,
            ],
        )
        query.get_snql_query().validate()

        query = DiscoverQueryBuilder(
            Dataset.Discover,
            self.params,
            query="symbolicated_in_app:False",
            selected_columns=["symbolicated_in_app"],
        )

        self.assertCountEqual(
            query.where,
            [
                Condition(Column("symbolicated_in_app"), Op.EQ, 0),
                *self.default_conditions,
            ],
        )
        query.get_snql_query().validate()

        # Test !has: filter for checking NULL values
        query = DiscoverQueryBuilder(
            Dataset.Discover,
            self.params,
            query="!has:symbolicated_in_app",
            selected_columns=["symbolicated_in_app"],
        )

        self.assertCountEqual(
            query.where,
            [
                Condition(Function("isNull", [Column("symbolicated_in_app")]), Op.EQ, 1),
                *self.default_conditions,
            ],
        )
        query.get_snql_query().validate()
