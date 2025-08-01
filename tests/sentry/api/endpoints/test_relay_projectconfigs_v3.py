from unittest.mock import patch, sentinel

import orjson
import pytest
from django.urls import reverse

from sentry.db.postgres.transactions import in_test_hide_transaction_boundary
from sentry.relay.config import ProjectConfig
from sentry.tasks.relay import build_project_config
from sentry.testutils.hybrid_cloud import simulated_transaction_watermarks
from sentry.testutils.pytest.fixtures import django_db_all


@pytest.fixture(autouse=True)
def disable_auto_on_commit():
    simulated_transaction_watermarks.state["default"] = -1
    with in_test_hide_transaction_boundary():
        yield


@pytest.fixture
def call_endpoint(client, relay, private_key, default_projectkey):
    def inner(public_keys=None, global_=False):
        path = reverse("sentry-api-0-relay-projectconfigs") + "?version=3"

        if public_keys is None:
            public_keys = [str(default_projectkey.public_key)]

        body = {"publicKeys": public_keys, "no_cache": False}
        if global_ is not None:
            body.update({"global": global_})
        raw_json, signature = private_key.pack(body)

        resp = client.post(
            path,
            data=raw_json,
            content_type="application/json",
            HTTP_X_SENTRY_RELAY_ID=relay.relay_id,
            HTTP_X_SENTRY_RELAY_SIGNATURE=signature,
        )

        return orjson.loads(resp.content), resp.status_code

    return inner


@pytest.fixture
def projectconfig_cache_get_mock_config():
    with patch(
        "sentry.relay.projectconfig_cache.backend.get",
        return_value={"is_mock_config": True},
    ):
        yield


@pytest.fixture
def single_mock_proj_cached():
    def cache_get(*args, **kwargs):
        if args[0] == "must_exist":
            return {"is_mock_config": True}
        return None

    with patch("sentry.relay.projectconfig_cache.backend.get", cache_get):
        yield


@pytest.fixture
def projectconfig_debounced_cache():
    with patch("sentry.relay.projectconfig_debounce_cache.backend.is_debounced", return_value=True):
        yield


@pytest.fixture
def project_config_get_mock():
    with patch(
        "sentry.relay.config.get_project_config",
        return_value=ProjectConfig(sentinel.mock_project, is_mock_config=True),
    ):
        yield


@django_db_all
def test_return_full_config_if_in_cache(
    call_endpoint, default_projectkey, projectconfig_cache_get_mock_config
):
    result, status_code = call_endpoint()
    assert status_code < 400
    assert result == {
        "configs": {default_projectkey.public_key: {"is_mock_config": True}},
        "pending": [],
    }


@django_db_all
def test_proj_in_cache_and_another_pending(
    call_endpoint, default_projectkey, single_mock_proj_cached
):
    result, status_code = call_endpoint(public_keys=["must_exist", default_projectkey.public_key])
    assert status_code < 400
    assert result == {
        "configs": {"must_exist": {"is_mock_config": True}},
        "pending": [default_projectkey.public_key],
    }


@patch("sentry.tasks.relay.build_project_config.delay")
@django_db_all
def test_enqueue_task_if_config_not_cached_not_queued(
    schedule_mock,
    call_endpoint,
    default_projectkey,
):
    result, status_code = call_endpoint()
    assert status_code < 400
    assert result == {"configs": {}, "pending": [default_projectkey.public_key]}
    assert schedule_mock.call_count == 1


@patch("sentry.tasks.relay.build_project_config.delay")
@django_db_all
def test_debounce_task_if_proj_config_not_cached_already_enqueued(
    task_mock,
    call_endpoint,
    default_projectkey,
    projectconfig_debounced_cache,
):
    result, status_code = call_endpoint()
    assert status_code < 400
    assert result == {"configs": {}, "pending": [default_projectkey.public_key]}
    assert task_mock.call_count == 0


@patch("sentry.relay.projectconfig_cache.backend.set_many")
@django_db_all
def test_task_writes_config_into_cache(
    cache_set_many_mock,
    default_projectkey,
    project_config_get_mock,
):
    build_project_config(
        public_key=default_projectkey.public_key,
        update_reason="test",
    )

    assert cache_set_many_mock.call_count == 1
    # Using a tuple because that's the format `.args` uses
    assert cache_set_many_mock.call_args.args == (
        {default_projectkey.public_key: {"is_mock_config": True}},
    )


@patch(
    "sentry.api.endpoints.relay.project_configs.get_global_config",
    lambda *args, **kargs: {"global_mock_config": True},
)
@django_db_all
def test_return_project_and_global_config(
    call_endpoint,
    default_projectkey,
    projectconfig_cache_get_mock_config,
):
    result, status_code = call_endpoint(global_=True)
    assert status_code == 200
    assert result == {
        "configs": {default_projectkey.public_key: {"is_mock_config": True}},
        "pending": [],
        "global": {"global_mock_config": True},
        "global_status": "ready",
    }
