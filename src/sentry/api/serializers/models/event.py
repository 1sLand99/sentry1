from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any, TypedDict

import sentry_sdk
import sqlparse
from django.contrib.auth.models import AnonymousUser
from sentry_relay.processing import meta_with_chunks

from sentry.api.serializers import Serializer, register, serialize
from sentry.api.serializers.models.release import GroupEventReleaseSerializer
from sentry.api.serializers.models.userreport import UserReportSerializerResponse
from sentry.api.serializers.types import GroupEventReleaseSerializerResponse
from sentry.eventstore.models import Event, GroupEvent
from sentry.interfaces.user import EventUserApiContext
from sentry.models.eventattachment import EventAttachment
from sentry.models.eventerror import EventError
from sentry.models.release import Release
from sentry.models.userreport import UserReport
from sentry.sdk_updates import SdkSetupState, get_suggested_updates
from sentry.search.utils import convert_user_tag_to_query, map_device_class_level
from sentry.stacktraces.processing import find_stacktraces_in_data
from sentry.users.models.user import User
from sentry.users.services.user.model import RpcUser
from sentry.utils.json import prune_empty_keys
from sentry.utils.safe import get_path

CRASH_FILE_TYPES = {"event.minidump"}
RESERVED_KEYS = frozenset(["user", "sdk", "device", "contexts"])

FORMATTED_BREADCRUMB_CATEGORIES = frozenset(["query", "sql.query"])
FORMATTED_SPAN_OPS = frozenset(["db", "db.query", "db.sql.query"])
SQL_DOUBLEQUOTES_REGEX = re.compile(r"\"([a-zA-Z0-9_]+?)\"")
MAX_SQL_FORMAT_OPS = 20
MAX_SQL_FORMAT_LENGTH = 1500


class EventTagOptional(TypedDict, total=False):
    query: str


class EventTag(EventTagOptional):
    key: str
    value: str


def get_crash_files(events):
    event_ids = [x.event_id for x in events if x.platform == "native"]
    if event_ids:
        return [
            ea
            for ea in EventAttachment.objects.filter(event_id__in=event_ids)
            if ea.type in CRASH_FILE_TYPES
        ]
    return []


def get_tags_with_meta(event) -> tuple[list[EventTag], dict[str, Any] | None]:
    meta = get_path(event.data, "_meta", "tags") or {}

    # If we have meta, we need to get the tags in their original order
    # from the raw event body as the indexes need to line up with the
    # metadata indexes. In other cases we can use event.tags
    if meta:
        raw_tags = event.data.get("tags") or []
    else:
        raw_tags = event.tags

    tags_and_meta: list[tuple[EventTag, dict[str, str] | None]] = sorted(
        (
            (
                {
                    "key": kv[0] and kv[0].split("sentry:", 1)[-1],
                    "value": kv[1],
                },
                prune_empty_keys(
                    {
                        "key": get_path(meta, str(i), "0"),
                        "value": get_path(meta, str(i), "1"),
                    }
                )
                or None,
            )
            for i, kv in enumerate(raw_tags)
            if kv is not None
        ),
        key=lambda x: x[0]["key"] if x[0]["key"] is not None else "",
    )

    # Add 'query' for each tag to tell the UI what to use as query
    # params for this tag.
    tags = [tag for tag, _ in tags_and_meta]
    for tag in tags:
        query = convert_user_tag_to_query(tag["key"], tag["value"])
        if query:
            tag["query"] = query
    map_device_class_tags(tags)

    tags_meta = prune_empty_keys({str(i): meta for i, (_, meta) in enumerate(tags_and_meta)})

    return tags, meta_with_chunks(tags, tags_meta)


def get_entries(event: Event | GroupEvent, user: User, is_public: bool = False):
    # XXX(dcramer): These are called entries for future-proofing
    platform = event.platform
    meta = event.data.get("_meta") or {}
    interface_list = []

    for key, interface in event.interfaces.items():
        # we treat user as a special contextual item
        if key in RESERVED_KEYS:
            continue

        data = interface.get_api_context(is_public=is_public, platform=platform)
        # data might not be returned for e.g. a public HTTP repr
        # However, spans can be an empty list and should still be included.
        if not data and interface.path != "spans":
            continue

        entry = {"data": data, "type": interface.external_type}

        api_meta = None
        if meta.get(key):
            api_meta = interface.get_api_meta(meta[key], is_public=is_public, platform=platform)
            api_meta = meta_with_chunks(data, api_meta)

        interface_list.append((interface, entry, api_meta))

    interface_list.sort(key=lambda x: x[0].get_display_score(), reverse=True)

    return (
        [i[1] for i in interface_list],
        {k: {"data": i[2]} for k, i in enumerate(interface_list) if i[2]},
    )


