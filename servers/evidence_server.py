#!/usr/bin/env python3
"""Evidence Server — HTTP MCP server on :5001 for evidence collection and management."""

import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastmcp import FastMCP
import aiosqlite

DB_PATH = os.environ.get("DB_PATH", "compliance.db")
mcp = FastMCP("evidence-server")


@mcp.tool()
async def upload_evidence(control_id: str, filename: str, description: str, tags: str = "") -> dict:
    """Upload/register evidence for a control. Tags are comma-separated."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id FROM controls WHERE id=?", (control_id,)
        ) as cur:
            if not await cur.fetchone():
                return {"error": f"Control '{control_id}' not found"}

        await db.execute(
            "INSERT INTO evidence (control_id, filename, description, tags) VALUES (?,?,?,?)",
            (control_id, filename, description, tags)
        )
        await db.commit()

        async with db.execute("SELECT last_insert_rowid()") as cur:
            eid = (await cur.fetchone())[0]

        return {"success": True, "evidence_id": eid, "control_id": control_id, "filename": filename}


@mcp.tool()
async def list_evidence(control_id: str) -> list[dict]:
    """List all evidence items for a given control."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM evidence WHERE control_id=? ORDER BY uploaded_at DESC",
            (control_id,)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


@mcp.tool()
async def get_evidence(evidence_id: int) -> dict:
    """Get a single evidence item by ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT e.*, c.title as control_title FROM evidence e JOIN controls c ON e.control_id=c.id WHERE e.id=?",
            (evidence_id,)
        ) as cur:
            row = await cur.fetchone()
            if not row:
                return {"error": f"Evidence #{evidence_id} not found"}
            return dict(row)


@mcp.tool()
async def delete_evidence(evidence_id: int) -> dict:
    """Delete an evidence item by ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id FROM evidence WHERE id=?", (evidence_id,)) as cur:
            if not await cur.fetchone():
                return {"error": f"Evidence #{evidence_id} not found"}
        await db.execute("DELETE FROM evidence WHERE id=?", (evidence_id,))
        await db.commit()
        return {"success": True, "deleted_id": evidence_id}


@mcp.tool()
async def tag_evidence(evidence_id: int, tags: str) -> dict:
    """Update the tags on an evidence item. Provide comma-separated tags."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, tags FROM evidence WHERE id=?", (evidence_id,)) as cur:
            row = await cur.fetchone()
            if not row:
                return {"error": f"Evidence #{evidence_id} not found"}
            existing = set(t.strip() for t in (row[1] or "").split(",") if t.strip())
            new_tags = set(t.strip() for t in tags.split(",") if t.strip())
            merged = ",".join(sorted(existing | new_tags))

        await db.execute("UPDATE evidence SET tags=? WHERE id=?", (merged, evidence_id))
        await db.commit()
        return {"success": True, "evidence_id": evidence_id, "tags": merged}


if __name__ == "__main__":
    import uvicorn
    app = mcp.http_app()
    uvicorn.run(app, host="0.0.0.0", port=5001, log_level="warning")
