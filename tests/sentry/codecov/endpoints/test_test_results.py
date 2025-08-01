from unittest.mock import MagicMock, Mock, patch

from django.urls import reverse

from sentry.codecov.endpoints.test_results.serializers import (
    TestResultNodeSerializer as NodeSerializer,
)
from sentry.testutils.cases import APITestCase

mock_graphql_response_empty = {
    "data": {
        "owner": {
            "repository": {
                "__typename": "Repository",
                "defaultBranch": "main",
                "testAnalytics": {
                    "testResults": {
                        "edges": [],
                        "pageInfo": {
                            "endCursor": None,
                            "hasNextPage": False,
                            "hasPreviousPage": False,
                            "startCursor": None,
                        },
                        "totalCount": 0,
                    }
                },
            }
        }
    }
}

mock_graphql_response_populated = {
    "data": {
        "owner": {
            "repository": {
                "__typename": "Repository",
                "defaultBranch": "another-branch",
                "testAnalytics": {
                    "testResults": {
                        "edges": [
                            {
                                "node": {
                                    "updatedAt": "2025-05-22T16:21:18.763951+00:00",
                                    "avgDuration": 0.04066228070175437,
                                    "totalDuration": 1.0,
                                    "lastDuration": 0.04066228070175437,
                                    "name": "../usr/local/lib/python3.13/site-packages/asgiref/sync.py::GetFinalYamlInteractorTest::test_when_commit_has_no_yaml",
                                    "failureRate": 0.0,
                                    "flakeRate": 0.0,
                                    "commitsFailed": 0,
                                    "totalFailCount": 0,
                                    "totalFlakyFailCount": 0,
                                    "totalSkipCount": 0,
                                    "totalPassCount": 70,
                                }
                            },
                            {
                                "node": {
                                    "updatedAt": "2025-05-22T16:21:18.763961+00:00",
                                    "avgDuration": 0.034125877192982455,
                                    "totalDuration": 1.0,
                                    "lastDuration": 0.034125877192982455,
                                    "name": "../usr/local-2/lib/python3.13/site-packages/asgiref/sync.py::GetFinalYamlInteractorTest::test_when_commit_has_yaml",
                                    "failureRate": 0.0,
                                    "flakeRate": 0.0,
                                    "commitsFailed": 0,
                                    "totalFailCount": 0,
                                    "totalFlakyFailCount": 0,
                                    "totalSkipCount": 0,
                                    "totalPassCount": 70,
                                }
                            },
                        ],
                        "pageInfo": {
                            "endCursor": "cursor123",
                            "hasNextPage": False,
                            "hasPreviousPage": False,
                            "startCursor": None,
                        },
                        "totalCount": 2,
                    }
                },
            }
        }
    }
}


