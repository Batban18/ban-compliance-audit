#!/usr/bin/env python3
"""Gap Analysis Server — HTTP MCP server on :5004 for gap identification and remediation."""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastmcp import FastMCP
import aiosqlite

DB_PATH = os.environ.get("DB_PATH", "compliance.db")
mcp = FastMCP("gap-analysis-server")


@mcp.tool()
async def get_all_gaps(framework: str) -> list[dict]:
    """Get all gaps for a framework, both open and resolved."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT g.*, c.title as control_title, c.category
               FROM gaps g JOIN controls c ON g.control_id=c.id
               WHERE g.framework_id=? ORDER BY g.severity, g.status, g.due_date""",
            (framework,)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


@mcp.tool()
async def get_critical_gaps(framework: str) -> list[dict]:
    """Get only critical and high severity open gaps for a framework."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT g.*, c.title as control_title, c.category
               FROM gaps g JOIN controls c ON g.control_id=c.id
               WHERE g.framework_id=? AND g.severity IN ('critical','high') AND g.status='open'
               ORDER BY g.severity, g.due_date""",
            (framework,)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


@mcp.tool()
async def get_gap_detail(gap_id: int) -> dict:
    """Get full details for a specific gap."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT g.*, c.title as control_title, c.description as control_description,
                      c.guidance, f.name as framework_name
               FROM gaps g
               JOIN controls c ON g.control_id=c.id
               JOIN frameworks f ON g.framework_id=f.id
               WHERE g.id=?""",
            (gap_id,)
        ) as cur:
            row = await cur.fetchone()
            if not row:
                return {"error": f"Gap #{gap_id} not found"}
            return dict(row)


@mcp.tool()
async def mark_gap_resolved(gap_id: int) -> dict:
    """Mark a compliance gap as resolved."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, status FROM gaps WHERE id=?", (gap_id,)) as cur:
            row = await cur.fetchone()
            if not row:
                return {"error": f"Gap #{gap_id} not found"}
            if row[1] == "resolved":
                return {"message": f"Gap #{gap_id} is already resolved"}

        await db.execute(
            "UPDATE gaps SET status='resolved', resolved_at=datetime('now') WHERE id=?",
            (gap_id,)
        )
        await db.commit()
        return {"success": True, "gap_id": gap_id, "status": "resolved", "resolved_at": datetime.now().isoformat()}


@mcp.tool()
async def get_gap_summary() -> dict:
    """Get an aggregated gap summary across all frameworks."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            "SELECT framework_id, severity, COUNT(*) as cnt FROM gaps WHERE status='open' GROUP BY framework_id, severity"
        ) as cur:
            by_fw_sev = await cur.fetchall()

        async with db.execute(
            "SELECT severity, COUNT(*) as cnt FROM gaps WHERE status='open' GROUP BY severity"
        ) as cur:
            by_severity = {r["severity"]: r["cnt"] for r in await cur.fetchall()}

        async with db.execute("SELECT COUNT(*) FROM gaps WHERE status='open'") as cur:
            total_open = (await cur.fetchone())[0]

        async with db.execute("SELECT COUNT(*) FROM gaps WHERE status='resolved'") as cur:
            total_resolved = (await cur.fetchone())[0]

        async with db.execute(
            "SELECT COUNT(*) FROM gaps WHERE status='open' AND due_date < date('now')"
        ) as cur:
            overdue = (await cur.fetchone())[0]

    fw_breakdown = {}
    for r in by_fw_sev:
        fw = r["framework_id"]
        if fw not in fw_breakdown:
            fw_breakdown[fw] = {}
        fw_breakdown[fw][r["severity"]] = r["cnt"]

    return {
        "total_open": total_open,
        "total_resolved": total_resolved,
        "overdue": overdue,
        "by_severity": by_severity,
        "by_framework": fw_breakdown,
    }


if __name__ == "__main__":
    import uvicorn
    app = mcp.http_app()
    uvicorn.run(app, host="0.0.0.0", port=5004, log_level="warning")