class BaseEventSerializerResponse(TypedDict):
    id: str
    groupID: str | None
    eventID: str
    projectID: str
    message: str | None
    title: str
    location: str | None
    user: EventUserApiContext | None
    tags: list[EventTag]
    platform: str
    dateReceived: datetime | None
    contexts: dict[str, Any] | None
    size: int | None
    entries: list[Any]
    dist: str | None
    sdk: dict[str, str]
    context: dict[str, Any] | None
    packages: dict[str, Any]
    type: str
    metadata: Any
    errors: list[Any]
    occurrence: Any
    _meta: dict[str, Any]


class ErrorEventFields(TypedDict, total=False):
    crashFile: str | None
    culprit: str | None
    dateCreated: datetime
    fingerprints: list[str]
    groupingConfig: Any


class TransactionEventFields(TypedDict, total=False):
    startTimestamp: datetime
    endTimestamp: datetime
    measurements: Any
    breakdowns: Any


class EventSerializerResponse(
    BaseEventSerializerResponse, ErrorEventFields, TransactionEventFields
):
    pass


class SqlFormatEventSerializerResponse(EventSerializerResponse):
    release: GroupEventReleaseSerializerResponse | None


class IssueEventSerializerResponse(SqlFormatEventSerializerResponse):
    userReport: UserReportSerializerResponse | None
    sdkUpdates: list[dict[str, Any]]
    resolvedWith: list[str]


