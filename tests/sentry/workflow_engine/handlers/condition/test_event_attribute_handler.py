from unittest.mock import MagicMock, patch

import pytest
from jsonschema import ValidationError

from sentry.eventstream.base import GroupState
from sentry.rules.conditions.event_attribute import EventAttributeCondition, attribute_registry
from sentry.rules.filters.event_attribute import EventAttributeFilter
from sentry.rules.match import MatchType
from sentry.utils.registry import NoRegistrationExistsError
from sentry.workflow_engine.models.data_condition import Condition
from sentry.workflow_engine.types import WorkflowEventData
from tests.sentry.workflow_engine.handlers.condition.test_base import ConditionTestCase


class TestEventAttributeCondition(ConditionTestCase):
    condition = Condition.EVENT_ATTRIBUTE
    payload = {
        "id": EventAttributeCondition.id,
        "match": MatchType.EQUAL,
        "value": "php",
        "attribute": "platform",
    }

    def get_event(self, **kwargs):
        data = {
            "message": "hello world",
            "request": {"method": "GET", "url": "http://example.com/"},
            "user": {
                "id": "1",
                "ip_address": "127.0.0.1",
                "email": "foo@example.com",
                "username": "foo",
            },
            "exception": {
                "values": [
                    {
                        "type": "SyntaxError",
                        "value": "hello world",
                        "stacktrace": {
                            "frames": [
                                {
                                    "filename": "example.php",
                                    "module": "example",
                                    "context_line": 'echo "hello";',
                                    "abs_path": "path/to/example.php",
                                }
                            ]
                        },
                        "thread_id": 1,
                    }
                ]
            },
            "tags": [("environment", "production")],
            "extra": {"foo": {"bar": "baz"}, "biz": ["baz"], "bar": "foo"},
            "platform": "php",
            "sdk": {"name": "sentry.javascript.react", "version": "6.16.1"},
            "contexts": {
                "response": {
                    "type": "response",
                    "status_code": 500,
                },
                "device": {
                    "screen_width_pixels": 1920,
                    "screen_height_pixels": 1080,
                    "screen_dpi": 123,
                    "screen_density": 2.5,
                },
                "app": {
                    "in_foreground": True,
                },
                "unreal": {
                    "crash_type": "crash",
                },
                "os": {"distribution_name": "ubuntu", "distribution_version": "22.04"},
                "ota_updates": {
                    "channel": "production",
                    "runtime_version": "1.0.0",
                    "update_id": "123",
                },
            },
            "threads": {
                "values": [
                    {
                        "id": 1,
                        "main": True,
                    },
                ],
            },
        }
        data.update(kwargs)
        event = self.store_event(data, project_id=self.project.id)
        return event

    def setup_group_event_and_job(self):
        self.group_event = self.event.for_group(self.group)
        self.event_data = WorkflowEventData(
            event=self.group_event,
            group=self.group,
            group_state=GroupState(
                {
                    "id": 1,
                    "is_regression": False,
                    "is_new": False,
                    "is_new_group_environment": False,
                }
            ),
        )

    def error_setup(self):
        self.event = self.get_event(
            exception={
                "values": [
                    {
                        "type": "Generic",
                        "value": "hello world",
                        "mechanism": {"type": "UncaughtExceptionHandler", "handled": False},
                    }
                ],
            }
        )
        self.setup_group_event_and_job()

    def setUp(self) -> None:
        self.event = self.get_event()
        self.setup_group_event_and_job()
        self.dc = self.create_data_condition(
            type=self.condition,
            comparison={"match": MatchType.EQUAL, "attribute": "platform", "value": "php"},
            condition_result=True,
        )

    def test_dual_write(self) -> None:
        dcg = self.create_data_condition_group()
        dc = self.translate_to_data_condition(self.payload, dcg)

        assert dc.type == self.condition
        assert dc.comparison == {
            "match": MatchType.EQUAL,
            "value": "php",
            "attribute": "platform",
        }
        assert dc.condition_result is True
        assert dc.condition_group == dcg

        payload = {
            "id": EventAttributeCondition.id,
            "match": MatchType.IS_SET,
            "attribute": "platform",
        }
        dc = self.translate_to_data_condition(payload, dcg)

        assert dc.type == self.condition
        assert dc.comparison == {
            "match": MatchType.IS_SET,
            "attribute": "platform",
        }
        assert dc.condition_result is True
        assert dc.condition_group == dcg

    def test_dual_write_filter(self) -> None:
        self.payload["id"] = EventAttributeFilter.id
        dcg = self.create_data_condition_group()
        dc = self.translate_to_data_condition(self.payload, dcg)

        assert dc.type == self.condition
        assert dc.comparison == {
            "match": MatchType.EQUAL,
            "value": "php",
            "attribute": "platform",
        }
        assert dc.condition_result is True
        assert dc.condition_group == dcg

    def test_json_schema(self) -> None:
        self.dc.comparison.update(
            {"match": MatchType.EQUAL, "attribute": "platform", "value": "php"}
        )
        self.dc.save()

        self.dc.comparison.update(
            {"match": "invalid_match", "attribute": "platform", "value": "php"}
        )
        with pytest.raises(ValidationError):
            self.dc.save()

        self.dc.comparison.update({"match": MatchType.EQUAL, "attribute": 0, "value": "php"})
        with pytest.raises(ValidationError):
            self.dc.save()

        self.dc.comparison.update(
            {"match": MatchType.EQUAL, "attribute": "platform", "value": 2000}
        )
        with pytest.raises(ValidationError):
            self.dc.save()

        self.dc.comparison.update({"attribute": "platform", "value": 2000})
        with pytest.raises(ValidationError):
            self.dc.save()

        self.dc.comparison.update({"match": MatchType.EQUAL, "value": 2000})
        with pytest.raises(ValidationError):
            self.dc.save()

        self.dc.comparison.update({"match": MatchType.EQUAL, "attribute": "platform"})
        with pytest.raises(ValidationError):
            self.dc.save()

        self.dc.comparison.update(
            {"match": MatchType.EQUAL, "attribute": "platform", "value": 2000, "extra": "extra"}
        )
        with pytest.raises(ValidationError):
            self.dc.save()

        self.dc.comparison.update(
            {"match": MatchType.IS_SET, "attribute": "platform", "value": 2000}
        )
        with pytest.raises(ValidationError):
            self.dc.save()

        self.dc.comparison.update({"match": MatchType.EQUAL, "attribute": "asdf", "value": 2000})
        with pytest.raises(ValidationError):
            self.dc.save()

    def test_not_in_registry(self) -> None:
        with pytest.raises(NoRegistrationExistsError):
            attribute_registry.get("transaction")
        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "transaction",
                "value": "asdf",
            }
        )
        self.assert_does_not_pass(self.dc, self.event_data)

    def test_equals(self) -> None:
        self.dc.comparison.update(
            {"match": MatchType.EQUAL, "attribute": "platform", "value": "php"}
        )
        self.assert_passes(self.dc, self.event_data)

        self.dc.comparison.update(
            {"match": MatchType.EQUAL, "attribute": "platform", "value": "python"}
        )
        self.assert_does_not_pass(self.dc, self.event_data)

    def test_not_equals(self) -> None:
        self.dc.comparison.update(
            {"match": MatchType.NOT_EQUAL, "attribute": "platform", "value": "php"}
        )
        self.assert_does_not_pass(self.dc, self.event_data)

        self.dc.comparison.update(
            {
                "match": MatchType.NOT_EQUAL,
                "attribute": "platform",
                "value": "python",
            }
        )
        self.assert_passes(self.dc, self.event_data)

    def test_starts_with(self) -> None:
        self.dc.comparison.update(
            {
                "match": MatchType.STARTS_WITH,
                "attribute": "platform",
                "value": "ph",
            }
        )
        self.assert_passes(self.dc, self.event_data)

        self.dc.comparison.update(
            {
                "match": MatchType.STARTS_WITH,
                "attribute": "platform",
                "value": "py",
            }
        )
        self.assert_does_not_pass(self.dc, self.event_data)

    def test_does_not_start_with(self) -> None:
        self.dc.comparison.update(
            {
                "match": MatchType.NOT_STARTS_WITH,
                "attribute": "platform",
                "value": "ph",
            }
        )
        self.assert_does_not_pass(self.dc, self.event_data)

        self.dc.comparison.update(
            {
                "match": MatchType.NOT_STARTS_WITH,
                "attribute": "platform",
                "value": "py",
            }
        )
        self.assert_passes(self.dc, self.event_data)

    def test_ends_with(self) -> None:
        self.dc.comparison.update(
            {"match": MatchType.ENDS_WITH, "attribute": "platform", "value": "hp"}
        )
        self.assert_passes(self.dc, self.event_data)

        self.dc.comparison.update(
            {
                "match": MatchType.ENDS_WITH,
                "attribute": "platform",
                "value": "thon",
            }
        )
        self.assert_does_not_pass(self.dc, self.event_data)

    def test_does_not_end_with(self) -> None:
        self.dc.comparison.update(
            {
                "match": MatchType.NOT_ENDS_WITH,
                "attribute": "platform",
                "value": "hp",
            }
        )
        self.assert_does_not_pass(self.dc, self.event_data)

        self.dc.comparison.update(
            {
                "match": MatchType.NOT_ENDS_WITH,
                "attribute": "platform",
                "value": "thon",
            }
        )
        self.assert_passes(self.dc, self.event_data)

    def test_contains(self) -> None:
        self.dc.comparison.update(
            {"match": MatchType.CONTAINS, "attribute": "platform", "value": "p"}
        )
        self.assert_passes(self.dc, self.event_data)

        self.dc.comparison.update(
            {"match": MatchType.CONTAINS, "attribute": "platform", "value": "z"}
        )
        self.assert_does_not_pass(self.dc, self.event_data)

    def test_contains_message(self) -> None:
        self.dc.comparison.update(
            {"match": MatchType.CONTAINS, "attribute": "message", "value": "hello"}
        )
        self.assert_passes(self.dc, self.event_data)

        # Validate that this searches message in the same way that snuba does
        self.event = self.get_event(message="")
        self.setup_group_event_and_job()
        # This should still pass, even though the message is now empty
        self.dc.comparison.update(
            {"match": MatchType.CONTAINS, "attribute": "message", "value": "hello"}
        )
        self.assert_passes(self.dc, self.event_data)

        # The search should also include info from the exception if present
        self.dc.comparison.update(
            {
                "match": MatchType.CONTAINS,
                "attribute": "message",
                "value": "SyntaxError",
            }
        )
        self.assert_passes(self.dc, self.event_data)

        self.dc.comparison.update(
            {
                "match": MatchType.CONTAINS,
                "attribute": "message",
                "value": "not present",
            }
        )
        self.assert_does_not_pass(self.dc, self.event_data)

    def test_does_not_contain(self) -> None:
        self.dc.comparison.update(
            {
                "match": MatchType.NOT_CONTAINS,
                "attribute": "platform",
                "value": "p",
            }
        )
        self.assert_does_not_pass(self.dc, self.event_data)

        self.dc.comparison.update(
            {
                "match": MatchType.NOT_CONTAINS,
                "attribute": "platform",
                "value": "z",
            }
        )
        self.assert_passes(self.dc, self.event_data)

    def test_message(self) -> None:
        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "message",
                "value": "hello world",
            }
        )
        self.assert_passes(self.dc, self.event_data)

        self.dc.comparison.update(
            {"match": MatchType.EQUAL, "attribute": "message", "value": "php"}
        )
        self.assert_does_not_pass(self.dc, self.event_data)

    def test_environment(self) -> None:
        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "environment",
                "value": "production",
            }
        )
        self.assert_passes(self.dc, self.event_data)

        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "environment",
                "value": "staging",
            }
        )
        self.assert_does_not_pass(self.dc, self.event_data)

    def test_compares_case_insensitive(self) -> None:
        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "environment",
                "value": "PRODUCTION",
            }
        )
        self.assert_passes(self.dc, self.event_data)

    def test_compare_int_value(self) -> None:
        self.event.data["extra"]["number"] = 1
        self.setup_group_event_and_job()
        self.dc.comparison.update(
            {"match": MatchType.EQUAL, "attribute": "extra.number", "value": "1"}
        )
        self.assert_passes(self.dc, self.event_data)

    def test_http_method(self) -> None:
        self.dc.comparison.update(
            {"match": MatchType.EQUAL, "attribute": "http.method", "value": "GET"}
        )
        self.assert_passes(self.dc, self.event_data)

        self.dc.comparison.update(
            {"match": MatchType.EQUAL, "attribute": "http.method", "value": "POST"}
        )
        self.assert_does_not_pass(self.dc, self.event_data)

    def test_http_url(self) -> None:
        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "http.url",
                "value": "http://example.com/",
            }
        )
        self.assert_passes(self.dc, self.event_data)

        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "http.url",
                "value": "http://foo.com/",
            }
        )
        self.assert_does_not_pass(self.dc, self.event_data)

    def test_http_status_code(self) -> None:
        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "http.status_code",
                "value": "500",
            }
        )
        self.assert_passes(self.dc, self.event_data)

        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "http.status_code",
                "value": "400",
            }
        )
        self.assert_does_not_pass(self.dc, self.event_data)

    def test_user_id(self) -> None:
        self.dc.comparison.update({"match": MatchType.EQUAL, "attribute": "user.id", "value": "1"})
        self.assert_passes(self.dc, self.event_data)

        self.dc.comparison.update({"match": MatchType.EQUAL, "attribute": "user.id", "value": "2"})
        self.assert_does_not_pass(self.dc, self.event_data)

    def test_user_ip_address(self) -> None:
        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "user.ip_address",
                "value": "127.0.0.1",
            }
        )
        self.assert_passes(self.dc, self.event_data)

        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "user.ip_address",
                "value": "2",
            }
        )
        self.assert_does_not_pass(self.dc, self.event_data)

    def test_user_email(self) -> None:
        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "user.email",
                "value": "foo@example.com",
            }
        )
        self.assert_passes(self.dc, self.event_data)

        self.dc.comparison.update(
            {"match": MatchType.EQUAL, "attribute": "user.email", "value": "2"}
        )
        self.assert_does_not_pass(self.dc, self.event_data)

    def test_user_username(self) -> None:
        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "user.username",
                "value": "foo",
            }
        )
        self.assert_passes(self.dc, self.event_data)

        self.dc.comparison.update(
            {"match": MatchType.EQUAL, "attribute": "user.username", "value": "2"}
        )
        self.assert_does_not_pass(self.dc, self.event_data)

    def test_exception_type(self) -> None:
        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "exception.type",
                "value": "SyntaxError",
            }
        )
        self.assert_passes(self.dc, self.event_data)

        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "exception.type",
                "value": "TypeError",
            }
        )
        self.assert_does_not_pass(self.dc, self.event_data)

    @patch("sentry.eventstore.models.get_interfaces", return_value={})
    def test_exception_type_keyerror(self, mock_get_interfaces: MagicMock) -> None:
        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "exception.type",
                "value": "SyntaxError",
            }
        )
        self.assert_does_not_pass(self.dc, self.event_data)

    def test_error_handled(self) -> None:
        self.error_setup()
        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "error.handled",
                "value": "False",
            }
        )
        self.assert_passes(self.dc, self.event_data)

        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "error.handled",
                "value": "True",
            }
        )
        self.assert_does_not_pass(self.dc, self.event_data)

    def test_error_handled_not_defined(self) -> None:
        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "error.handled",
                "value": "True",
            }
        )
        self.assert_does_not_pass(self.dc, self.event_data)

    @patch("sentry.eventstore.models.get_interfaces", return_value={})
    def test_error_handled_keyerror(self, mock_get_interfaces: MagicMock) -> None:
        self.error_setup()
        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "error.handled",
                "value": "False",
            }
        )
        self.assert_does_not_pass(self.dc, self.event_data)

    def test_error_unhandled(self) -> None:
        self.error_setup()
        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "error.unhandled",
                "value": "True",
            }
        )
        self.assert_passes(self.dc, self.event_data)

        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "error.unhandled",
                "value": "False",
            }
        )
        self.assert_does_not_pass(self.dc, self.event_data)

    def test_exception_value(self) -> None:
        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "exception.value",
                "value": "hello world",
            }
        )
        self.assert_passes(self.dc, self.event_data)

        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "exception.value",
                "value": "foo bar",
            }
        )
        self.assert_does_not_pass(self.dc, self.event_data)

    def test_sdk_name(self) -> None:
        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "sdk.name",
                "value": "sentry.javascript.react",
            }
        )
        self.assert_passes(self.dc, self.event_data)

        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "sdk.name",
                "value": "sentry.python",
            }
        )
        self.assert_does_not_pass(self.dc, self.event_data)

    def test_stacktrace_filename(self) -> None:
        """Stacktrace.filename should match frames anywhere in the stack."""

        self.event = self.get_event(
            exception={
                "values": [
                    {
                        "type": "SyntaxError",
                        "value": "hello world",
                        "stacktrace": {
                            "frames": [
                                {"filename": "example.php", "module": "example"},
                                {"filename": "somecode.php", "module": "somecode"},
                                {"filename": "othercode.php", "module": "othercode"},
                            ]
                        },
                    }
                ]
            }
        )
        self.setup_group_event_and_job()

        # correctly matching filenames, at various locations in the stacktrace
        for value in ["example.php", "somecode.php", "othercode.php"]:
            self.dc.comparison.update(
                {
                    "match": MatchType.EQUAL,
                    "attribute": "stacktrace.filename",
                    "value": value,
                }
            )
            self.assert_passes(self.dc, self.event_data)

        # non-matching filename
        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "stacktrace.filename",
                "value": "foo.php",
            }
        )
        self.assert_does_not_pass(self.dc, self.event_data)

    def test_stacktrace_attributeerror(self) -> None:
        self.event = self.get_event(
            exception={
                "values": [
                    {
                        "type": "SyntaxError",
                        "value": "hello world",
                    }
                ]
            }
        )
        # hack to trigger attributeerror
        self.event.interfaces["exception"]._data["values"][0] = None
        self.setup_group_event_and_job()

        for value in ["example.php", "somecode.php", "othercode.php"]:
            self.dc.comparison.update(
                {
                    "match": MatchType.EQUAL,
                    "attribute": "stacktrace.filename",
                    "value": value,
                }
            )
            self.assert_does_not_pass(self.dc, self.event_data)

    def test_stacktrace_module(self) -> None:
        """Stacktrace.module should match frames anywhere in the stack."""

        self.event = self.get_event(
            exception={
                "values": [
                    {
                        "type": "SyntaxError",
                        "value": "hello world",
                        "stacktrace": {
                            "frames": [
                                {"filename": "example.php", "module": "example"},
                                {"filename": "somecode.php", "module": "somecode"},
                                {"filename": "othercode.php", "module": "othercode"},
                            ]
                        },
                    }
                ]
            }
        )
        self.setup_group_event_and_job()

        # correctly matching modules, at various locations in the stacktrace
        for value in ["example", "somecode", "othercode"]:
            self.dc.comparison.update(
                {
                    "match": MatchType.EQUAL,
                    "attribute": "stacktrace.module",
                    "value": value,
                }
            )
            self.assert_passes(self.dc, self.event_data)

        # non-matching module
        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "stacktrace.module",
                "value": "foo",
            }
        )
        self.assert_does_not_pass(self.dc, self.event_data)

    def test_stacktrace_code(self) -> None:
        """Stacktrace.code should match frames anywhere in the stack."""

        self.event = self.get_event(
            exception={
                "values": [
                    {
                        "type": "NameError",
                        "value": "name 'hi' is not defined",
                        "stacktrace": {
                            "frames": [
                                {
                                    "filename": "example.py",
                                    "module": "example",
                                    "function": "foo",
                                    "context_line": "somecode.bar()",
                                },
                                {
                                    "filename": "somecode.py",
                                    "module": "somecode",
                                    "function": "bar",
                                    "context_line": "othercode.baz()",
                                },
                                {
                                    "filename": "othercode.py",
                                    "module": "othercode",
                                    "function": "baz",
                                    "context_line": "hi()",
                                },
                            ]
                        },
                    }
                ]
            }
        )
        self.setup_group_event_and_job()

        # correctly matching code, at various locations in the stacktrace
        for value in ["somecode.bar()", "othercode.baz()", "hi()"]:
            self.dc.comparison.update(
                {
                    "match": MatchType.EQUAL,
                    "attribute": "stacktrace.code",
                    "value": value,
                }
            )
            self.assert_passes(self.dc, self.event_data)

        # non-matching code
        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "stacktrace.code",
                "value": "foo",
            }
        )
        self.assert_does_not_pass(self.dc, self.event_data)

    def test_stacktrace_abs_path(self) -> None:
        """Stacktrace.abs_path should match frames anywhere in the stack."""

        self.event = self.get_event(
            exception={
                "values": [
                    {
                        "type": "SyntaxError",
                        "value": "hello world",
                        "stacktrace": {
                            "frames": [
                                {
                                    "filename": "example.php",
                                    "module": "example",
                                    "abs_path": "path/to/example.php",
                                },
                                {
                                    "filename": "somecode.php",
                                    "module": "somecode",
                                    "abs_path": "path/to/somecode.php",
                                },
                                {
                                    "filename": "othercode.php",
                                    "module": "othercode",
                                    "abs_path": "path/to/othercode.php",
                                },
                            ]
                        },
                    }
                ]
            }
        )
        self.setup_group_event_and_job()

        # correctly matching abs_paths, at various locations in the stacktrace
        for value in ["path/to/example.php", "path/to/somecode.php", "path/to/othercode.php"]:
            self.dc.comparison.update(
                {
                    "match": MatchType.EQUAL,
                    "attribute": "stacktrace.abs_path",
                    "value": value,
                }
            )
            self.assert_passes(self.dc, self.event_data)

        # non-matching abs_path
        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "stacktrace.abs_path",
                "value": "path/to/foo.php",
            }
        )
        self.assert_does_not_pass(self.dc, self.event_data)

    def test_stacktrace_package(self) -> None:
        """Stacktrace.package should match frames anywhere in the stack."""

        self.event = self.get_event(
            exception={
                "values": [
                    {
                        "type": "SyntaxError",
                        "value": "hello world",
                        "stacktrace": {
                            "frames": [
                                {"filename": "example.php", "package": "package/example.lib"},
                                {
                                    "filename": "somecode.php",
                                    "package": "package/otherpackage.lib",
                                },
                                {
                                    "filename": "othercode.php",
                                    "package": "package/somepackage.lib",
                                },
                            ]
                        },
                    }
                ]
            }
        )
        self.setup_group_event_and_job()

        # correctly matching filenames, at various locations in the stacktrace
        for value in ["package/example.lib", "package/otherpackage.lib", "package/somepackage.lib"]:
            self.dc.comparison.update(
                {
                    "match": MatchType.EQUAL,
                    "attribute": "stacktrace.package",
                    "value": value,
                }
            )
            self.assert_passes(self.dc, self.event_data)

        # non-matching filename
        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "stacktrace.package",
                "value": "package/otherotherpackage.lib",
            }
        )
        self.assert_does_not_pass(self.dc, self.event_data)

    def test_extra_simple_value(self) -> None:
        self.dc.comparison.update(
            {"match": MatchType.EQUAL, "attribute": "extra.bar", "value": "foo"}
        )
        self.assert_passes(self.dc, self.event_data)

        self.dc.comparison.update(
            {"match": MatchType.EQUAL, "attribute": "extra.bar", "value": "bar"}
        )
        self.assert_does_not_pass(self.dc, self.event_data)

    def test_extra_nested_value(self) -> None:
        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "extra.foo.bar",
                "value": "baz",
            }
        )
        self.assert_passes(self.dc, self.event_data)

        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "extra.foo.bar",
                "value": "bar",
            }
        )
        self.assert_does_not_pass(self.dc, self.event_data)

    def test_extra_nested_list(self) -> None:
        self.dc.comparison.update(
            {"match": MatchType.EQUAL, "attribute": "extra.biz", "value": "baz"}
        )
        self.assert_passes(self.dc, self.event_data)

        self.dc.comparison.update(
            {"match": MatchType.EQUAL, "attribute": "extra.biz", "value": "bar"}
        )
        self.assert_does_not_pass(self.dc, self.event_data)

    def test_event_type(self) -> None:
        self.event.data["type"] = "error"
        self.setup_group_event_and_job()
        self.dc.comparison.update({"match": MatchType.EQUAL, "attribute": "type", "value": "error"})
        self.assert_passes(self.dc, self.event_data)

        self.dc.comparison.update({"match": MatchType.EQUAL, "attribute": "type", "value": "csp"})
        self.assert_does_not_pass(self.dc, self.event_data)

    def test_device_screen_width_pixels(self) -> None:
        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "device.screen_width_pixels",
                "value": "1920",
            }
        )
        self.assert_passes(self.dc, self.event_data)

        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "device.screen_width_pixels",
                "value": "400",
            }
        )
        self.assert_does_not_pass(self.dc, self.event_data)

    def test_device_screen_height_pixels(self) -> None:
        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "device.screen_height_pixels",
                "value": "1080",
            }
        )
        self.assert_passes(self.dc, self.event_data)

        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "device.screen_height_pixels",
                "value": "400",
            }
        )
        self.assert_does_not_pass(self.dc, self.event_data)

    def test_device_screen_dpi(self) -> None:
        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "device.screen_dpi",
                "value": "123",
            }
        )
        self.assert_passes(self.dc, self.event_data)

        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "device.screen_dpi",
                "value": "400",
            }
        )
        self.assert_does_not_pass(self.dc, self.event_data)

    def test_device_screen_density(self) -> None:
        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "device.screen_density",
                "value": "2.5",
            }
        )
        self.assert_passes(self.dc, self.event_data)

        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "device.screen_density",
                "value": "400",
            }
        )
        self.assert_does_not_pass(self.dc, self.event_data)

    def test_app_in_foreground(self) -> None:
        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "app.in_foreground",
                "value": "True",
            }
        )
        self.assert_passes(self.dc, self.event_data)

        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "app.in_foreground",
                "value": "False",
            }
        )
        self.assert_does_not_pass(self.dc, self.event_data)

    def test_os_distribution_name_and_version(self) -> None:
        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "os.distribution_name",
                "value": "ubuntu",
            }
        )
        self.assert_passes(self.dc, self.event_data)

        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "os.distribution_name",
                "value": "slackware",
            }
        )
        self.assert_does_not_pass(self.dc, self.event_data)

        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "os.distribution_version",
                "value": "22.04",
            }
        )
        self.assert_passes(self.dc, self.event_data)

        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "os.distribution_version",
                "value": "20.04",
            }
        )
        self.assert_does_not_pass(self.dc, self.event_data)

    def test_ota_updates(self) -> None:
        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "ota_updates.channel",
                "value": "production",
            }
        )
        self.assert_passes(self.dc, self.event_data)

        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "ota_updates.channel",
                "value": "development",
            }
        )
        self.assert_does_not_pass(self.dc, self.event_data)

        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "ota_updates.runtime_version",
                "value": "1.0.0",
            }
        )
        self.assert_passes(self.dc, self.event_data)

        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "ota_updates.runtime_version",
                "value": "2.0.0",
            }
        )
        self.assert_does_not_pass(self.dc, self.event_data)

        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "ota_updates.update_id",
                "value": "123",
            }
        )
        self.assert_passes(self.dc, self.event_data)

        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "ota_updates.update_id",
                "value": "876",
            }
        )
        self.assert_does_not_pass(self.dc, self.event_data)

        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "ota_updates.non_existent",
                "value": "876",
            }
        )
        self.assert_does_not_pass(self.dc, self.event_data)

    def test_unreal_crash_type(self) -> None:
        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "unreal.crash_type",
                "value": "Crash",
            }
        )
        self.assert_passes(self.dc, self.event_data)

        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "unreal.crash_type",
                "value": "NoCrash",
            }
        )
        self.assert_does_not_pass(self.dc, self.event_data)

    def test_does_not_error_with_none(self) -> None:
        self.event = self.get_event(
            exception={
                "values": [
                    None,
                    {
                        "type": "SyntaxError",
                        "value": "hello world",
                        "stacktrace": {
                            "frames": [
                                {
                                    "filename": "example.php",
                                    "module": "example",
                                    "context_line": 'echo "hello";',
                                    "abs_path": "path/to/example.php",
                                }
                            ]
                        },
                        "thread_id": 1,
                    },
                ]
            }
        )
        self.setup_group_event_and_job()
        self.dc.comparison.update(
            {
                "match": MatchType.EQUAL,
                "attribute": "exception.type",
                "value": "SyntaxError",
            }
        )
        self.assert_passes(self.dc, self.event_data)

    def test_is_set(self) -> None:
        self.dc.comparison.update({"match": MatchType.IS_SET, "attribute": "platform"})
        self.assert_passes(self.dc, self.event_data)

        self.dc.comparison.update({"match": MatchType.IS_SET, "attribute": "missing"})
        self.assert_does_not_pass(self.dc, self.event_data)

    def test_not_set(self) -> None:
        self.dc.comparison.update({"match": MatchType.NOT_SET, "attribute": "platform"})
        self.assert_does_not_pass(self.dc, self.event_data)

        self.dc.comparison.update({"match": MatchType.NOT_SET, "attribute": "missing"})
        self.assert_passes(self.dc, self.event_data)

    def test_attr_is_in(self) -> None:
        self.dc.comparison.update(
            {
                "match": MatchType.IS_IN,
                "attribute": "platform",
                "value": "php, python",
            }
        )
        self.assert_passes(self.dc, self.event_data)

        self.dc.comparison.update(
            {
                "match": MatchType.IS_IN,
                "attribute": "platform",
                "value": "python, ruby",
            }
        )
        self.assert_does_not_pass(self.dc, self.event_data)

    def test_attr_not_in(self) -> None:
        self.dc.comparison.update(
            {
                "match": MatchType.NOT_IN,
                "attribute": "platform",
                "value": "php, python",
            }
        )
        self.assert_does_not_pass(self.dc, self.event_data)

        self.dc.comparison.update(
            {
                "match": MatchType.NOT_IN,
                "attribute": "platform",
                "value": "python, ruby",
            }
        )
        self.assert_passes(self.dc, self.event_data)
