from uuid import uuid4

import orjson
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response

from sentry.api.api_owners import ApiOwner
from sentry.api.api_publish_status import ApiPublishStatus
from sentry.api.base import region_silo_endpoint
from sentry.api.bases.project import ProjectEndpoint
from sentry.apidocs.constants import (
    RESPONSE_BAD_REQUEST,
    RESPONSE_FORBIDDEN,
    RESPONSE_NO_CONTENT,
    RESPONSE_NOT_FOUND,
)
from sentry.apidocs.examples.project_examples import ProjectExamples
from sentry.apidocs.parameters import GlobalParams, ProjectParams
from sentry.lang.native.sources import (
    REDACTED_SOURCE_SCHEMA,
    REDACTED_SOURCES_SCHEMA,
    VALID_CASINGS,
    VALID_FILE_TYPES,
    VALID_LAYOUTS,
    InvalidSourcesError,
    backfill_source,
    parse_sources,
    redact_source_secrets,
    validate_sources,
)
from sentry.models.project import Project


class LayoutSerializer(serializers.Serializer):
    """
    Layout settings for the source. This is required for HTTP, GCS, and S3 sources.

    **`type`** ***(string)*** - The layout of the folder structure. The options are:
    - `native` - Platform-Specific (SymStore / GDB / LLVM)
    - `symstore` - Microsoft SymStore
    - `symstore_index2` - Microsoft SymStore (with index2.txt)
    - `ssqp` - Microsoft SSQP
    - `unified` - Unified Symbol Server Layout
    - `debuginfod` - debuginfod

    **`casing`** ***(string)*** - The layout of the folder structure. The options are:
    - `default` - Default (mixed case)
    - `uppercase` - Uppercase
    - `lowercase` - Lowercase

    ```json
    {
        "layout": {
            "type": "native"
            "casing": "default"
        }
    }
    ```
    """

    type = serializers.ChoiceField(
        choices=VALID_LAYOUTS, help_text="The source's layout type.", required=True
    )
    casing = serializers.ChoiceField(
        choices=VALID_CASINGS, help_text="The source's casing rules.", required=True
    )


class FiltersSerializer(serializers.Serializer):
    """
    Filter settings for the source. This is optional for all sources.

    **`filetypes`** ***(list)*** - A list of file types that can be found on this source. If this is left empty, all file types will be enabled. The options are:
    - `pe` - Windows executable files
    - `pdb` - Windows debug files
    - `portablepdb` - .NET portable debug files
    - `mach_code` - MacOS executable files
    - `mach_debug` - MacOS debug files
    - `elf_code` - ELF executable files
    - `elf_debug` - ELF debug files
    - `wasm_code` - WASM executable files
    - `wasm_debug` - WASM debug files
    - `breakpad` - Breakpad symbol files
    - `sourcebundle` - Source code bundles
    - `uuidmap` - Apple UUID mapping files
    - `bcsymbolmap` - Apple bitcode symbol maps
    - `il2cpp` - Unity IL2CPP mapping files
    - `proguard` - ProGuard mapping files

    **`path_patterns`** ***(list)*** - A list of glob patterns to check against the debug and code file paths of debug files. Only files that match one of these patterns will be requested from the source. If this is left empty, no path-based filtering takes place.

    **`requires_checksum`** ***(boolean)*** - Whether this source requires a debug checksum to be sent with each request. Defaults to `false`.

    ```json
    {
        "filters": {
            "filetypes": ["pe", "pdb", "portablepdb"],
            "path_patterns": ["*ffmpeg*"]
        }
    }
    ```
    """

    filetypes = serializers.MultipleChoiceField(
        choices=VALID_FILE_TYPES,
        required=False,
        help_text="The file types enabled for the source.",
    )
    path_patterns = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="The debug and code file paths enabled for the source.",
    )
    requires_checksum = serializers.BooleanField(
        required=False, help_text="Whether the source requires debug checksums."
    )


