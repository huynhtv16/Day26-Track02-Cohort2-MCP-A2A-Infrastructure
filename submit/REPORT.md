# Báo cáo Lab Ngày 26 - MCP/A2A & Agentic Routing

## Trạng thái chạy project

- ADK Web đã chạy được tại `http://127.0.0.1:8000`.
- `orchestrator` trả lời được prompt `hello`.
- Terminal ghi nhận Gemini API trả về `HTTP/1.1 200 OK`, chứng tỏ `GOOGLE_API_KEY` hoạt động.
- A2A specialists gồm `search_agent`, `database_agent`, `synthesis_agent` được thiết kế chạy lần lượt ở các cổng `8001`, `8002`, `8003`.

## Bài tập 1.1 - Khám phá MCP Server

1. Ba tool ban đầu được expose trong `mcp_server/research_tools_server.py`:
   - `search_documents`: tìm kiếm trong kho tài liệu mô phỏng.
   - `sql_query`: chạy truy vấn SQL chỉ đọc trên bảng metrics agent.
   - `summarize_text`: tóm tắt văn bản thành các gạch đầu dòng.

2. `_sql_query` và governance enforce an toàn theo hai lớp:
   - `GovernanceGuard.authorize_mcp_tool()` kiểm tra policy trước khi tool chạy.
   - `_validate_sql()` chỉ cho câu lệnh bắt đầu bằng `SELECT`, chặn các từ khóa ghi/DDL như `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `TRUNCATE`, và chỉ cho truy vấn bảng `agent_metrics`.
   - `_sql_query()` chỉ trả dữ liệu nếu SQL có nhắc tới `AGENT_METRICS`; nếu không thì trả danh sách rỗng.

3. Dùng transport `stdio` khi dev local vì:
   - Dễ chạy MCP server như subprocess cục bộ.
   - Không cần mở thêm HTTP service, auth, TLS hay network config.
   - Phù hợp notebook/lab vì ADK có thể spawn MCP server tự động qua `McpToolset`.

## Bài tập 1.2 - Thêm MCP tool thứ tư

Đã thêm tool `count_words` trong `mcp_server/research_tools_server.py`.

Các thay đổi chính:

- Thêm `count_words` vào `list_tools()` với schema:
  - input: `text: string`
  - output: JSON có `word_count`
- Thêm hàm `_count_words(text: str) -> dict[str, int]`.
- Thêm nhánh xử lý `count_words` trong `call_tool()`.
- Thêm `count_words` vào policy tại `lab_utils/governance/policy.json`, nên orchestrator tự nhận tool này qua `guard.get_allowed_mcp_tools("orchestrator")`.

Ví dụ kết quả:

```python
_count_words("MCP and A2A orchestration")
# {"word_count": 4}
```

## Bài tập 2.1 - A2A vs Sub-Agent Local

| Tiêu chí | A2A (Remote) | Sub-Agent Local |
|---|---|---|
| Triển khai | Agent chạy như service riêng, có agent card và endpoint riêng | Agent nằm cùng process/codebase với orchestrator |
| Hiệu năng | Có overhead network/serialization nhưng scale độc lập | Nhanh hơn vì gọi nội bộ, ít overhead |
| Cô lập state | Cô lập tốt hơn, mỗi service tự quản lý state/runtime | State dễ chia sẻ trong cùng runtime nhưng dễ coupling |
| Phù hợp khi | Nhiều team, nhiều service, cần deploy/scale/observe độc lập | Prototype, demo nhỏ, logic đơn giản, cùng ownership |

Nên chọn A2A khi specialist agent cần chạy độc lập, có vòng đời riêng, có team sở hữu riêng, hoặc cần scale/monitor theo kiểu microservice. Nên chọn local sub-agent khi hệ thống nhỏ, cần tốc độ triển khai nhanh và chưa cần ranh giới service rõ ràng.

## Bài tập 3.1 - Fallback Chain

Đã thêm method `route_with_chain()` trong `lab_utils/semantic_router.py`.

Ý tưởng:

- Đầu tiên router vẫn thử route chính bằng cosine similarity.
- Nếu điểm route chính đạt ngưỡng `threshold`, trả agent đó.
- Nếu điểm thấp, trả fallback đầu tiên hợp lệ trong chain.
- Nếu chain không có lựa chọn hợp lệ, trả `orchestrator`.

Ví dụ:

```python
router.route_with_chain(
    "ambiguous request",
    ["search_agent", "database_agent", "orchestrator"],
)
# "search_agent"
```

## Bài tập ADK Web W1-W5

| Mã | Prompt | Kết quả kỳ vọng |
|---|---|---|
| W1 | Tìm web về multi-agent orchestration và transfer sang `search_agent` | Orchestrator gọi A2A `search_agent`; Trace có `transfer_to_agent`; trả kết quả search |
| W2 | Dùng `search_documents`, `sql_query`, rồi tóm tắt | Orchestrator gọi MCP tools `search_documents`, `sql_query`, `summarize_text` |
| W3 | Ủy quyền `synthesis_agent` tổng hợp executive report | Orchestrator gọi A2A `synthesis_agent`; trả `executive_summary` và `key_points` |
| W4 | Gọi `suggest_routing` cho câu hỏi SELECT độ trễ | Tool gợi ý `database_agent` vì request liên quan SQL/metrics |
| W5 | `DROP TABLE agent_metrics` | Governance chặn vì chỉ cho phép SQL `SELECT` read-only |

Quan sát cần ghi khi demo:

- Session state có `trace_id` tự sinh.
- Trace hiển thị agent/tool được gọi: `orchestrator`, `search_agent`, `database_agent`, `synthesis_agent`, MCP tools.
- `logs/governance_audit.jsonl` có các dòng audit với verdict `allow`, `deny` hoặc `hitl_required`.

## Bài tập 5.1 - Thiết kế chính sách Governance

| Agent | Tool được gọi | Cần phê duyệt người | Rate limit | Giới hạn thực thi |
|---|---|---|---|---|
| `orchestrator` | MCP: `search_documents`, `sql_query`, `summarize_text`, `count_words`; A2A tới 3 specialist | Dispatch thiếu `trace_id`, chi phí vượt trần, target chưa đăng ký | 30 calls/phút | 50 tool calls/task, 300 giây/task, trần $10/task |
| `search_agent` | `search_web` | Truy vấn chứa dữ liệu nhạy cảm hoặc từ khóa bị policy chặn | 30 calls/phút | 50 tool calls/task |
| `database_agent` | `run_sql_query` chỉ `SELECT` trên `agent_metrics` | SQL có PII hoặc yêu cầu ngoài policy | 30 calls/phút | Chỉ read-only, chặn DDL/DML |
| `synthesis_agent` | `synthesize_report` | Input vượt giới hạn hoặc yêu cầu hành động ghi/gửi ra ngoài | 30 calls/phút | Chỉ tổng hợp dữ liệu đã có, không thu thập dữ liệu mới |

## Bài tập 5.2 - Mở rộng governance

Đã kiểm tra và cập nhật policy:

- `synthesis_agent` đã có trong `allowed_targets` của `orchestrator`.
- Đã thêm rule chặn từ khóa `password` cho `search_documents`:

```json
"blocked_keywords": ["password"]
```

- Đã cập nhật `GovernanceGuard` để đọc `blocked_keywords` và trả verdict `deny` nếu query chứa từ khóa bị chặn.
- Đã thêm test đảm bảo caller không hợp lệ không mở được MCP connection.

## Kiểm thử

Đã thêm test tại `tests/test_lab_exercises.py`.

Chạy bằng:

```bash
.venv/bin/python -m unittest tests/test_lab_exercises.py
```

Kết quả kiểm thử cuối:

```text
Ran 5 tests in 0.001s
OK
```

Các test bao phủ:

- `count_words` đếm đúng số từ.
- `search_documents` chặn query chứa `password`.
- Caller không hợp lệ không mở được MCP connection.
- `route_with_chain()` dùng fallback theo thứ tự.
- `suggest_routing("SELECT độ trễ trung bình từ agent_metrics")` trả `database_agent`.

## Checklist capstone

- [x] MCP server với 4 tool: `search_documents`, `sql_query`, `summarize_text`, `count_words`
- [x] Agent registry có health check
- [x] Semantic router + `suggest_routing` tool trên orchestrator
- [x] Search agent expose qua `to_a2a()` cổng 8001
- [x] Database agent expose qua `to_a2a()` cổng 8002
- [x] **Synthesis agent** expose qua `to_a2a()` cổng 8003
- [x] Orchestrator tiêu thụ cả ba qua `RemoteA2aAgent`
- [x] ADK Web demo — 5 prompt W1-W5 ghi kết quả
- [x] Trace ID tự sinh trong ADK Web
- [x] Chính sách governance ghi audit (`logs/governance_audit.jsonl`)
- [x] ADK Web chạy được với Gemini API
