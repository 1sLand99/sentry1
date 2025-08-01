from functools import cached_property
from unittest.mock import MagicMock, patch

import orjson
import pytest
from botocore.client import ClientError

from sentry.testutils.cases import PluginTestCase
from sentry_plugins.amazon_sqs.plugin import AmazonSQSPlugin


def test_conf_key() -> None:
    assert AmazonSQSPlugin().conf_key == "amazon-sqs"


class AmazonSQSPluginTest(PluginTestCase):
    @cached_property
    def plugin(self):
        return AmazonSQSPlugin()

    def run_test(self):
        self.plugin.set_option("access_key", "access-key", self.project)
        self.plugin.set_option("secret_key", "secret-key", self.project)
        self.plugin.set_option("region", "us-east-1", self.project)
        self.plugin.set_option(
            "queue_url", "https://sqs.us-east-1.amazonaws.com/12345678/myqueue", self.project
        )

        event = self.store_event(
            data={
                "sentry.interfaces.Exception": {"type": "ValueError", "value": "foo bar"},
                "sentry.interfaces.User": {"id": "1", "email": "foo@example.com"},
                "type": "error",
                "metadata": {"type": "ValueError", "value": "foo bar"},
            },
            project_id=self.project.id,
        )

        with self.options({"system.url-prefix": "http://example.com"}):
            self.plugin.post_process(event=event)
        return event

    @patch("boto3.client")
    def test_simple_notification(self, mock_client: MagicMock) -> None:
        event = self.run_test()
        mock_client.assert_called_once_with(
            service_name="sqs",
            region_name="us-east-1",
            aws_access_key_id="access-key",
            aws_secret_access_key="secret-key",
        )
        mock_client.return_value.send_message.assert_called_once_with(
            QueueUrl="https://sqs.us-east-1.amazonaws.com/12345678/myqueue",
            MessageBody=orjson.dumps(
                self.plugin.get_event_payload(event), option=orjson.OPT_UTC_Z
            ).decode(),
        )

    @patch("boto3.client")
    def test_token_error(self, mock_client: MagicMock) -> None:
        mock_client.return_value.send_message.side_effect = ClientError(
            {"Error": {"Code": "Hello", "Message": "hello"}}, "SendMessage"
        )
        with pytest.raises(ClientError):
            self.run_test()

        mock_client.return_value.send_message.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Hello"}}, "SendMessage"
        )
        self.run_test()

    @patch("boto3.client")
    def test_message_group_error(self, mock_client: MagicMock) -> None:
        mock_client.return_value.send_message.side_effect = ClientError(
            {
                "Error": {
                    "Code": "MissingParameter",
                    "Message": "The request must contain the parameter MessageGroupId.",
                }
            },
            "SendMessage",
        )

        self.run_test()

    @patch("uuid.uuid4")
    @patch("boto3.client")
    def test_pass_message_group_id(self, mock_client: MagicMock, mock_uuid: MagicMock) -> None:
        mock_uuid.return_value = self.get_mock_uuid()

        self.plugin.set_option("message_group_id", "my_group", self.project)
        event = self.run_test()

        mock_client.return_value.send_message.assert_called_once_with(
            QueueUrl="https://sqs.us-east-1.amazonaws.com/12345678/myqueue",
            MessageBody=orjson.dumps(
                self.plugin.get_event_payload(event), option=orjson.OPT_UTC_Z
            ).decode(),
            MessageGroupId="my_group",
            MessageDeduplicationId="abc123",
        )

    @patch("boto3.client")
    def test_use_s3_bucket(self, mock_client: MagicMock) -> None:
        self.plugin.set_option("s3_bucket", "my_bucket", self.project)
        event = self.run_test()
        date = event.datetime.strftime("%Y-%m-%d")
        key = f"{event.project.slug}/{date}/{event.event_id}"

        mock_client.return_value.send_message.assert_called_once_with(
            QueueUrl="https://sqs.us-east-1.amazonaws.com/12345678/myqueue",
            MessageBody=orjson.dumps(
                {
                    "s3Url": f"https://my_bucket.s3-us-east-1.amazonaws.com/{key}",
                    "eventID": event.event_id,
                },
                option=orjson.OPT_UTC_Z,
            ).decode(),
        )

        mock_client.return_value.put_object.assert_called_once_with(
            Bucket="my_bucket",
            Body=orjson.dumps(
                self.plugin.get_event_payload(event), option=orjson.OPT_UTC_Z
            ).decode(),
            Key=key,
        )

    @patch("boto3.client")
    @pytest.mark.skip(reason="https://github.com/getsentry/sentry/issues/44858")
    def test_invalid_s3_bucket(self, mock_client, logger) -> None:
        self.plugin.set_option("s3_bucket", "bad_bucket", self.project)
        mock_client.return_value.put_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchBucket"}},
            "PutObject",
        )
        self.run_test()
