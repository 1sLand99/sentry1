from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response

from sentry import audit_log
from sentry.api.api_owners import ApiOwner
from sentry.api.api_publish_status import ApiPublishStatus
from sentry.api.base import control_silo_endpoint
from sentry.api.bases import ControlSiloOrganizationEndpoint
from sentry.api.bases.organization import OrganizationAuditPermission
from sentry.api.paginator import DateTimePaginator
from sentry.api.serializers import serialize
from sentry.api.utils import get_date_range_from_stats_period
from sentry.audit_log.manager import AuditLogEventNotRegistered
from sentry.db.models.fields.bounded import BoundedIntegerField
from sentry.models.auditlogentry import AuditLogEntry
from sentry.organizations.services.organization.model import (
    RpcOrganization,
    RpcUserOrganizationContext,
)


class AuditLogQueryParamSerializer(serializers.Serializer):
    event = serializers.CharField(required=False)
    actor = serializers.IntegerField(required=False, max_value=BoundedIntegerField.MAX_VALUE)
    start = serializers.DateTimeField(required=False)
    end = serializers.DateTimeField(required=False)
    statsPeriod = serializers.CharField(required=False)

    def validate_event(self, event):
        try:
            return audit_log.get_event_id_from_api_name(event)
        except AuditLogEventNotRegistered:
            return None


@control_silo_endpoint
class OrganizationAuditLogsEndpoint(ControlSiloOrganizationEndpoint):
    publish_status = {
        "GET": ApiPublishStatus.EXPERIMENTAL,
    }
    owner = ApiOwner.ENTERPRISE
    permission_classes = (OrganizationAuditPermission,)

    def get(
        self,
        request: Request,
        organization_context: RpcUserOrganizationContext,
        organization: RpcOrganization,
    ) -> Response:
        queryset = AuditLogEntry.objects.filter(organization_id=organization.id).select_related(
            "actor"
        )

        serializer = AuditLogQueryParamSerializer(data=request.GET)

        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        query = serializer.validated_data

        if "actor" in query:
            queryset = queryset.filter(actor=query["actor"])

        if "event" in query:
            if query.get("event") is None:
                queryset = queryset.none()
            else:
                queryset = queryset.filter(event=query["event"])

        # Handle date filtering
        start, end = get_date_range_from_stats_period(request.GET, optional=True)
        if start and end:
            queryset = queryset.filter(datetime__range=(start, end))

        response = self.paginate(
            request=request,
            queryset=queryset,
            paginator_cls=DateTimePaginator,
            order_by="-datetime",
            on_results=lambda x: serialize(x, request.user),
        )
        response.data = {"rows": response.data, "options": audit_log.get_api_names()}
        return response