@register(GroupEvent)
@register(Event)
class EventSerializer(Serializer):
    def _get_interface_with_meta(self, event, name, is_public=False):
        interface = event.get_interface(name)
        if not interface:
            return (None, None)

        platform = event.platform
        data = interface.get_api_context(is_public=is_public, platform=platform)
        event_meta = event.data.get("_meta") or {}
        if not data or not event_meta.get(name):
            return (data, None)

        api_meta = interface.get_api_meta(event_meta[name], is_public=is_public, platform=platform)
        # data might not be returned for e.g. a public HTTP repr
        if not api_meta:
            return (data, None)

        return (data, meta_with_chunks(data, api_meta))

    def _get_attr_with_meta(self, event, attr, default=None):
        value = event.data.get(attr, default)
        meta = get_path(event.data, "_meta", attr)
        return (value, meta_with_chunks(value, meta))

    def _get_legacy_message_with_meta(self, event):
        meta = event.data.get("_meta")

        message: str | None = get_path(event.data, "logentry", "formatted")
        msg_meta = get_path(meta, "logentry", "formatted")

        if not message:
            message = get_path(event.data, "logentry", "message")
            msg_meta = get_path(meta, "logentry", "message")

        if not message:
            message = event.message
            msg_meta = None

        return (message, meta_with_chunks(message, msg_meta))

    def _get_user_report(self, user, event):
        try:
            user_report = UserReport.objects.get(
                event_id=event.event_id, project_id=event.project_id
            )
        except UserReport.DoesNotExist:
            user_report = None
        return serialize(user_report, user)

    def get_attrs(self, item_list, user, **kwargs):
        is_public = kwargs.pop("is_public", False)
        crash_files = get_crash_files(item_list)
        serialized_files = {
            file.event_id: serialized
            for file, serialized in zip(crash_files, serialize(crash_files, user=user))
        }
        results: dict[Event | GroupEvent, dict[str, Any]] = defaultdict(dict)
        for item in item_list:
            # TODO(dcramer): convert to get_api_context
            (user_data, user_meta) = self._get_interface_with_meta(item, "user", is_public)
            (contexts_data, contexts_meta) = self._get_interface_with_meta(
                item, "contexts", is_public
            )
            (sdk_data, sdk_meta) = self._get_interface_with_meta(item, "sdk", is_public)

            (entries, entries_meta) = get_entries(item, user, is_public=is_public)

            results[item] = {
                "entries": entries,
                "user": user_data,
                "contexts": contexts_data or {},
                "sdk": sdk_data,
                "crash_file": serialized_files.get(item.event_id),
                "_meta": {
                    "entries": entries_meta,
                    "user": user_meta,
                    "contexts": contexts_meta,
                    "sdk": sdk_meta,
                },
            }
        return results

    def should_display_error(self, error):
        name = error.get("name")
        if not isinstance(name, str):
            return True

        return (
            not name.startswith("breadcrumbs.")
            and not name.startswith("extra.")
            and not name.startswith("tags.")
            and ".frames." not in name
        )

    def serialize(self, obj, attrs, user, **kwargs) -> EventSerializerResponse:
        from sentry.api.serializers.rest_framework import convert_dict_key_case, snake_to_camel_case

        errors = [
            EventError(error).get_api_context()
            for error in get_path(obj.data, "errors", filter=True, default=())
            # TODO(ja): Temporary workaround to hide certain normalization errors.
            # Remove this and the test in tests/sentry/api/serializers/test_event.py
            if self.should_display_error(error)
        ]

        (message, message_meta) = self._get_legacy_message_with_meta(obj)
        (tags, tags_meta) = get_tags_with_meta(obj)
        (context, context_meta) = self._get_attr_with_meta(obj, "extra", {})
        (packages, packages_meta) = self._get_attr_with_meta(obj, "modules", {})

        received_data = obj.data.get("received")
        received: datetime | None = None
        if received_data:
            # Sentry at one point attempted to record invalid types here.
            # Remove after June 2 2016
            try:
                received = datetime.fromtimestamp(received_data, timezone.utc)
            except TypeError:
                received = None

        occurrence = getattr(obj, "occurrence", None)

        event_data: EventSerializerResponse = {
            "id": obj.event_id,
            "groupID": str(obj.group_id) if obj.group_id else None,
            "eventID": obj.event_id,
            "projectID": str(obj.project_id),
            "size": obj.size,
            "entries": attrs["entries"],
            "dist": obj.dist,
            # See GH-3248
            "message": message,
            "title": obj.title,
            "location": obj.location,
            "user": attrs["user"],
            "contexts": attrs["contexts"],
            "sdk": attrs["sdk"],
            # TODO(dcramer): move into contexts['extra']
            "context": context,
            "packages": packages,
            "type": obj.get_event_type(),
            "metadata": obj.get_event_metadata(),
            "tags": tags,
            "platform": obj.platform,
            "dateReceived": received,
            "errors": errors,
            "occurrence": (
                convert_dict_key_case(occurrence.to_dict(), snake_to_camel_case)
                if occurrence
                else None
            ),
            "_meta": {
                "entries": attrs["_meta"]["entries"],
                "message": message_meta,
                "user": attrs["_meta"]["user"],
                "contexts": attrs["_meta"]["contexts"],
                "sdk": attrs["_meta"]["sdk"],
                "context": context_meta,
                "packages": packages_meta,
                "tags": tags_meta,
            },
        }
        # Serialize attributes that are specific to different types of events.
        if obj.get_event_type() == "transaction":
            return {
                **event_data,
                **self.__serialize_transaction_attrs(attrs, obj),
            }
        else:
            return {
                **event_data,
                **self.__serialize_error_attrs(attrs, obj),
            }

    def __serialize_transaction_attrs(self, attrs, obj) -> TransactionEventFields:
        """
        Add attributes that are only present on transaction events.
        """
        transaction_attrs: TransactionEventFields = {
            "startTimestamp": obj.data.get("start_timestamp"),
            "endTimestamp": obj.data.get("timestamp"),
            "measurements": obj.data.get("measurements"),
            "breakdowns": obj.data.get("breakdowns"),
        }

        return transaction_attrs

    def __serialize_error_attrs(self, attrs, obj) -> ErrorEventFields:
        """
        Add attributes that are present on error and default event types
        """
        return {
            "crashFile": attrs["crash_file"],
            "culprit": obj.culprit,
            "dateCreated": obj.datetime,
            "fingerprints": obj.get_hashes(),
            "groupingConfig": obj.get_grouping_config(),
        }


