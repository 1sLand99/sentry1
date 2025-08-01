import sentry_sdk
from django.utils import timezone
from rest_framework.request import Request
from rest_framework.response import Response

from sentry import onboarding_tasks
from sentry.api.api_owners import ApiOwner
from sentry.api.api_publish_status import ApiPublishStatus
from sentry.api.base import region_silo_endpoint
from sentry.api.bases.organization import OrganizationEndpoint, OrganizationPermission
from sentry.api.serializers import serialize
from sentry.models.organization import Organization
from sentry.models.organizationonboardingtask import OnboardingTask, OnboardingTaskStatus


class OnboardingTaskPermission(OrganizationPermission):
    scope_map = {"POST": ["org:read"], "GET": ["org:read"]}


@region_silo_endpoint
class OrganizationOnboardingTaskEndpoint(OrganizationEndpoint):
    publish_status = {
        "POST": ApiPublishStatus.PRIVATE,
        "GET": ApiPublishStatus.PRIVATE,
    }
    owner = ApiOwner.TELEMETRY_EXPERIENCE
    permission_classes = (OnboardingTaskPermission,)

    def post(self, request: Request, organization) -> Response:
        task_id = onboarding_tasks.get_task_lookup_by_key(request.data["task"])
        if task_id is None:
            return Response({"detail": "Invalid task key"}, status=422)

        status_value = request.data.get("status")
        completion_seen = request.data.get("completionSeen")

        if status_value is None and completion_seen is None:
            return Response({"detail": "completionSeen or status must be provided"}, status=422)

        status = onboarding_tasks.get_status_lookup_by_key(status_value)

        if status_value and status is None:
            return Response({"detail": "Invalid status key"}, status=422)

        # Cannot skip unskippable tasks
        if (
            status == OnboardingTaskStatus.SKIPPED
            and task_id not in onboarding_tasks.get_skippable_tasks(organization)
        ):
            return Response(status=422)

        values = {}

        if status:
            values["status"] = status
            values["date_completed"] = timezone.now()
        if completion_seen:
            values["completion_seen"] = timezone.now()

        rows_affected, created = onboarding_tasks.create_or_update_onboarding_task(
            organization=organization,
            task=task_id,
            user=request.user,
            values=values,
        )

        if created and task_id == OnboardingTask.FIRST_PROJECT:
            scope = sentry_sdk.get_current_scope()
            scope.set_extra("org", organization.id)
            sentry_sdk.capture_message(
                f"Onboarding task {task_id} was created unexpectedly. It should have been updated instead.",
                level="warning",
            )

        if rows_affected or created:
            onboarding_tasks.try_mark_onboarding_complete(organization.id)

        return Response(status=204)

    def get(self, request: Request, organization: Organization) -> Response:
        tasks_to_serialize = list(
            onboarding_tasks.fetch_onboarding_tasks(organization, request.user)
        )
        serialized_tasks = serialize(tasks_to_serialize, request.user)

        return Response({"onboardingTasks": serialized_tasks}, status=200)
