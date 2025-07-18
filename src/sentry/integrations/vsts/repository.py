from __future__ import annotations

import logging
from collections.abc import Mapping, MutableMapping, Sequence
from typing import Any

from sentry.integrations.types import IntegrationProviderSlug
from sentry.models.organization import Organization
from sentry.models.repository import Repository
from sentry.organizations.services.organization.model import RpcOrganization
from sentry.plugins.providers import IntegrationRepositoryProvider
from sentry.plugins.providers.integration_repository import RepositoryConfig

MAX_COMMIT_DATA_REQUESTS = 90

logger = logging.getLogger(__name__)


class VstsRepositoryProvider(IntegrationRepositoryProvider):
    name = "Azure DevOps"
    repo_provider = IntegrationProviderSlug.AZURE_DEVOPS.value

    def get_repository_data(
        self, organization: Organization, config: MutableMapping[str, Any]
    ) -> Mapping[str, str]:
        from sentry.integrations.vsts.integration import VstsIntegration

        installation = self.get_installation(config.get("installation"), organization.id)
        assert isinstance(installation, VstsIntegration), installation
        client = installation.get_client()

        repo_id = config["identifier"]

        try:
            repo = client.get_repo(repo_id)
        except Exception as e:
            raise installation.raise_error(e)
        config.update(
            {
                "instance": installation.instance,
                "project": repo["project"]["name"],
                "name": repo["name"],
                "external_id": str(repo["id"]),
                "url": repo["_links"]["web"]["href"],
            }
        )
        return config

    def build_repository_config(
        self, organization: RpcOrganization, data: dict[str, Any]
    ) -> RepositoryConfig:
        return {
            "name": data["name"],
            "external_id": data["external_id"],
            "url": data["url"],
            "config": {
                "instance": data["instance"],
                "project": data["project"],
                "name": data["name"],
            },
            "integration_id": data["installation"],
        }

    def transform_changes(
        self, patch_set: Sequence[Mapping[str, Any]]
    ) -> Sequence[Mapping[str, str]]:
        type_mapping = {"add": "A", "delete": "D", "edit": "M"}
        file_changes = []
        # https://docs.microsoft.com/en-us/rest/api/vsts/git/commits/get%20changes#versioncontrolchangetype
        for change in patch_set:
            change_type = type_mapping.get(change["changeType"])

            if change_type and change.get("item") and change["item"]["gitObjectType"] == "blob":
                file_changes.append({"path": change["item"]["path"], "type": change_type})

        return file_changes

    def zip_commit_data(
        self, repo: Repository, commit_list: list[dict[str, Any]], organization_id: int
    ) -> list[dict[str, Any]]:
        installation = self.get_installation(repo.integration_id, organization_id)
        client = installation.get_client()
        n = 0
        for commit in commit_list:
            # Azure will truncate commit comments to only the first line.
            # We need to make an additional API call to get the full commit message.
            # This is important because issue refs could be anywhere in the commit
            # message.
            if commit.get("commentTruncated", False):
                full_commit = client.get_commit(repo.external_id, commit["commitId"])
                commit["comment"] = full_commit["comment"]

            commit["patch_set"] = self.transform_changes(
                client.get_commit_filechanges(repo.external_id, commit["commitId"])
            )
            # We only fetch patch data for 90 commits.
            n += 1
            if n > MAX_COMMIT_DATA_REQUESTS:
                break

        return commit_list

    def compare_commits(
        self, repo: Repository, start_sha: str | None, end_sha: str
    ) -> Sequence[Mapping[str, str]]:
        """TODO(mgaeta): This function is kinda a mess."""
        installation = self.get_installation(repo.integration_id, repo.organization_id)
        client = installation.get_client()

        try:
            if start_sha is None:
                res = client.get_commits(repo.external_id, commit=end_sha, limit=10)
            else:
                res = client.get_commit_range(repo.external_id, start_sha, end_sha)
        except Exception as e:
            raise installation.raise_error(e)

        commits = self.zip_commit_data(repo, res["value"], repo.organization_id)
        return self._format_commits(repo, commits)

    def _format_commits(
        self, repo: Repository, commit_list: Sequence[Mapping[str, Any]]
    ) -> Sequence[Mapping[str, Any]]:
        return [
            {
                "id": c["commitId"],
                "repository": repo.name,
                "author_email": c["author"]["email"],
                "author_name": c["author"]["name"],
                "message": c["comment"],
                "patch_set": c.get("patch_set"),
                "timestamp": self.format_date(c["author"]["date"]),
            }
            for c in commit_list
        ]

    def repository_external_slug(self, repo: Repository) -> str | None:
        return repo.external_id