class SqlFormatEventSerializer(EventSerializer):
    """
    Applies formatting to SQL queries in the serialized event.
    """

    def __init__(self) -> None:
        super().__init__()
        self.formatted_sql_cache: dict[str, str] = {}

    def get_attrs(self, item_list, user, **kwargs):
        is_public = kwargs.pop("is_public", False)
        return super().get_attrs(item_list, user, is_public=is_public)

    # Various checks to ensure that we don't spend too much time formatting
    def _should_skip_formatting(self, query: str):
        if (
            (not query)
            | (len(self.formatted_sql_cache) >= MAX_SQL_FORMAT_OPS)
            | (len(query) > MAX_SQL_FORMAT_LENGTH)
        ):
            return True

        return False

    def _remove_doublequotes(self, message: str) -> str:
        return SQL_DOUBLEQUOTES_REGEX.sub(r"\1", message)

    def _format_sql_query(self, message: str) -> str | None:
        formatted = self.formatted_sql_cache.get(message, None)
        if formatted is not None:
            return formatted
        if self._should_skip_formatting(message):
            return message

        formatted = sqlparse.format(message, reindent=True, wrap_after=80)
        if formatted != message:
            formatted = self._remove_doublequotes(formatted)
        self.formatted_sql_cache[message] = formatted

        return formatted

    def _format_breadcrumb_messages(
        self, event_data: EventSerializerResponse, event: Event | GroupEvent, user: User
    ) -> EventSerializerResponse:
        try:
            breadcrumbs = next(
                filter(lambda entry: entry["type"] == "breadcrumbs", event_data.get("entries", ())),
                None,
            )

            if not breadcrumbs:
                return event_data

            for breadcrumb_item in breadcrumbs.get("data", {}).get("values", ()):
                breadcrumb_message = breadcrumb_item.get("message")
                breadcrumb_category = breadcrumb_item.get("category")
                if breadcrumb_category in FORMATTED_BREADCRUMB_CATEGORIES and breadcrumb_message:
                    breadcrumb_item["messageFormat"] = "sql"
                    breadcrumb_item["messageRaw"] = breadcrumb_message
                    breadcrumb_item["message"] = self._format_sql_query(breadcrumb_message)

            return event_data
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            return event_data

    def _get_release_info(
        self, user, event, include_full_release_data: bool
    ) -> GroupEventReleaseSerializerResponse | None:
        version = event.get_tag("sentry:release")
        if not version:
            return None
        try:
            release = Release.objects.get(
                projects=event.project,
                organization_id=event.project.organization_id,
                version=version,
            )
        except Release.DoesNotExist:
            return {"version": version}
        if include_full_release_data:
            return serialize(release, user)
        else:
            return serialize(release, user, GroupEventReleaseSerializer())

    def _format_db_spans(
        self, event_data: EventSerializerResponse, event: Event | GroupEvent, user: User
    ) -> EventSerializerResponse:
        try:
            spans = next(
                filter(lambda entry: entry["type"] == "spans", event_data.get("entries", ())),
                None,
            )

            if not spans:
                return event_data

            for span in spans.get("data", ()):
                span_description = span.get("description")
                if span.get("op") in FORMATTED_SPAN_OPS and span_description:
                    span["description"] = self._format_sql_query(span_description)

            return event_data
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            return event_data

    def serialize(self, obj, attrs, user, **kwargs) -> SqlFormatEventSerializerResponse:
        include_full_release_data = kwargs.pop("include_full_release_data", False)
        result = super().serialize(obj, attrs, user, **kwargs)

        with sentry_sdk.start_span(op="serialize", name="Format SQL"):
            result = self._format_breadcrumb_messages(result, obj, user)
            result = self._format_db_spans(result, obj, user)
            release_info = self._get_release_info(user, obj, include_full_release_data)

        return {**result, "release": release_info}


class IssueEventSerializer(SqlFormatEventSerializer):
    """
    Adds release, user report, sdk updates, and perf issue info to the event.
    """

    def get_attrs(
        self,
        item_list: Sequence[Event | GroupEvent],
        user: User | RpcUser | AnonymousUser,
        **kwargs,
    ):
        is_public = kwargs.pop("is_public", False)
        return super().get_attrs(item_list, user, is_public=is_public, **kwargs)

    def _get_sdk_updates(self, obj):
        return list(get_suggested_updates(SdkSetupState.from_event_json(obj.data)))

    def _get_resolved_with(self, obj: Event) -> list[str]:
        stacktraces = find_stacktraces_in_data(obj.data)

        frame_lists = [stacktrace.get_frames() for stacktrace in stacktraces]
        frame_data = [frame.get("data") for frame_list in frame_lists for frame in frame_list]

        unique_resolution_methods = {
            frame.get("resolved_with") for frame in frame_data if frame is not None
        }

        return list(unique_resolution_methods)

    def serialize(self, obj, attrs, user, **kwargs) -> IssueEventSerializerResponse:
        result = super().serialize(obj, attrs, user, **kwargs)

        return {
            **result,
            "userReport": self._get_user_report(user, obj),
            "sdkUpdates": self._get_sdk_updates(obj),
            "resolvedWith": self._get_resolved_with(obj),
        }


