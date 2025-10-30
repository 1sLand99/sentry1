from typing import Any

from django.db import router, transaction
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from sentry.api.api_owners import ApiOwner
from sentry.api.api_publish_status import ApiPublishStatus
from sentry.api.base import region_silo_endpoint
from sentry.api.bases.organization import OrganizationEndpoint, OrganizationPermission
from sentry.api.exceptions import ResourceDoesNotExist
from sentry.api.serializers import serialize
from sentry.apidocs.constants import RESPONSE_BAD_REQUEST, RESPONSE_FORBIDDEN, RESPONSE_NO_CONTENT
from sentry.apidocs.parameters import GlobalParams
from sentry.integrations.api.serializers.models.data_forwarder import (
    DataForwarderSerializer as DataForwarderModelSerializer,
)
from sentry.integrations.api.serializers.rest_framework.data_forwarder import (
    DataForwarderProjectSerializer,
    DataForwarderSerializer,
)
from sentry.integrations.models.data_forwarder import DataForwarder
from sentry.integrations.models.data_forwarder_project import DataForwarderProject
from sentry.models.organization import Organization
from sentry.models.project import Project
from sentry.organizations.services.organization.model import (
    RpcOrganization,
    RpcUserOrganizationContext,
)
from sentry.web.decorators import set_referrer_policy


class OrganizationDataForwardingDetailsPermission(OrganizationPermission):
    scope_map = {
        "PUT": ["org:write"],
        "DELETE": ["org:write"],
    }

    def has_object_permission(
        self,
        request: Request,
        view: APIView,
        organization: Organization | RpcOrganization | RpcUserOrganizationContext,
    ) -> bool:
        if super().has_object_permission(request, view, organization):
            return True

        if request.method == "PUT":
            self.determine_access(request, organization)
            return len(request.access.team_ids_with_membership) > 0

        return False


