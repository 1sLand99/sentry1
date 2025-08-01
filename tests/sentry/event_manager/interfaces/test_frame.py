import pytest

from sentry import eventstore
from sentry.event_manager import EventManager
from sentry.testutils.pytest.fixtures import django_db_all


@pytest.fixture
def make_frames_snapshot(insta_snapshot):
    def inner(data):
        mgr = EventManager(data={"stacktrace": {"frames": [data]}})
        mgr.normalize()
        evt = eventstore.backend.create_event(project_id=1, data=mgr.get_data())
        frame = evt.interfaces["stacktrace"].frames[0]

        insta_snapshot({"errors": evt.data.get("errors"), "to_json": frame.to_json()})

    return inner


@django_db_all
@pytest.mark.parametrize(
    "input",
    [
        {"filename": 1},
        {"filename": "foo", "abs_path": 1},
        {"function": 1},
        {"module": 1},
        {"function": "?"},
    ],
)
def test_bad_input(make_frames_snapshot, input) -> None:
    make_frames_snapshot(input)


@django_db_all
@pytest.mark.parametrize(
    "x", [float("inf"), float("-inf"), float("nan")], ids=["inf", "neginf", "nan"]
)
def test_context_with_nan(make_frames_snapshot, x) -> None:
    make_frames_snapshot({"filename": "x", "vars": {"x": x}})


def test_address_normalization(make_frames_snapshot) -> None:
    make_frames_snapshot(
        {
            "lineno": 1,
            "filename": "blah.c",
            "function": "main",
            "instruction_addr": 123456,
            "symbol_addr": "123450",
            "image_addr": "0x0",
        }
    )
