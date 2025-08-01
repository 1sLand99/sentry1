from functools import cached_property

import orjson
import responses

from sentry.models.rule import Rule
from sentry.plugins.base import Notification
from sentry.testutils.cases import PluginTestCase
from sentry_plugins.opsgenie.plugin import OpsGeniePlugin


def test_conf_key() -> None:
    assert OpsGeniePlugin().conf_key == "opsgenie"


class OpsGeniePluginTest(PluginTestCase):
    @cached_property
    def plugin(self):
        return OpsGeniePlugin()

    def test_is_configured(self) -> None:
        assert self.plugin.is_configured(self.project) is False
        self.plugin.set_option("api_key", "abcdef", self.project)
        assert self.plugin.is_configured(self.project) is False
        self.plugin.set_option("alert_url", "https://api.opsgenie.com/v2/alerts", self.project)
        assert self.plugin.is_configured(self.project) is True

    @responses.activate
    def test_simple_notification(self) -> None:
        responses.add("POST", "https://api.opsgenie.com/v2/alerts")
        self.plugin.set_option("api_key", "abcdef", self.project)
        self.plugin.set_option("alert_url", "https://api.opsgenie.com/v2/alerts", self.project)
        self.plugin.set_option("recipients", "me", self.project)

        event = self.store_event(
            data={
                "message": "Hello world",
                "level": "warning",
                "platform": "python",
                "culprit": "foo.bar",
            },
            project_id=self.project.id,
        )
        group = event.group
        assert group is not None

        rule = Rule.objects.create(project=self.project, label="my rule")

        notification = Notification(event=event, rule=rule)

        with self.options({"system.url-prefix": "http://example.com"}):
            self.plugin.notify(notification)

        request = responses.calls[0].request
        payload = orjson.loads(request.body)
        group_id = str(group.id)
        assert payload == {
            "recipients": "me",
            "tags": ["level:warning"],
            "entity": "foo.bar",
            "alias": "sentry: %s" % group_id,
            "details": {
                "Project Name": self.project.name,
                "Triggering Rules": '["my rule"]',
                "Sentry Group": "Hello world",
                "Sentry ID": group_id,
                "Logger": "",
                "Level": "warning",
                "Project ID": "bar",
                "URL": "http://example.com/organizations/baz/issues/%s/" % group_id,
            },
            "message": "Hello world",
            "source": "Sentry",
        }
