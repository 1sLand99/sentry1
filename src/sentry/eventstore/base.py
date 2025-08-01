from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import datetime
from typing import Any, Literal, Self, overload

import sentry_sdk
from snuba_sdk import Condition

from sentry import nodestore
from sentry.eventstore.models import Event, GroupEvent
from sentry.snuba.dataset import Dataset
from sentry.snuba.events import Columns
from sentry.utils.services import Service


class Filter:
    """
    A set of conditions, start/end times and project, group and event ID sets
    used to restrict the results of a Snuba query.

    start (DateTime): Start datetime - default None
    end (DateTime): Start datetime - default None
    conditions (Sequence[tuple[str, str, Any]]): List of conditions to fetch - default None
    having (Sequence[str, str, Any]]): List of having conditions to filter by - default None
    user_id (int): The user ID to fetch - default None
    organization_id (int): The organization ID to fetch - default None
    team_id (Sequence[int]): List of team IDs to fetch - default None
    project_ids (Sequence[int]): List of project IDs to fetch - default None
    group_ids (Sequence[int]): List of group IDs to fetch - default None
    event_ids (Sequence[int]): List of event IDs to fetch - default None

    selected_columns (Sequence[str]): List of columns to select
    aggregations (Sequence[Any, str|None, str]): Aggregate functions to fetch.
    groupby (Sequence[str]): List of columns to group results by

    condition_aggregates (Sequence[str]): List of aggregates used in the condition
    aliases (Dict[str, Alias]): Endpoint specific aliases
    """

    def __init__(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
        conditions: list[Any] | None = None,
        having: Sequence[Condition] | None = None,
        user_id: int | None = None,
        organization_id: int | None = None,
        team_id: Sequence[int] | None = None,
        project_ids: Sequence[int] | None = None,
        group_ids: Sequence[int] | None = None,
        event_ids: Sequence[str] | None = None,
        selected_columns: Sequence[str] | None = None,
        aggregations: Sequence[str] | None = None,
        rollup: int | None = None,
        groupby: Sequence[str] | None = None,
        orderby: Sequence[str] | None = None,
        condition_aggregates: Sequence[str] | None = None,
        aliases: Mapping[str, Any] | None = None,
    ) -> None:
        self.start = start
        self.end = end
        self.conditions = conditions or []
        self.having = having or []
        self.user_id = user_id
        self.organization_id = organization_id
        self.team_id = team_id
        self.project_ids = project_ids
        self.group_ids = group_ids
        self.event_ids = event_ids or []

        self.rollup = rollup
        self.selected_columns = selected_columns if selected_columns is not None else []
        self.aggregations = aggregations if aggregations is not None else []
        self.groupby = groupby
        self.orderby = orderby
        self.condition_aggregates = condition_aggregates
        self.aliases = aliases

    @property
    def filter_keys(self) -> dict[str, Any]:
        """
        Get filter_keys value required for raw snuba query
        """
        filter_keys: dict[str, Any] = {}

        if self.project_ids:
            filter_keys["project_id"] = self.project_ids

        if self.group_ids:
            filter_keys["group_id"] = self.group_ids

        if self.event_ids:
            filter_keys["event_id"] = self.event_ids

        return filter_keys

    @property
    def params(self) -> dict[str, Any]:
        """
        Get the datetime parameters as a dictionary
        """
        return {
            "start": self.start,
            "end": self.end,
            "user_id": self.user_id,
            "organization_id": self.organization_id,
            # needed for the team key transaction column
            "team_id": self.team_id,
            "project_id": self.project_ids,
        }

    def update_with(self, updates: dict[str, Any]) -> None:
        keys = ("selected_columns", "aggregations", "conditions", "orderby", "groupby", "rollup")
        for key in keys:
            if key in updates:
                setattr(self, key, updates[key])

    def clone(self) -> Self:
        return deepcopy(self)


