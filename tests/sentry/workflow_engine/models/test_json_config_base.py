from dataclasses import dataclass

import pytest
from jsonschema import ValidationError

from sentry.incidents.grouptype import MetricIssue
from sentry.issues.grouptype import GroupCategory, GroupType
from sentry.testutils.cases import APITestCase
from sentry.workflow_engine.types import DetectorSettings
from tests.sentry.issues.test_grouptype import BaseGroupTypeTest


class JSONConfigBaseTest(BaseGroupTypeTest):
    def setUp(self) -> None:
        super().setUp()
        self.correct_config = {
            "username": "user123",
            "email": "user@example.com",
            "fullName": "John Doe",
            "age": 30,
            "location": "Cityville",
            "interests": ["Travel", "Technology"],
        }

        self.example_schema = {
            "$id": "https://example.com/user-profile.schema.json",
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "description": "A representation of a user profile",
            "type": "object",
            "required": ["username", "email"],
            "properties": {
                "username": {"type": "string"},
                "email": {"type": "string", "format": "email"},
                "fullName": {"type": "string"},
                "age": {"type": "integer", "minimum": 0},
                "location": {"type": "string"},
                "interests": {"type": "array", "items": {"type": "string"}},
            },
        }

        @dataclass(frozen=True)
        class TestGroupType(GroupType):
            type_id = 1
            slug = "test"
            description = "Test"
            category = GroupCategory.ERROR.value
            category_v2 = GroupCategory.ERROR.value
            detector_settings = DetectorSettings(config_schema=self.example_schema)

        @dataclass(frozen=True)
        class ExampleGroupType(GroupType):
            type_id = 2
            slug = "example"
            description = "Example"
            category = GroupCategory.PERFORMANCE.value
            category_v2 = GroupCategory.DB_QUERY.value
            detector_settings = DetectorSettings(
                config_schema={"type": "object", "additionalProperties": False},
            )


# TODO - Move this to the detector model test
class TestDetectorConfig(JSONConfigBaseTest):
    def test_detector_no_registration(self) -> None:
        with pytest.raises(ValueError):
            self.create_detector(name="test_detector", type="no_registration")

    def test_detector_schema(self) -> None:
        self.create_detector(name="test_detector", type="test", config=self.correct_config)

        with pytest.raises(ValidationError):
            self.create_detector(name="test_detector", type="test", config={"hi": "there"})

    def test_detector_empty_schema(self) -> None:
        self.create_detector(name="example_detector", type="example", config={})

        with pytest.raises(ValidationError):
            self.create_detector(name="test_detector", type="example", config={"hi": "there"})


# TODO - Move this to the workflow model test
class TestWorkflowConfig(JSONConfigBaseTest):
    def test_workflow_mismatched_schema(self) -> None:
        with pytest.raises(ValidationError):
            self.create_workflow(
                organization=self.organization, name="test_workflow", config={"hi": "there"}
            )

    def test_workflow_correct_schema(self) -> None:
        self.create_workflow(organization=self.organization, name="test_workflow", config={})
        self.create_workflow(
            organization=self.organization, name="test_workflow2", config={"frequency": 30}
        )


# TODO - This should be moved into incidents directory
class TestMetricIssueDetectorConfig(JSONConfigBaseTest, APITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.metric_alert = self.create_alert_rule(threshold_period=1)

        @dataclass(frozen=True)
        class TestGroupType(GroupType):
            type_id = 3
            slug = "test_metric_issue"
            description = "Metric alert fired"
            category = GroupCategory.METRIC_ALERT.value
            category_v2 = GroupCategory.METRIC.value
            detector_settings = DetectorSettings(
                config_schema=MetricIssue.detector_settings.config_schema,
            )

    def test_detector_correct_schema(self) -> None:
        self.create_detector(
            name=self.metric_alert.name,
            project_id=self.project.id,
            type="test_metric_issue",
            owner_user_id=self.metric_alert.user_id,
            config={
                "threshold_period": self.metric_alert.threshold_period,
                "comparison_delta": self.metric_alert.comparison_delta,
                "detection_type": self.metric_alert.detection_type,
                "sensitivity": self.metric_alert.sensitivity,
                "seasonality": self.metric_alert.seasonality,
            },
        )

    def test_empty_config(self) -> None:
        with pytest.raises(ValidationError):
            self.create_detector(
                name=self.metric_alert.name,
                project_id=self.project.id,
                type="test_metric_issue",
                owner_user_id=self.metric_alert.user_id,
                config={},
            )

    def test_no_config(self) -> None:
        with pytest.raises(ValidationError):
            self.create_detector(
                name=self.metric_alert.name,
                project_id=self.project.id,
                type="test_metric_issue",
                owner_user_id=self.metric_alert.user_id,
            )

    def test_incorrect_config(self) -> None:
        with pytest.raises(ValidationError):
            self.create_detector(
                name=self.metric_alert.name,
                project_id=self.project.id,
                type="test_metric_issue",
                owner_user_id=self.metric_alert.user_id,
                config=["some", "stuff"],
            )

    def test_mismatched_schema(self) -> None:
        with pytest.raises(ValidationError):
            self.create_detector(
                name=self.metric_alert.name,
                project_id=self.project.id,
                type="test_metric_issue",
                owner_user_id=self.metric_alert.user_id,
                config={
                    "comparison_delta": "matcha",
                    "detection_type": self.metric_alert.detection_type,
                },
            )

    def test_missing_required(self) -> None:
        with pytest.raises(ValidationError):
            self.create_detector(
                name=self.metric_alert.name,
                project_id=self.project.id,
                type="test_metric_issue",
                owner_user_id=self.metric_alert.user_id,
                config={
                    "threshold_period": self.metric_alert.threshold_period,
                    "comparison_delta": self.metric_alert.comparison_delta,
                    "sensitivity": self.metric_alert.sensitivity,
                    "seasonality": self.metric_alert.seasonality,
                },
            )
