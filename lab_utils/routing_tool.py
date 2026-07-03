"""Semantic routing tool — gợi ý specialist cho orchestrator (capstone)."""

from __future__ import annotations

import re

from lab_utils.semantic_router import AgentCapability, SemanticRouter

_DEFAULT_AGENTS = [
    AgentCapability(
        name="search_agent",
        description="Tìm kiếm web tài liệu nghiên cứu bằng chứng",
        tags=["search", "web", "documents"],
    ),
    AgentCapability(
        name="database_agent",
        description="SQL metrics phân tích database truy vấn SELECT",
        tags=["sql", "metrics", "database"],
    ),
    AgentCapability(
        name="synthesis_agent",
        description="Tóm tắt kết hợp kết quả thành báo cáo cuối",
        tags=["summary", "report", "synthesis"],
    ),
]

_router = SemanticRouter(agents=_DEFAULT_AGENTS)


def _is_database_request(user_request: str) -> bool:
    text = user_request.lower()
    sql_patterns = [
        r"\bselect\b",
        r"\bfrom\b",
        r"\bwhere\b",
        r"\bsql\b",
        r"\bagent_metrics\b",
    ]
    metric_terms = ("latency", "metrics", "database", "truy vấn", "độ trễ")
    return any(re.search(pattern, text) for pattern in sql_patterns) or any(
        term in text for term in metric_terms
    )


def suggest_routing(user_request: str) -> dict:
    """Gợi ý specialist phù hợp cho yêu cầu người dùng (chỉ mang tính tư vấn).

    Orchestrator vẫn quyết định cuối cùng; tool này dùng semantic router
    bag-of-words để xếp hạng search_agent, database_agent, synthesis_agent.

    Args:
        user_request: Câu hỏi hoặc nhiệm vụ nghiên cứu từ người dùng.

    Returns:
        Dict với recommended_agent, top_candidates (name + score), fallback.
    """
    candidates = _router.route(user_request, top_k=3)
    recommended = _router.route_with_fallback(user_request, fallback="orchestrator")
    if _is_database_request(user_request):
        recommended = "database_agent"
    return {
        "recommended_agent": recommended,
        "top_candidates": [
            {"agent": name, "score": round(score, 3)} for name, score in candidates
        ],
        "fallback": "orchestrator",
        "note": "Gợi ý mang tính tư vấn — orchestrator quyết định MCP vs A2A.",
    }