class SourceSerializer(serializers.Serializer):
    type = serializers.ChoiceField(
        choices=[
            ("http", "SymbolServer (HTTP)"),
            ("gcs", "Google Cloud Storage"),
            ("s3", "Amazon S3"),
        ],
        required=True,
        help_text="The type of the source.",
    )
    id = serializers.CharField(
        required=False,
        help_text="The internal ID of the source. Must be distinct from all other source IDs and cannot start with '`sentry:`'. If this is not provided, a new UUID will be generated.",
    )
    name = serializers.CharField(
        required=True,
        help_text="The human-readable name of the source.",
    )
    layout = LayoutSerializer(
        required=False,
    )
    filters = FiltersSerializer(required=False)
    url = serializers.CharField(
        required=False,
        help_text="The source's URL. Optional for HTTP sources, invalid for all others.",
    )
    username = serializers.CharField(
        required=False,
        help_text="The user name for accessing the source. Optional for HTTP sources, invalid for all others.",
    )
    password = serializers.CharField(
        required=False,
        help_text="The password for accessing the source. Optional for HTTP sources, invalid for all others.",
    )
    bucket = serializers.CharField(
        required=False,
        help_text="The GCS or S3 bucket where the source resides. Required for GCS and S3 source, invalid for HTTP sources.",
    )
    region = serializers.ChoiceField(
        choices=[
            ("us-east-2", "US East (Ohio)"),
            ("us-east-1", "US East (N. Virginia)"),
            ("us-west-1", "US West (N. California)"),
            ("us-west-2", "US West (Oregon)"),
            ("ap-east-1", "Asia Pacific (Hong Kong)"),
            ("ap-south-1", "Asia Pacific (Mumbai)"),
            ("ap-northeast-2", "Asia Pacific (Seoul)"),
            ("ap-southeast-1", "Asia Pacific (Singapore)"),
            ("ap-southeast-2", "Asia Pacific (Sydney)"),
            ("ap-northeast-1", "Asia Pacific (Tokyo)"),
            ("ca-central-1", "Canada (Central)"),
            ("cn-north-1", "China (Beijing)"),
            ("cn-northwest-1", "China (Ningxia)"),
            ("eu-central-1", "EU (Frankfurt)"),
            ("eu-west-1", "EU (Ireland)"),
            ("eu-west-2", "EU (London)"),
            ("eu-west-3", "EU (Paris)"),
            ("eu-north-1", "EU (Stockholm)"),
            ("sa-east-1", "South America (São Paulo)"),
            ("us-gov-east-1", "AWS GovCloud (US-East)"),
            ("us-gov-west-1", "AWS GovCloud (US)"),
        ],
        required=False,
        help_text="The source's [S3 region](https://docs.aws.amazon.com/general/latest/gr/s3.html). Required for S3 sources, invalid for all others.",
    )
    access_key = serializers.CharField(
        required=False,
        help_text="The [AWS Access Key](https://docs.aws.amazon.com/IAM/latest/UserGuide/security-creds.html#access-keys-and-secret-access-keys).Required for S3 sources, invalid for all others.",
    )
    secret_key = serializers.CharField(
        required=False,
        help_text="The [AWS Secret Access Key](https://docs.aws.amazon.com/IAM/latest/UserGuide/security-creds.html#access-keys-and-secret-access-keys).Required for S3 sources, invalid for all others.",
    )
    prefix = serializers.CharField(
        required=False,
        help_text="The GCS or [S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-prefixes.html) prefix. Optional for GCS and S3 sourcse, invalid for HTTP.",
    )
    client_email = serializers.CharField(
        required=False,
        help_text="The GCS email address for authentication. Required for GCS sources, invalid for all others.",
    )
    private_key = serializers.CharField(
        required=False,
        help_text="The GCS private key. Required for GCS sources if not using impersonated tokens. Invalid for all others.",
    )

    def validate(self, data):
        if data["type"] == "http":
            required = ["type", "name", "url", "layout"]
            allowed = required + ["username", "password"]
        elif data["type"] == "s3":
            required = ["type", "name", "bucket", "region", "access_key", "secret_key", "layout"]
            allowed = required + ["prefix"]
        else:
            required = ["type", "name", "bucket", "client_email", "layout"]
            allowed = required + ["prefix", "private_key"]

        missing = [field for field in required if field not in data]
        invalid = [field for field in data if field not in allowed]

        err = ""
        if missing:
            err += f"Missing fields: {missing}\n"
        if invalid:
            err += f"Invalid fields: {invalid}"

        if err:
            raise serializers.ValidationError(err)

        return data