@region_silo_endpoint
@extend_schema(tags=["Integrations"])
class DataForwardingDetailsEndpoint(OrganizationEndpoint):
    owner = ApiOwner.INTEGRATIONS
    publish_status = {
        "PUT": ApiPublishStatus.EXPERIMENTAL,
        "DELETE": ApiPublishStatus.EXPERIMENTAL,
    }
    permission_classes = (OrganizationDataForwardingDetailsPermission,)

    def convert_args(
        self,
        request: Request,
        organization_id_or_slug: int | str,
        data_forwarder_id: int,
        *args,
        **kwargs,
    ):
        args, kwargs = super().convert_args(request, organization_id_or_slug, *args, **kwargs)

        try:
            data_forwarder = DataForwarder.objects.get(
                id=data_forwarder_id,
                organization=kwargs["organization"],
            )
        except DataForwarder.DoesNotExist:
            raise ResourceDoesNotExist

        kwargs["data_forwarder"] = data_forwarder
        return args, kwargs

    def _update_data_forwarder_config(
        self, request: Request, organization: Organization, data_forwarder: DataForwarder
    ) -> Response:
        """
        Request body: {"is_enabled": true, "enroll_new_projects": true, "provider": "segment", "config": {...}, "project_ids": [1, 2, 3]}

        Returns:
            Response: 200 OK with serialized data forwarder on success,
                     400 Bad Request with validation errors on failure
        """
        data: dict[str, Any] = request.data
        data["organization_id"] = organization.id

        serializer = DataForwarderSerializer(
            data_forwarder, data=data, context={"organization": organization}
        )
        if serializer.is_valid():
            data_forwarder = serializer.save()
            return Response(
                serialize(data_forwarder, request.user),
                status=status.HTTP_200_OK,
            )
        return self.respond(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def _validate_enrollment_changes(
        self,
        request: Request,
        organization: Organization,
        data_forwarder: DataForwarder,
    ) -> tuple[set[int], set[int]]:
        """
        Request body: {"project_ids": [1, 2, 3]}

        Validates enrollment changes:
        - project IDs to be enrolled exist in the organization
        - User has project:write on projects being enrolled
        - User has project:write on projects being unenrolled

        Returns:
            Tuple of (project_ids_to_enroll, project_ids_to_unenroll)
        """
        project_ids_new: set[int] = set(request.data.get("project_ids", []))
        project_ids_current: set[int] = set(
            DataForwarderProject.objects.filter(
                data_forwarder=data_forwarder, is_enabled=True
            ).values_list("project_id", flat=True)
        )

        project_ids_to_enroll: set[int] = project_ids_new - project_ids_current
        project_ids_to_unenroll: set[int] = project_ids_current - project_ids_new

        all_project_ids: set[int] = project_ids_new | project_ids_to_unenroll
        all_projects_by_id: dict[int, Project] = {
            project.id: project
            for project in Project.objects.filter(
                organization_id=organization.id, id__in=all_project_ids
            )
        }

        # Validate new project IDs being enrolled exist in the organization
        missing_ids: set[int] = project_ids_to_enroll - all_projects_by_id.keys()
        if missing_ids:
            raise serializers.ValidationError(
                {
                    "project_ids": [
                        f"Invalid project IDs for this organization: {', '.join(map(str, missing_ids))}"
                    ]
                }
            )

        # Validate permissions on all projects
        unauthorized_project_ids: set[int] = {
            project_id
            for project_id in all_projects_by_id.keys()
            if not request.access.has_project_scope(all_projects_by_id[project_id], "project:write")
        }
        if unauthorized_project_ids:
            raise PermissionDenied(
                detail={
                    "project_ids": [
                        f"Insufficient access to projects: {', '.join(map(str, unauthorized_project_ids))}"
                    ]
                }
            )

        return project_ids_to_enroll, project_ids_to_unenroll

    def _update_enrollment(
        self,
        request: Request,
        organization: Organization,
        data_forwarder: DataForwarder,
    ) -> Response:
        """
        Request body: {"project_ids": [1, 2, 3]}
        """
        project_ids_to_enroll, project_ids_to_unenroll = self._validate_enrollment_changes(
            request, organization, data_forwarder
        )

        with transaction.atomic(router.db_for_write(DataForwarderProject)):
            existing_data_forwarder_projects: set[int] = set(
                DataForwarderProject.objects.filter(
                    data_forwarder=data_forwarder, project_id__in=project_ids_to_enroll
                ).values_list("project_id", flat=True)
            )

            new_data_forwarder_projects: set[int] = (
                project_ids_to_enroll - existing_data_forwarder_projects
            )
            DataForwarderProject.objects.bulk_create(
                [
                    DataForwarderProject(
                        data_forwarder=data_forwarder,
                        project_id=project_id,
                        is_enabled=True,
                    )
                    for project_id in new_data_forwarder_projects
                ]
            )

            DataForwarderProject.objects.filter(
                data_forwarder=data_forwarder, project_id__in=existing_data_forwarder_projects
            ).update(is_enabled=True)

            DataForwarderProject.objects.filter(
                data_forwarder=data_forwarder, project_id__in=project_ids_to_unenroll
            ).update(is_enabled=False)

        return Response(
            serialize(data_forwarder, request.user),
            status=status.HTTP_200_OK,
        )

    def _update_single_project_configuration(
        self,
        request: Request,
        organization: Organization,
        data_forwarder: DataForwarder,
    ) -> Response:
        """
        Request body: {"project_id": 1, "overrides": {...}, "is_enabled": true}
        """
        project_id: int = request.data["project_id"]

        try:
            # Update existing configuration
            project_config = DataForwarderProject.objects.get(
                data_forwarder=data_forwarder,
                project_id=project_id,
            )
            serializer = DataForwarderProjectSerializer(
                project_config,
                data={
                    "data_forwarder_id": data_forwarder.id,
                    "project": project_id,
                    "overrides": request.data.get("overrides", {}),
                    "is_enabled": request.data.get("is_enabled", project_config.is_enabled),
                },
                context={"organization": organization, "access": request.access},
            )
        except DataForwarderProject.DoesNotExist:
            # Create new configuration
            serializer = DataForwarderProjectSerializer(
                data={
                    "data_forwarder_id": data_forwarder.id,
                    "project": project_id,
                    "overrides": request.data.get("overrides", {}),
                    "is_enabled": request.data.get("is_enabled", True),
                },
                context={"organization": organization, "access": request.access},
            )

        if serializer.is_valid():
            serializer.save()
            return Response(
                serialize(data_forwarder, request.user),
                status=status.HTTP_200_OK,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @set_referrer_policy("strict-origin-when-cross-origin")
    @method_decorator(never_cache)
    @extend_schema(
        operation_id="Update a Data Forwarding Configuration for an Organization",
        parameters=[GlobalParams.ORG_ID_OR_SLUG],
        request=DataForwarderSerializer,
        responses={
            200: DataForwarderModelSerializer,
            400: RESPONSE_BAD_REQUEST,
            403: RESPONSE_FORBIDDEN,
        },
    )
    def put(
        self, request: Request, organization: Organization, data_forwarder: DataForwarder
    ) -> Response:
        # org:write users can update the main data forwarder configuration
        if request.access.has_scope("org:write"):
            return self._update_data_forwarder_config(request, organization, data_forwarder)

        # project:write users have two operation types:
        # 1. Bulk enrollment/unenrollment: {"project_ids": [...]}
        # 2. Single project override update: {"project_id": X, "overrides": {...}}

        has_project_ids = "project_ids" in request.data
        has_project_id = "project_id" in request.data

        if has_project_ids and has_project_id:
            raise serializers.ValidationError(
                "Cannot specify both 'project_ids' and 'project_id'. "
                "Use 'project_ids' for bulk enrollment or 'project_id' with 'overrides' for single project update."
            )

        if has_project_ids:
            return self._update_enrollment(request, organization, data_forwarder)
        elif has_project_id:
            return self._update_single_project_configuration(request, organization, data_forwarder)
        else:
            raise serializers.ValidationError(
                "Must specify either 'project_ids' for bulk enrollment or 'project_id' with 'overrides' for single project update."
            )

    @extend_schema(
        operation_id="Delete a Data Forwarding Configuration for an Organization",
        parameters=[GlobalParams.ORG_ID_OR_SLUG],
        responses={
            204: RESPONSE_NO_CONTENT,
            403: RESPONSE_FORBIDDEN,
        },
    )
    def delete(
        self, request: Request, organization: Organization, data_forwarder: DataForwarder
    ) -> Response:
        data_forwarder.delete()
        return self.respond(status=status.HTTP_204_NO_CONTENT)
