import tempfile
import unittest
from pathlib import Path

from lab_utils.governance.audit import AuditLogger
from lab_utils.governance.guard import GovernanceGuard
from lab_utils.routing_tool import suggest_routing
from lab_utils.semantic_router import AgentCapability, SemanticRouter
from mcp_server.research_tools_server import _count_words


class LabExerciseTests(unittest.TestCase):
    def _guard(self) -> GovernanceGuard:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        audit_path = Path(temp_dir.name) / "audit.jsonl"
        return GovernanceGuard(audit=AuditLogger(audit_path))

    def test_count_words(self):
        self.assertEqual(_count_words("MCP and A2A orchestration")["word_count"], 4)

    def test_search_documents_blocks_password(self):
        decision = self._guard().authorize_mcp_tool(
            actor_id="orchestrator",
            tool_name="search_documents",
            arguments={"query": "find password rotation policy"},
        )
        self.assertTrue(decision.blocked)
        self.assertIn("password", decision.reason)

    def test_invalid_caller_cannot_open_mcp_connection(self):
        decision = self._guard().authorize_mcp_connection("search_agent")
        self.assertTrue(decision.blocked)

    def test_route_with_chain_uses_ordered_fallback(self):
        router = SemanticRouter(
            agents=[
                AgentCapability("search_agent", "web search documents", ["search"]),
                AgentCapability("database_agent", "sql metrics", ["database"]),
            ],
            threshold=0.9,
        )
        selected = router.route_with_chain(
            "ambiguous request",
            ["search_agent", "database_agent", "orchestrator"],
        )
        self.assertEqual(selected, "search_agent")

    def test_suggest_routing_select_metrics_goes_to_database(self):
        result = suggest_routing("SELECT độ trễ trung bình từ agent_metrics")
        self.assertEqual(result["recommended_agent"], "database_agent")


if __name__ == "__main__":
    unittest.main()