class SharedEventSerializer(EventSerializer):
    def get_attrs(self, item_list, user, **kwargs):
        return super().get_attrs(item_list, user, is_public=True, **kwargs)

    def serialize(self, obj, attrs, user, **kwargs):
        base = super().serialize(obj, attrs, user)
        result: dict[str, Any] = {
            k: v
            for k, v in base.items()
            if k not in {"context", "contexts", "user", "tags", "sdk", "errors"}
        }
        result["entries"] = [e for e in result["entries"] if e["type"] != "breadcrumbs"]
        return result


SimpleEventSerializerResponse = TypedDict(
    "SimpleEventSerializerResponse",
    {
        "id": str,
        "event.type": str,
        "groupID": str | None,
        "eventID": str,
        "projectID": str,
        "message": str,
        "title": str,
        "location": str | None,
        "culprit": str | None,
        "user": EventUserApiContext | None,
        "tags": list[EventTag],
        "platform": str | None,
        "dateCreated": datetime,
        "crashFile": str | None,
        "metadata": dict[str, Any] | None,
    },
)


class SimpleEventSerializer(EventSerializer):
    """
    Simple event serializer that renders a basic outline of an event without
    most interfaces/breadcrumbs. This can be used for basic event list queries
    where we don't need the full detail. The side effect is that, if the
    serialized events are actually SnubaEvents, we can render them without
    needing to fetch the event bodies from nodestore.

    NB it would be super easy to inadvertently add a property accessor here
    that would require a nodestore lookup for a SnubaEvent serialized using
    this serializer. You will only really notice you've done this when the
    organization event search API gets real slow.
    """

    def get_attrs(self, item_list, user, **kwargs):
        crash_files = get_crash_files(item_list)
        serialized_files = {
            file.event_id: serialized
            for file, serialized in zip(crash_files, serialize(crash_files, user=user))
        }
        return {event: {"crash_file": serialized_files.get(event.event_id)} for event in item_list}

    def serialize(  # type: ignore[override]  # intentionally different shape
        self, obj: Event | GroupEvent, attrs, user, **kwargs
    ) -> SimpleEventSerializerResponse:
        tags: list[EventTag] = [
            {"key": key.split("sentry:", 1)[-1], "value": value} for key, value in obj.tags
        ]
        for tag in tags:
            query = convert_user_tag_to_query(tag["key"], tag["value"])
            if query:
                tag["query"] = query
        map_device_class_tags(tags)

        event_user = obj.get_minimal_user()

        return {
            "id": str(obj.event_id),
            "event.type": str(obj.get_event_type()),
            "groupID": str(obj.group_id) if obj.group_id else None,
            "eventID": str(obj.event_id),
            "projectID": str(obj.project_id),
            # XXX for 'message' this doesn't do the proper resolution of logentry
            # etc. that _get_legacy_message_with_meta does.
            "message": obj.message,
            "title": obj.title,
            "location": obj.location,
            "culprit": obj.culprit,
            "user": event_user.get_api_context() if event_user is not None else None,
            "tags": tags,
            "platform": obj.platform,
            "dateCreated": obj.datetime,
            # Needed to generate minidump links in UI
            "crashFile": attrs["crash_file"],
            "metadata": obj.get_event_metadata(),
        }


class ExternalEventSerializer(EventSerializer):
    """
    Event serializer for the minimum event data needed to send to an external service. This
    should be used for Integrations that need to include event data.
    """

    def serialize(self, obj, attrs, user, **kwargs):
        from sentry.notifications.utils import get_notification_group_title

        tags = [{"key": key.split("sentry:", 1)[-1], "value": value} for key, value in obj.tags]
        for tag in tags:
            query = convert_user_tag_to_query(tag["key"], tag["value"])
            if query:
                tag["query"] = query
        map_device_class_tags(tags)

        user = obj.get_minimal_user()

        return {
            "groupID": str(obj.group_id) if obj.group_id else None,
            "eventID": str(obj.event_id),
            "project": str(obj.project_id),
            # XXX for 'message' this doesn't do the proper resolution of logentry
            # etc. that _get_legacy_message_with_meta does.
            "message": obj.message,
            "title": get_notification_group_title(obj.group, obj, 1024),
            "location": obj.location,
            "culprit": obj.culprit,
            "user": user and user.get_api_context(),
            "tags": tags,
            "platform": obj.platform,
            "datetime": obj.datetime.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        }


def map_device_class_tags(tags):
    """
    If device.class tag exists, set the value to high, medium, low
    """
    for tag in tags:
        if tag["key"] == "device.class":
            if device_class := map_device_class_level(tag["value"]):
                tag["value"] = device_class
    return tags
