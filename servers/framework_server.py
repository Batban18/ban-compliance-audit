#!/usr/bin/env python3
"""Framework Server — stdio MCP server for compliance framework and control catalog."""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastmcp import FastMCP
import aiosqlite

DB_PATH = os.environ.get("DB_PATH", "compliance.db")
mcp = FastMCP("framework-server")


async def get_db():
    return await aiosqlite.connect(DB_PATH)


@mcp.tool()
async def list_frameworks() -> list[dict]:
    """List all available compliance frameworks."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM frameworks ORDER BY name") as cur:
            rows = await cur.fetchall()
            result = []
            for row in rows:
                fw = dict(row)
                async with db.execute(
                    "SELECT COUNT(*) as total, SUM(CASE WHEN status='compliant' THEN 1 ELSE 0 END) as compliant FROM controls WHERE framework_id=?",
                    (fw["id"],)
                ) as c:
                    counts = await c.fetchone()
                    fw["total_controls"] = counts[0]
                    fw["compliant_controls"] = counts[1] or 0
                result.append(fw)
            return result


@mcp.tool()
async def get_controls(framework: str) -> list[dict]:
    """Get all controls for a given framework ID (e.g. 'soc2', 'iso27001', 'hipaa', 'pci-dss', 'nist-csf')."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM controls WHERE framework_id=? ORDER BY category, id",
            (framework,)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


@mcp.tool()
async def get_control_detail(control_id: str) -> dict:
    """Get full detail for a single control by its ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT c.*, f.name as framework_name FROM controls c JOIN frameworks f ON c.framework_id=f.id WHERE c.id=?",
            (control_id,)
        ) as cur:
            row = await cur.fetchone()
            if not row:
                return {"error": f"Control '{control_id}' not found"}
            ctrl = dict(row)

        async with db.execute(
            "SELECT COUNT(*) FROM evidence WHERE control_id=?", (control_id,)
        ) as cur:
            ctrl["evidence_count"] = (await cur.fetchone())[0]

        async with db.execute(
            "SELECT * FROM audit_results WHERE control_id=? ORDER BY audited_at DESC LIMIT 1",
            (control_id,)
        ) as cur:
            last_audit = await cur.fetchone()
            ctrl["last_audit"] = dict(last_audit) if last_audit else None

        return ctrl


@mcp.tool()
async def search_controls(keyword: str) -> list[dict]:
    """Search controls by keyword across title, description, and guidance."""
    pattern = f"%{keyword}%"
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT c.*, f.name as framework_name FROM controls c
               JOIN frameworks f ON c.framework_id=f.id
               WHERE c.title LIKE ? OR c.description LIKE ? OR c.guidance LIKE ?
               ORDER BY c.framework_id, c.id""",
            (pattern, pattern, pattern)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


if __name__ == "__main__":
    mcp.run(transport="stdio")
