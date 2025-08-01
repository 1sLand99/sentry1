from __future__ import annotations

import logging
from collections.abc import Callable, Sequence

from rest_framework.response import Response

from sentry import features
from sentry.constants import ObjectStatus
from sentry.eventstore.models import GroupEvent
from sentry.exceptions import InvalidIdentity
from sentry.integrations.base import IntegrationInstallation
from sentry.integrations.mixins.issues import IssueBasicIntegration
from sentry.integrations.models.external_issue import ExternalIssue
from sentry.integrations.project_management.metrics import (
    ProjectManagementActionType,
    ProjectManagementEvent,
)
from sentry.integrations.services.integration.model import RpcIntegration
from sentry.integrations.services.integration.service import integration_service
from sentry.models.grouplink import GroupLink
from sentry.notifications.types import TEST_NOTIFICATION_ID
from sentry.notifications.utils.links import create_link_to_workflow
from sentry.shared_integrations.exceptions import (
    ApiUnauthorized,
    IntegrationFormError,
    IntegrationInstallationConfigurationError,
)
from sentry.silo.base import region_silo_function
from sentry.types.rules import RuleFuture

logger = logging.getLogger("sentry.rules")


@region_silo_function
def create_link(
    integration: RpcIntegration,
    installation: IntegrationInstallation,
    event: GroupEvent,
    response: Response,
) -> None:
    """
    After creating the event on a third-party service, create a link to the
    external resource in the DB. TODO make this a transaction.
    :param integration: Integration object.
    :param installation: Installation object.
    :param event: The event object that was recorded on an external service.
    :param response: The API response from creating the new resource.
        - key: String. The unique ID of the external resource
        - metadata: Optional Object. Can contain `display_name`.
    """

    assert isinstance(
        installation, IssueBasicIntegration
    ), "Installation must be an IssueBasicIntegration to create a link"
    external_issue_key = installation.make_external_key(response)

    external_issue = ExternalIssue.objects.create(
        organization_id=event.group.project.organization_id,
        integration_id=integration.id,
        key=external_issue_key,
        title=event.title,
        description=installation.get_group_description(event.group, event),
        metadata=response.get("metadata"),
    )
    GroupLink.objects.create(
        group_id=event.group.id,
        project_id=event.group.project_id,
        linked_type=GroupLink.LinkedType.issue,
        linked_id=external_issue.id,
        relationship=GroupLink.Relationship.references,
        data={"provider": integration.provider},
    )


def build_description_workflow_engine_ui(
    event: GroupEvent,
    workflow_id: int,
    installation: IssueBasicIntegration,
    generate_footer: Callable[[str], str],
) -> str:
    project = event.group.project
    workflow_url = create_link_to_workflow(project.organization.id, str(workflow_id))

    description: str = installation.get_group_description(event.group, event) + generate_footer(
        workflow_url
    )
    return description


def build_description(
    event: GroupEvent,
    rule_id: int,
    installation: IssueBasicIntegration,
    generate_footer: Callable[[str], str],
) -> str:
    """
    Format the description of the ticket/work item
    """
    project = event.group.project
    rule_url = f"/organizations/{project.organization.slug}/alerts/rules/{project.slug}/{rule_id}/"

    description: str = installation.get_group_description(event.group, event) + generate_footer(
        rule_url
    )
    return description


def create_issue(event: GroupEvent, futures: Sequence[RuleFuture]) -> None:
    from sentry.notifications.notification_action.utils import should_fire_workflow_actions

    """Create an issue for a given event"""
    organization = event.group.project.organization

    for future in futures:
        rule_id = future.rule.id
        data = future.kwargs.get("data")
        provider = future.kwargs.get("provider")
        integration_id = future.kwargs.get("integration_id")
        generate_footer = future.kwargs.get("generate_footer")

        # If we invoked this handler from the notification action, we need to replace the rule_id with the legacy_rule_id, so we link notifications correctly
        action_id = None
        if should_fire_workflow_actions(organization, event.group.type):
            # In the Notification Action, we store the rule_id in the action_id field
            action_id = rule_id
            rule_id = data.get("legacy_rule_id")

        integration = integration_service.get_integration(
            integration_id=integration_id,
            provider=provider,
            organization_id=organization.id,
            status=ObjectStatus.ACTIVE,
        )
        if not integration:
            # Integration removed, rule still active.
            return

        installation = integration.get_installation(organization.id)

        assert isinstance(
            installation, IssueBasicIntegration
        ), "Installation must be an IssueBasicIntegration to create a ticket"
        data["title"] = installation.get_group_title(event.group, event)
        if features.has("organizations:workflow-engine-ui-links", organization):
            workflow_id = data.get("workflow_id")
            assert workflow_id is not None
            data["description"] = build_description_workflow_engine_ui(
                event, workflow_id, installation, generate_footer
            )
        else:
            data["description"] = build_description(event, rule_id, installation, generate_footer)

        if data.get("dynamic_form_fields"):
            del data["dynamic_form_fields"]

        if ExternalIssue.objects.has_linked_issue(event, integration):
            logger.info(
                "%s.rule_trigger.link_already_exists",
                provider,
                extra={
                    "rule_id": rule_id,
                    "project_id": event.group.project.id,
                    "group_id": event.group.id,
                },
            )
            return

        with ProjectManagementEvent(
            action_type=ProjectManagementActionType.CREATE_EXTERNAL_ISSUE,
            integration=integration,
        ).capture() as lifecycle:
            lifecycle.add_extra("provider", provider)
            lifecycle.add_extra("integration_id", integration.id)
            lifecycle.add_extra("rule_id", rule_id)

            if action_id:
                lifecycle.add_extra("action_id", action_id)

            try:
                response = installation.create_issue(data)
            except (
                IntegrationInstallationConfigurationError,
                IntegrationFormError,
                InvalidIdentity,
                ApiUnauthorized,
            ) as e:
                # Most of the time, these aren't explicit failures, they're
                # some misconfiguration of an issue field - typically Jira.
                # We only want to raise if the rule_id is -1 because that means we're testing the action
                lifecycle.record_halt(e)
                if rule_id == TEST_NOTIFICATION_ID:
                    raise
            # If we successfully created the issue, we want to create the link
            else:
                create_link(integration, installation, event, response)