class EventStorage(Service):
    __all__ = (
        "minimal_columns",
        "create_event",
        "get_event_by_id",
        "get_events",
        "get_events_snql",
        "get_unfetched_events",
        "get_adjacent_event_ids",
        "get_adjacent_event_ids_snql",
        "bind_nodes",
        "get_unfetched_transactions",
    )

    # The minimal list of columns we need to get from snuba to bootstrap an
    # event. If the client is planning on loading the entire event body from
    # nodestore anyway, we may as well only fetch the minimum from snuba to
    # avoid duplicated work.
    minimal_columns = {
        Dataset.Events: [Columns.EVENT_ID, Columns.GROUP_ID, Columns.PROJECT_ID, Columns.TIMESTAMP],
        Dataset.Transactions: [
            Columns.EVENT_ID,
            Columns.GROUP_IDS,
            Columns.PROJECT_ID,
            Columns.TIMESTAMP,
        ],
        Dataset.IssuePlatform: [
            Columns.EVENT_ID,
            Columns.GROUP_ID,
            Columns.PROJECT_ID,
            Columns.TIMESTAMP,
            Columns.OCCURRENCE_ID,
        ],
    }

    def get_events(
        self,
        filter: Filter,
        orderby: Sequence[str] | None = None,
        limit: int = 100,
        offset: int = 0,
        referrer: str = "eventstore.get_events",
        dataset: Dataset = Dataset.Events,
        tenant_ids: Mapping[str, Any] | None = None,
    ) -> list[Event]:
        """
        Fetches a list of events given a set of criteria.

        Searches for error events, including security and default messages, but not for
        transaction events. Returns an empty list if no events match the filter.

        Arguments:
        snuba_filter (Filter): Filter
        orderby (Sequence[str]): List of fields to order by - default ['-time', '-event_id']
        limit (int): Query limit - default 100
        offset (int): Query offset - default 0
        referrer (string): Referrer - default "eventstore.get_events"
        """
        raise NotImplementedError

    def get_events_snql(
        self,
        organization_id: int,
        group_id: int,
        start: datetime | None,
        end: datetime | None,
        conditions: Sequence[Condition],
        orderby: Sequence[str],
        limit: int = 100,
        offset: int = 0,
        referrer: str = "eventstore.get_events_snql",
        dataset: Dataset = Dataset.Events,
        tenant_ids: Mapping[str, Any] | None = None,
    ) -> list[Event]:
        raise NotImplementedError

    def get_unfetched_events(
        self,
        filter: Filter,
        orderby: Sequence[str] | None = None,
        limit: int = 100,
        offset: int = 0,
        referrer: str = "eventstore.get_unfetched_events",
        dataset: Dataset = Dataset.Events,
        tenant_ids: Mapping[str, Any] | None = None,
    ) -> list[Event]:
        """
        Same as get_events but returns events without their node datas loaded.
        Only the event ID, projectID, groupID and timestamp field will be present without
        an additional fetch to nodestore.

        Used for fetching large volumes of events that do not need data loaded
        from nodestore. Currently this is just used for event data deletions where
        we just need the event IDs in order to process the deletions.

        Arguments:
        snuba_filter (Filter): Filter
        orderby (Sequence[str]): List of fields to order by - default ['-time', '-event_id']
        limit (int): Query limit - default 100
        offset (int): Query offset - default 0
        referrer (string): Referrer - default "eventstore.get_unfetched_events"
        """
        raise NotImplementedError

    @overload
    def get_event_by_id(
        self,
        project_id: int,
        event_id: str,
        group_id: int | None = None,
        tenant_ids: Mapping[str, Any] | None = None,
        occurrence_id: str | None = None,
        *,
        skip_transaction_groupevent: Literal[True],
    ) -> Event | None: ...

    @overload
    def get_event_by_id(
        self,
        project_id: int,
        event_id: str,
        group_id: int | None = None,
        tenant_ids: Mapping[str, Any] | None = None,
        occurrence_id: str | None = None,
        *,
        skip_transaction_groupevent: bool = False,
    ) -> Event | GroupEvent | None: ...

    def get_event_by_id(
        self,
        project_id: int,
        event_id: str,
        group_id: int | None = None,
        tenant_ids: Mapping[str, Any] | None = None,
        occurrence_id: str | None = None,
        *,
        skip_transaction_groupevent: bool = False,
    ) -> Event | GroupEvent | None:
        """
        Gets a single event of any event type given a project_id and event_id.
        Returns None if an event cannot be found.

        Arguments:
        project_id (int): Project ID
        event_id (str): Event ID
        group_id (Optional[int]): If the group ID for this event is already known, pass
            it here to save one Snuba query.
        """
        raise NotImplementedError

    def get_adjacent_event_ids_snql(
        self,
        organization_id: int,
        project_id: int,
        group_id: int | None,
        environments: Sequence[str],
        event: Event | GroupEvent,
        start: datetime | None = None,
        end: datetime | None = None,
        conditions: list[Any] | None = None,
    ) -> list[tuple[str, str] | None]:
        raise NotImplementedError

    def get_adjacent_event_ids(
        self, event: Event | GroupEvent, filter: Filter
    ) -> tuple[tuple[str, str] | None, tuple[str, str] | None]:
        """
        Gets the previous and next event IDs given a current event and some conditions/filters.
        Returns a tuple of (project_id, event_id) for (prev_ids, next_ids)

        Arguments:
        event (Event): Event object
        snuba_filter (Filter): Filter
        """
        raise NotImplementedError

    def create_event(
        self,
        *,
        project_id: int,
        event_id: str | None = None,
        group_id: int | None = None,
        data: Mapping[str, Any] | None = None,
    ) -> Event:
        """
        Returns an Event from processed data
        """
        return Event(
            project_id=project_id,
            event_id=event_id or str(uuid.uuid4()),
            group_id=group_id,
            data=data,
        )

    def bind_nodes(self, object_list: Sequence[Event]) -> None:
        """
        For a list of Event objects, and a property name where we might find an
        (unfetched) NodeData on those objects, fetch all the data blobs for
        those NodeDatas with a single multi-get command to nodestore, and bind
        the returned blobs to the NodeDatas.

        It's not necessary to bind a single Event object since data will be lazily
        fetched on any attempt to access a property.
        """
        sentry_sdk.set_tag("eventstore.backend", "nodestore")

        with sentry_sdk.start_span(op="eventstore.base.bind_nodes"):
            object_node_list = [(i, i.data) for i in object_list if i.data.id]

            # Remove duplicates from the list of nodes to be fetched
            node_ids = list({n.id for _, n in object_node_list})
            if not node_ids:
                return

            node_results = nodestore.backend.get_multi(node_ids)

            for item, node in object_node_list:
                data = node_results.get(node.id) or {}
                node.bind_data(data, ref=node.get_ref(item))

    def get_unfetched_transactions(
        self,
        snuba_filter: Filter,
        orderby: Sequence[str] | None = None,
        limit: int = 100,
        offset: int = 0,
        referrer: str = "eventstore.get_unfetched_transactions",
        tenant_ids: Mapping[str, Any] | None = None,
    ) -> list[Event]:
        """
        Same as get_unfetched_events but returns transactions.
        Only the event ID, projectID and timestamp field will be present without
        an additional fetch to nodestore.

        Used for fetching large volumes of transactions that do not need data
        loaded from nodestore. Currently this is just used for transaction
        data deletions where we just need the transactions IDs in order to
        process the deletions.

        Arguments:
        snuba_filter (Filter): Filter
        orderby (Sequence[str]): List of fields to order by - default ['-time', '-event_id']
        limit (int): Query limit - default 100
        offset (int): Query offset - default 0
        referrer (string): Referrer - default "eventstore.get_unfetched_transactions"
        """
        raise NotImplementedError
