from datetime import UTC, datetime, timedelta
from typing import NotRequired, TypedDict

from rest_framework.request import Request
from rest_framework.response import Response

from sentry import quotas
from sentry.api.api_owners import ApiOwner
from sentry.api.api_publish_status import ApiPublishStatus
from sentry.api.base import region_silo_endpoint
from sentry.api.bases import NoProjects
from sentry.api.bases.organization import OrganizationEndpoint, OrganizationUserReportsPermission
from sentry.api.helpers.user_reports import user_reports_filter_to_unresolved
from sentry.api.paginator import DateTimePaginator
from sentry.api.serializers import serialize
from sentry.api.serializers.models import UserReportWithGroupSerializer
from sentry.models.organization import Organization
from sentry.models.userreport import UserReport
from sentry.utils.dates import epoch


class _PaginateKwargs(TypedDict):
    post_query_filter: NotRequired[object]


@region_silo_endpoint
class OrganizationUserReportsEndpoint(OrganizationEndpoint):
    owner = ApiOwner.FEEDBACK
    publish_status = {
        "GET": ApiPublishStatus.PRIVATE,  # TODO: deprecate
    }
    permission_classes = (OrganizationUserReportsPermission,)

    def get(self, request: Request, organization: Organization) -> Response:
        """
        List an Organization's User Feedback
        ``````````````````````````````

        Return a list of user feedback items within this organization. Can be
        filtered by projects/environments/creation date.

        :pparam string organization_id_or_slug: the id or slug of the organization.
        :pparam string project_id_or_slug: the id or slug of the project.
        :auth: required
        """
        try:
            filter_params = self.get_filter_params(request, organization, date_filter_optional=True)
        except NoProjects:
            return Response([])

        queryset = UserReport.objects.filter(
            project_id__in=filter_params["project_id"], group_id__isnull=False
        )
        if "environment" in filter_params:
            assert filter_params["environment_objects"]
            queryset = queryset.filter(
                environment_id__in=[env.id for env in filter_params["environment_objects"]]
            )
        if filter_params["start"] and filter_params["end"]:
            queryset = queryset.filter(
                date_added__range=(filter_params["start"], filter_params["end"])
            )
        else:
            retention = quotas.backend.get_event_retention(organization=organization)
            start = datetime.now(UTC) - timedelta(days=retention) if retention else epoch
            queryset = queryset.filter(date_added__gte=start)

        status = request.GET.get("status", "unresolved")
        paginate_kwargs: _PaginateKwargs = {}
        if status == "unresolved":
            paginate_kwargs["post_query_filter"] = user_reports_filter_to_unresolved
        elif status:
            return self.respond({"status": "Invalid status choice"}, status=400)

        return self.paginate(
            request=request,
            queryset=queryset,
            order_by="-date_added",
            on_results=lambda x: serialize(x, request.user, UserReportWithGroupSerializer()),
            paginator_cls=DateTimePaginator,
            **paginate_kwargs,
        )