@extend_schema(tags=["Projects"])
@region_silo_endpoint
class ProjectSymbolSourcesEndpoint(ProjectEndpoint):
    owner = ApiOwner.OWNERS_INGEST
    publish_status = {
        "GET": ApiPublishStatus.PUBLIC,
        "DELETE": ApiPublishStatus.PUBLIC,
        "POST": ApiPublishStatus.PUBLIC,
        "PUT": ApiPublishStatus.PUBLIC,
    }

    @extend_schema(
        operation_id="Retrieve a Project's Symbol Sources",
        parameters=[
            GlobalParams.ORG_ID_OR_SLUG,
            GlobalParams.PROJECT_ID_OR_SLUG,
            ProjectParams.source_id(
                "The ID of the source to look up. If this is not provided, all sources are returned.",
                False,
            ),
        ],
        responses={
            200: REDACTED_SOURCES_SCHEMA,
            403: RESPONSE_FORBIDDEN,
            404: RESPONSE_NOT_FOUND,
        },
        examples=ProjectExamples.GET_SYMBOL_SOURCES,
    )
    def get(self, request: Request, project: Project) -> Response:
        """
        List custom symbol sources configured for a project.
        """
        id = request.GET.get("id")
        custom_symbol_sources_json = project.get_option("sentry:symbol_sources") or []
        sources = parse_sources(custom_symbol_sources_json, filter_appconnect=False)
        redacted = redact_source_secrets(sources)

        if id:
            for source in redacted:
                if source["id"] == id:
                    return Response([source])
            return Response(data={"error": f"Unknown source id: {id}"}, status=404)

        return Response(redacted)

    @extend_schema(
        operation_id="Delete a Symbol Source from a Project",
        parameters=[
            GlobalParams.ORG_ID_OR_SLUG,
            GlobalParams.PROJECT_ID_OR_SLUG,
            ProjectParams.source_id("The ID of the source to delete.", True),
        ],
        responses={
            204: RESPONSE_NO_CONTENT,
            403: RESPONSE_FORBIDDEN,
            404: RESPONSE_NOT_FOUND,
        },
        examples=ProjectExamples.DELETE_SYMBOL_SOURCE,
    )
    def delete(self, request: Request, project: Project) -> Response:
        """
        Delete a custom symbol source from a project.
        """
        id = request.GET.get("id")
        custom_symbol_sources_json = project.get_option("sentry:symbol_sources") or []

        sources = parse_sources(custom_symbol_sources_json, filter_appconnect=False)

        if id:
            filtered_sources = [src for src in sources if src["id"] != id]
            if len(filtered_sources) == len(sources):
                return Response(data={"error": f"Unknown source id: {id}"}, status=404)

            serialized = orjson.dumps(filtered_sources).decode()
            project.update_option("sentry:symbol_sources", serialized)
            return Response(status=204)

        return Response(data={"error": "Missing source id"}, status=404)

    @extend_schema(
        operation_id="Add a Symbol Source to a Project",
        parameters=[GlobalParams.ORG_ID_OR_SLUG, GlobalParams.PROJECT_ID_OR_SLUG],
        request=SourceSerializer,
        responses={
            201: REDACTED_SOURCE_SCHEMA,
            400: RESPONSE_BAD_REQUEST,
            403: RESPONSE_FORBIDDEN,
        },
        examples=ProjectExamples.ADD_SYMBOL_SOURCE,
    )
    def post(self, request: Request, project: Project) -> Response:
        """
        Add a custom symbol source to a project.
        """
        custom_symbol_sources_json = project.get_option("sentry:symbol_sources") or []
        sources = parse_sources(custom_symbol_sources_json, filter_appconnect=False)

        source = request.data

        if "id" in source:
            id = source["id"]
        else:
            id = str(uuid4())
            source["id"] = id

        sources.append(source)

        try:
            validate_sources(sources)
        except InvalidSourcesError:
            return Response(status=400)

        serialized = orjson.dumps(sources).decode()
        project.update_option("sentry:symbol_sources", serialized)

        redacted = redact_source_secrets([source])
        return Response(data=redacted[0], status=201)

    @extend_schema(
        operation_id="Update a Project's Symbol Source",
        parameters=[
            GlobalParams.ORG_ID_OR_SLUG,
            GlobalParams.PROJECT_ID_OR_SLUG,
            ProjectParams.source_id("The ID of the source to update.", True),
        ],
        request=SourceSerializer,
        responses={
            200: REDACTED_SOURCE_SCHEMA,
            400: RESPONSE_BAD_REQUEST,
            403: RESPONSE_FORBIDDEN,
            404: RESPONSE_NOT_FOUND,
        },
        examples=ProjectExamples.UPDATE_SYMBOL_SOURCE,
    )
    def put(self, request: Request, project: Project) -> Response:
        """
        Update a custom symbol source in a project.
        """
        id = request.GET.get("id")
        source = request.data

        custom_symbol_sources_json = project.get_option("sentry:symbol_sources") or []
        sources = parse_sources(custom_symbol_sources_json, filter_appconnect=False)

        if id is None:
            return Response(data={"error": "Missing source id"}, status=404)

        if "id" not in source:
            source["id"] = str(uuid4())

        try:
            sources_by_id = {src["id"]: src for src in sources}
            backfill_source(source, sources_by_id)
        except InvalidSourcesError:
            return Response(status=400)
        except KeyError:
            return Response(status=400)

        found = False
        for i in range(len(sources)):
            if sources[i]["id"] == id:
                found = True
                sources[i] = source
                break

        if not found:
            return Response(data={"error": f"Unknown source id: {id}"}, status=404)

        try:
            validate_sources(sources)
        except InvalidSourcesError as e:
            return Response(data={"error": str(e)}, status=400)

        serialized = orjson.dumps(sources).decode()
        project.update_option("sentry:symbol_sources", serialized)

        redacted = redact_source_secrets([source])
        return Response(data=redacted[0], status=200)
