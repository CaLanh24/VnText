# WORKFLOW — bridge Codex (lưu trữ 2026-11-25)

Tách nguyên văn từ `docs/WORKFLOW.md` @ `a7bd48b`. Chỉ áp dụng khi điều phối qua bridge Codex; Claude không dùng các API này.

## Compact bridge results at the caller

For read_agent, inspect structuredContent.agent, structuredContent.latest_result and cursor before rendering any tool output. Use tests/lib/dev_projection.py (latest) for log/report projection. A missing structured result is UNKNOWN, not permission to dump text history. In functions.exec use `const r = await tools.<read_agent>(...); const d = r.structuredContent || {}; text({agent: {id:d.agent?.id,status:d.agent?.status || d.agent?.state}, latest_result:d.latest_result?.payload?.result,cursor:d.cursor});`. Pagination/history is a separate explicit diagnostic action. No shared bridge reconnect or code mutation is needed for this caller contract.