class TestResultsEndpointTest(APITestCase):
    endpoint_name = "sentry-api-0-test-results"

    def setUp(self) -> None:
        super().setUp()
        self.organization = self.create_organization(owner=self.user)
        self.integration = self.create_integration(
            organization=self.organization,
            external_id="1234",
            name="testowner",
            provider="github",
        )
        self.login_as(user=self.user)

    def reverse_url(self, owner="testowner", repository="testrepo"):
        """Custom reverse URL method to handle required URL parameters"""
        return reverse(
            self.endpoint_name,
            kwargs={
                "organization_id_or_slug": self.organization.slug,
                "owner": self.integration.id,
                "repository": repository,
            },
        )

    @patch("sentry.codecov.endpoints.test_results.test_results.CodecovApiClient")
    def test_get_returns_mock_response_with_default_variables(
        self, mock_codecov_client_class: MagicMock
    ) -> None:
        mock_codecov_client_instance = Mock()
        mock_response = Mock()
        mock_response.json.return_value = mock_graphql_response_populated
        mock_codecov_client_instance.query.return_value = mock_response
        mock_codecov_client_class.return_value = mock_codecov_client_instance

        url = self.reverse_url()
        response = self.client.get(url)

        mock_codecov_client_class.assert_called_once_with(git_provider_org="testowner")

        # Verify the correct variables are passed to the GraphQL query
        expected_variables = {
            "owner": "testowner",
            "repo": "testrepo",
            "filters": {
                "branch": None,
                "parameter": None,
                "interval": "INTERVAL_30_DAY",
                "flags": None,
                "term": None,
                "test_suites": None,
            },
            "ordering": {
                "direction": "DESC",
                "parameter": "COMMITS_WHERE_FAIL",
            },
            "first": 20,
            "last": None,
            "before": None,
            "after": None,
        }

        mock_codecov_client_instance.query.assert_called_once()
        call_args = mock_codecov_client_instance.query.call_args
        assert call_args[1]["variables"] == expected_variables

        assert response.status_code == 200
        assert len(response.data["results"]) == 2
        assert response.data["pageInfo"]["endCursor"] == "cursor123"
        assert response.data["pageInfo"]["hasNextPage"] is False
        assert response.data["pageInfo"]["hasPreviousPage"] is False
        assert response.data["pageInfo"]["startCursor"] is None
        assert response.data["totalCount"] == 2

        serializer_fields = set(NodeSerializer().fields.keys())
        response_keys = set(response.data["results"][0].keys())

        assert (
            response_keys == serializer_fields
        ), f"Response keys {response_keys} don't match serializer fields {serializer_fields}"

    @patch("sentry.codecov.endpoints.test_results.test_results.CodecovApiClient")
    def test_get_with_query_parameters(self, mock_codecov_client_class: MagicMock) -> None:
        mock_codecov_client_instance = Mock()
        mock_response = Mock()
        mock_response.json.return_value = mock_graphql_response_empty
        mock_codecov_client_instance.query.return_value = mock_response
        mock_codecov_client_class.return_value = mock_codecov_client_instance

        url = self.reverse_url()
        query_params = {
            "branch": "develop",
            "filterBy": "FLAKY_TESTS",
            "sortBy": "-AVG_DURATION",
            "interval": "INTERVAL_7_DAY",
            "limit": "10",
            "testSuites": ["../usr/local", "../usr/local-2"],
        }
        response = self.client.get(url, query_params)

        # Verify the correct variables are passed with custom query parameters
        expected_variables = {
            "owner": "testowner",
            "repo": "testrepo",
            "filters": {
                "branch": "develop",
                "parameter": "FLAKY_TESTS",
                "interval": "INTERVAL_7_DAY",
                "flags": None,
                "term": None,
                "test_suites": ["../usr/local", "../usr/local-2"],
            },
            "ordering": {
                "direction": "DESC",
                "parameter": "AVG_DURATION",
            },
            "first": 10,
            "last": None,
            "before": None,
            "after": None,
        }

        call_args = mock_codecov_client_instance.query.call_args
        assert call_args[1]["variables"] == expected_variables
        assert response.status_code == 200

    @patch("sentry.codecov.endpoints.test_results.test_results.CodecovApiClient")
    def test_get_with_term_filter(self, mock_codecov_client_class: MagicMock) -> None:
        mock_codecov_client_instance = Mock()
        mock_response = Mock()
        mock_response.json.return_value = mock_graphql_response_empty
        mock_codecov_client_instance.query.return_value = mock_response
        mock_codecov_client_class.return_value = mock_codecov_client_instance

        url = self.reverse_url()
        query_params = {
            "term": "test::function_with_underscores-and-dashes",
            "branch": "develop",
            "filterBy": "FLAKY_TESTS",
            "sortBy": "AVG_DURATION",
            "interval": "INTERVAL_7_DAY",
            "limit": "15",
        }
        response = self.client.get(url, query_params)

        expected_variables = {
            "owner": "testowner",
            "repo": "testrepo",
            "filters": {
                "branch": "develop",
                "parameter": "FLAKY_TESTS",
                "interval": "INTERVAL_7_DAY",
                "flags": None,
                "term": "test::function_with_underscores-and-dashes",
                "test_suites": None,
            },
            "ordering": {
                "direction": "ASC",
                "parameter": "AVG_DURATION",
            },
            "first": 15,
            "last": None,
            "before": None,
            "after": None,
        }

        call_args = mock_codecov_client_instance.query.call_args
        assert call_args[1]["variables"] == expected_variables
        assert response.status_code == 200

    @patch("sentry.codecov.endpoints.test_results.test_results.CodecovApiClient")
    def test_get_with_cursor_alone_uses_default_limit_and_navigation(
        self, mock_codecov_client_class
    ):
        mock_codecov_client_instance = Mock()
        mock_response = Mock()
        mock_response.json.return_value = mock_graphql_response_empty
        mock_codecov_client_instance.query.return_value = mock_response
        mock_codecov_client_class.return_value = mock_codecov_client_instance

        url = self.reverse_url()
        query_params = {"cursor": "some-cursor"}
        response = self.client.get(url, query_params)

        expected_variables = {
            "owner": "testowner",
            "repo": "testrepo",
            "filters": {
                "branch": None,
                "parameter": None,
                "interval": "INTERVAL_30_DAY",
                "flags": None,
                "term": None,
                "test_suites": None,
            },
            "ordering": {
                "direction": "DESC",
                "parameter": "COMMITS_WHERE_FAIL",
            },
            "first": 20,
            "last": None,
            "before": None,
            "after": "some-cursor",
        }

        call_args = mock_codecov_client_instance.query.call_args
        assert call_args[1]["variables"] == expected_variables
        assert response.status_code == 200

    @patch("sentry.codecov.endpoints.test_results.test_results.CodecovApiClient")
    def test_get_with_cursor_and_direction(self, mock_codecov_client_class: MagicMock) -> None:
        mock_codecov_client_instance = Mock()
        mock_response = Mock()
        mock_response.json.return_value = mock_graphql_response_empty
        mock_codecov_client_instance.query.return_value = mock_response
        mock_codecov_client_class.return_value = mock_codecov_client_instance

        url = self.reverse_url()
        query_params = {"cursor": "cursor123", "limit": "10", "navigation": "prev"}
        response = self.client.get(url, query_params)

        expected_variables = {
            "owner": "testowner",
            "repo": "testrepo",
            "filters": {
                "branch": None,
                "parameter": None,
                "interval": "INTERVAL_30_DAY",
                "flags": None,
                "term": None,
                "test_suites": None,
            },
            "ordering": {
                "direction": "DESC",
                "parameter": "COMMITS_WHERE_FAIL",
            },
            "first": None,
            "last": 10,
            "before": "cursor123",
            "after": None,
        }

        call_args = mock_codecov_client_instance.query.call_args
        assert call_args[1]["variables"] == expected_variables
        assert response.status_code == 200

    def test_get_with_negative_limit_returns_bad_request(self) -> None:
        url = self.reverse_url()
        query_params = {"limit": "-5"}
        response = self.client.get(url, query_params)

        assert response.status_code == 400
        assert response.data == {"details": "provided `limit` parameter must be a positive integer"}

    def test_get_with_limit_as_string_returns_bad_request(self) -> None:
        url = self.reverse_url()
        query_params = {"limit": "asdf"}
        response = self.client.get(url, query_params)

        assert response.status_code == 400
        assert response.data == {"details": "provided `limit` parameter must be a positive integer"}
