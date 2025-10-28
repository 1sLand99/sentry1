from datetime import timedelta
from uuid import uuid4

from django.urls import reverse

from sentry.testutils.cases import APITestCase, BaseSpansTestCase, SpanTestCase
from sentry.testutils.helpers import parse_link_header
from sentry.testutils.helpers.datetime import before_now

LLM_TOKENS = 100
LLM_COST = 0.001


class OrganizationAIConversationsEndpointTest(BaseSpansTestCase, SpanTestCase, APITestCase):
    view = "sentry-api-0-organization-ai-conversations"

    def setUp(self) -> None:
        super().setUp()
        self.login_as(user=self.user)

    def store_ai_span(
        self,
        conversation_id,
        timestamp,
        op="gen_ai.chat",
        description=None,
        status="ok",
        operation_type=None,
        tokens=None,
        cost=None,
        trace_id=None,
        agent_name=None,
    ):
        span_data = {"gen_ai.conversation.id": conversation_id}
        if operation_type:
            span_data["gen_ai.operation.type"] = operation_type
        if tokens is not None:
            span_data["gen_ai.usage.total_tokens"] = tokens
        if cost is not None:
            span_data["gen_ai.usage.total_cost"] = cost
        if agent_name is not None:
            span_data["gen_ai.agent.name"] = agent_name

        extra_data = {
            "description": description or "default",
            "sentry_tags": {"status": status, "op": op},
            "data": span_data,
        }
        if trace_id:
            extra_data["trace_id"] = trace_id

        span = self.create_span(
            extra_data,
            start_ts=timestamp,
        )
        self.store_spans([span], is_eap=True)
        return span

    def do_request(self, query=None, features=None, **kwargs):
        if features is None:
            features = ["organizations:gen-ai-conversations"]

        query = query or {}

        with self.feature(features):
            return self.client.get(
                reverse(
                    self.view,
                    kwargs={"organization_id_or_slug": self.organization.slug},
                ),
                query,
                format="json",
                **kwargs,
            )

    def test_no_feature(self) -> None:
        response = self.do_request(features=[])
        assert response.status_code == 404

    def test_no_project(self) -> None:
        response = self.do_request()
        assert response.status_code == 404

    def test_no_conversations(self) -> None:
        """Test endpoint returns empty list when there are no spans with gen_ai.conversation.id"""
        now = before_now(days=10).replace(microsecond=0)

        span = self.create_span(
            {"description": "test", "sentry_tags": {"status": "ok"}},
            start_ts=now,
        )
        self.store_spans([span], is_eap=True)

        query = {
            "project": [self.project.id],
            "start": now.isoformat(),
            "end": (now + timedelta(hours=1)).isoformat(),
        }

        response = self.do_request(query)
        assert response.status_code == 200, response.data
        assert len(response.data) == 0

    def test_single_conversation_single_trace(self) -> None:
        """Test a conversation with all spans in a single trace"""
        now = before_now(days=20).replace(microsecond=0)
        trace_id = uuid4().hex
        conversation_id = uuid4().hex

        self.store_ai_span(
            conversation_id=conversation_id,
            timestamp=now - timedelta(seconds=4),
            op="gen_ai.invoke_agent",
            description="Customer Support Agent",
            agent_name="Customer Support Agent",
            trace_id=trace_id,
        )

        self.store_ai_span(
            conversation_id=conversation_id,
            timestamp=now - timedelta(seconds=3),
            op="gen_ai.chat",
            operation_type="ai_client",
            tokens=LLM_TOKENS,
            cost=LLM_COST,
            trace_id=trace_id,
        )

        self.store_ai_span(
            conversation_id=conversation_id,
            timestamp=now - timedelta(seconds=2),
            op="gen_ai.execute_tool",
            trace_id=trace_id,
        )

        self.store_ai_span(
            conversation_id=conversation_id,
            timestamp=now - timedelta(seconds=1),
            op="gen_ai.invoke_agent",
            description="Response Generator",
            agent_name="Response Generator",
            trace_id=trace_id,
        )

        self.store_ai_span(
            conversation_id=conversation_id,
            timestamp=now,
            op="gen_ai.chat",
            status="internal_error",
            operation_type="ai_client",
            tokens=LLM_TOKENS,
            cost=LLM_COST,
            trace_id=trace_id,
        )

        query = {
            "project": [self.project.id],
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": (now + timedelta(hours=1)).isoformat(),
        }

        response = self.do_request(query)
        assert response.status_code == 200
        assert len(response.data) == 1

        conversation = response.data[0]
        assert conversation["conversationId"] == conversation_id
        assert conversation["errors"] == 1
        assert conversation["llmCalls"] == 2
        assert conversation["toolCalls"] == 1
        assert conversation["totalTokens"] == LLM_TOKENS * 2
        assert conversation["totalCost"] == LLM_COST * 2
        assert conversation["traceCount"] == 1
        assert conversation["duration"] > 0
        assert conversation["timestamp"] > 0
        assert conversation["flow"] == ["Customer Support Agent", "Response Generator"]
        assert len(conversation["traceIds"]) == 1
        assert conversation["traceIds"][0] == trace_id

    def test_conversation_spanning_multiple_traces(self) -> None:
        """Test a conversation with spans across multiple traces"""
        now = before_now(days=30).replace(microsecond=0)
        conversation_id = uuid4().hex
        trace_id_1 = uuid4().hex
        trace_id_2 = uuid4().hex

        self.store_ai_span(
            conversation_id=conversation_id,
            timestamp=now - timedelta(seconds=3),
            op="gen_ai.invoke_agent",
            description="Research Agent",
            agent_name="Research Agent",
            trace_id=trace_id_1,
        )

        self.store_ai_span(
            conversation_id=conversation_id,
            timestamp=now - timedelta(seconds=2),
            op="gen_ai.chat",
            operation_type="ai_client",
            tokens=LLM_TOKENS,
            cost=LLM_COST,
            trace_id=trace_id_1,
        )

        self.store_ai_span(
            conversation_id=conversation_id,
            timestamp=now - timedelta(seconds=1),
            op="gen_ai.invoke_agent",
            description="Summarization Agent",
            agent_name="Summarization Agent",
            trace_id=trace_id_2,
        )

        self.store_ai_span(
            conversation_id=conversation_id,
            timestamp=now,
            op="gen_ai.chat",
            operation_type="ai_client",
            tokens=LLM_TOKENS,
            cost=LLM_COST,
            trace_id=trace_id_2,
        )

        query = {
            "project": [self.project.id],
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": (now + timedelta(hours=1)).isoformat(),
        }

        response = self.do_request(query)
        assert response.status_code == 200
        assert len(response.data) == 1

        conversation = response.data[0]
        assert conversation["conversationId"] == conversation_id
        assert conversation["errors"] == 0
        assert conversation["llmCalls"] == 2
        assert conversation["toolCalls"] == 0
        assert conversation["totalTokens"] == LLM_TOKENS * 2
        assert conversation["totalCost"] == LLM_COST * 2
        assert conversation["traceCount"] == 2
        assert conversation["flow"] == ["Research Agent", "Summarization Agent"]
        assert len(conversation["traceIds"]) == 2
        assert set(conversation["traceIds"]) == {trace_id_1, trace_id_2}

    def test_multiple_conversations(self) -> None:
        """Test multiple conversations are returned correctly"""
        now = before_now(days=40).replace(microsecond=0)
        conversation_id_1 = uuid4().hex
        conversation_id_2 = uuid4().hex

        self.store_ai_span(
            conversation_id=conversation_id_1,
            timestamp=now - timedelta(minutes=2),
            op="gen_ai.chat",
            operation_type="ai_client",
            tokens=LLM_TOKENS,
            cost=LLM_COST,
        )

        self.store_ai_span(
            conversation_id=conversation_id_2,
            timestamp=now - timedelta(minutes=1),
            op="gen_ai.chat",
            operation_type="ai_client",
            tokens=LLM_TOKENS,
            cost=LLM_COST,
        )

        query = {
            "project": [self.project.id],
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": (now + timedelta(hours=1)).isoformat(),
        }

        response = self.do_request(query)
        assert response.status_code == 200
        assert len(response.data) == 2

        assert response.data[0]["conversationId"] == conversation_id_2
        assert response.data[1]["conversationId"] == conversation_id_1

    def test_pagination(self) -> None:
        """Test pagination works correctly"""
        now = before_now(days=50).replace(microsecond=0)

        for i in range(3):
            conversation_id = uuid4().hex
            span = self.create_span(
                {
                    "description": "test",
                    "sentry_tags": {"status": "ok", "op": "gen_ai.chat"},
                    "data": {
                        "gen_ai.conversation.id": conversation_id,
                    },
                },
                start_ts=now - timedelta(minutes=i),
            )
            self.store_spans([span], is_eap=True)

        query = {
            "project": [self.project.id],
            "per_page": "2",
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": (now + timedelta(hours=1)).isoformat(),
        }

        response = self.do_request(query)
        assert response.status_code == 200
        assert len(response.data) == 2

        links = parse_link_header(response.headers["Link"])
        next_link = next(link for link in links.values() if link["rel"] == "next")
        assert next_link["results"] == "true"
        assert next_link["cursor"]

        query["cursor"] = next_link["cursor"]
        response = self.do_request(query)
        assert response.status_code == 200
        assert len(response.data) == 1

    def test_zero_values(self) -> None:
        """Test conversations with zero values for metrics and no agent spans"""
        now = before_now(days=60).replace(microsecond=0)
        conversation_id = uuid4().hex

        span = self.create_span(
            {
                "description": "test",
                "sentry_tags": {"status": "ok", "op": "gen_ai.chat"},
                "data": {
                    "gen_ai.conversation.id": conversation_id,
                },
            },
            start_ts=now,
        )
        self.store_spans([span], is_eap=True)

        query = {
            "project": [self.project.id],
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": (now + timedelta(hours=1)).isoformat(),
        }

        response = self.do_request(query)
        assert response.status_code == 200, response.data
        assert len(response.data) == 1

        conversation = response.data[0]
        assert conversation["conversationId"] == conversation_id
        assert conversation["errors"] == 0
        assert conversation["llmCalls"] == 0
        assert conversation["toolCalls"] == 0
        assert conversation["totalTokens"] == 0
        assert conversation["totalCost"] == 0.0
        assert conversation["flow"] == []
        assert len(conversation["traceIds"]) == 1

    def test_mixed_error_statuses(self) -> None:
        """Test that various error statuses are counted correctly"""
        now = before_now(days=70).replace(microsecond=0)
        conversation_id = uuid4().hex
        trace_id = uuid4().hex

        statuses = [
            "ok",
            "cancelled",
            "unknown",
            "internal_error",
            "resource_exhausted",
            "invalid_argument",
        ]

        for i, span_status in enumerate(statuses):
            self.store_ai_span(
                conversation_id=conversation_id,
                timestamp=now - timedelta(seconds=i),
                op="gen_ai.chat",
                status=span_status,
                trace_id=trace_id,
            )

        query = {
            "project": [self.project.id],
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": (now + timedelta(hours=1)).isoformat(),
        }

        response = self.do_request(query)
        assert response.status_code == 200
        assert len(response.data) == 1

        conversation = response.data[0]
        assert conversation["errors"] == 3

    def test_flow_ordering(self) -> None:
        """Test that flow agents are ordered by timestamp"""
        now = before_now(days=80).replace(microsecond=0)
        conversation_id = uuid4().hex
        trace_id = uuid4().hex

        agents = [
            ("Agent A", now - timedelta(seconds=5)),
            ("Agent B", now - timedelta(seconds=3)),
            ("Agent C", now - timedelta(seconds=1)),
        ]

        for agent_name, timestamp in agents:
            self.store_ai_span(
                conversation_id=conversation_id,
                timestamp=timestamp,
                op="gen_ai.invoke_agent",
                description=agent_name,
                agent_name=agent_name,
                trace_id=trace_id,
            )

        query = {
            "project": [self.project.id],
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": (now + timedelta(hours=1)).isoformat(),
        }

        response = self.do_request(query)
        assert response.status_code == 200
        assert len(response.data) == 1

        conversation = response.data[0]
        assert conversation["flow"] == ["Agent A", "Agent B", "Agent C"]

    def test_complete_conversation_data_across_time_range(self) -> None:
        """Test that conversations show complete data even when spans are outside time range"""
        now = before_now(days=15).replace(microsecond=0)
        conversation_id = uuid4().hex
        trace_id = uuid4().hex

        old_span_time = now - timedelta(days=7)
        recent_span_time = now - timedelta(minutes=10)

        self.store_ai_span(
            conversation_id=conversation_id,
            timestamp=old_span_time,
            op="gen_ai.chat",
            operation_type="ai_client",
            tokens=100,
            cost=0.01,
            trace_id=trace_id,
        )

        self.store_ai_span(
            conversation_id=conversation_id,
            timestamp=recent_span_time,
            op="gen_ai.chat",
            operation_type="ai_client",
            tokens=50,
            cost=0.005,
            trace_id=trace_id,
        )

        query = {
            "project": [self.project.id],
            "start": (now - timedelta(hours=2)).isoformat(),
            "end": (now + timedelta(hours=1)).isoformat(),
        }

        response = self.do_request(query)
        assert response.status_code == 200
        assert len(response.data) == 1

        conversation = response.data[0]
        assert conversation["conversationId"] == conversation_id
        assert conversation["llmCalls"] == 1
        assert conversation["totalTokens"] == 50
        assert conversation["totalCost"] == 0.005
