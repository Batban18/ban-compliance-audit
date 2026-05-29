#!/usr/bin/env python3
"""Policy Server — stdio MCP server for policy lifecycle management."""

import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastmcp import FastMCP
import aiosqlite

DB_PATH = os.environ.get("DB_PATH", "compliance.db")
mcp = FastMCP("policy-server")


@mcp.tool()
async def create_policy(name: str, content: str, framework: str, control_ids: str = "") -> dict:
    """Create a new compliance policy. control_ids is comma-separated."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO policies (name, content, framework_id, control_ids) VALUES (?,?,?,?)",
            (name, content, framework, control_ids)
        )
        await db.commit()
        async with db.execute("SELECT last_insert_rowid()") as cur:
            pid = (await cur.fetchone())[0]

        await db.execute(
            "INSERT INTO policy_versions (policy_id, version, content, changed_by) VALUES (?,1,?,?)",
            (pid, content, "system")
        )
        await db.commit()
        return {"success": True, "policy_id": pid, "name": name, "version": 1, "status": "draft"}


@mcp.tool()
async def get_policy(policy_id: int) -> dict:
    """Get a policy by ID including its current content and metadata."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM policies WHERE id=?", (policy_id,)) as cur:
            row = await cur.fetchone()
            if not row:
                return {"error": f"Policy #{policy_id} not found"}
            return dict(row)


@mcp.tool()
async def list_policies(framework: str = "") -> list[dict]:
    """List all policies, optionally filtered by framework."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if framework:
            async with db.execute(
                "SELECT * FROM policies WHERE framework_id=? ORDER BY name", (framework,)
            ) as cur:
                rows = await cur.fetchall()
        else:
            async with db.execute("SELECT * FROM policies ORDER BY framework_id, name") as cur:
                rows = await cur.fetchall()
        return [dict(r) for r in rows]


@mcp.tool()
async def update_policy(policy_id: int, content: str, changed_by: str = "user") -> dict:
    """Update policy content and increment version."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, version FROM policies WHERE id=?", (policy_id,)
        ) as cur:
            row = await cur.fetchone()
            if not row:
                return {"error": f"Policy #{policy_id} not found"}
            new_version = row[1] + 1

        await db.execute(
            "UPDATE policies SET content=?, version=?, status='draft', updated_at=datetime('now') WHERE id=?",
            (content, new_version, policy_id)
        )
        await db.execute(
            "INSERT INTO policy_versions (policy_id, version, content, changed_by) VALUES (?,?,?,?)",
            (policy_id, new_version, content, changed_by)
        )
        await db.commit()
        return {"success": True, "policy_id": policy_id, "new_version": new_version}


@mcp.tool()
async def approve_policy(policy_id: int, approver: str) -> dict:
    """Approve a policy, moving it from draft to approved status."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, status FROM policies WHERE id=?", (policy_id,)
        ) as cur:
            row = await cur.fetchone()
            if not row:
                return {"error": f"Policy #{policy_id} not found"}
            if row[1] == "approved":
                return {"error": "Policy is already approved"}

        await db.execute(
            "UPDATE policies SET status='approved', approver=?, approved_at=datetime('now') WHERE id=?",
            (approver, policy_id)
        )
        await db.commit()
        return {"success": True, "policy_id": policy_id, "approver": approver, "status": "approved"}


@mcp.tool()
async def get_policy_version_history(policy_id: int) -> list[dict]:
    """Get the full version history of a policy."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM policy_versions WHERE policy_id=? ORDER BY version DESC",
            (policy_id,)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


if __name__ == "__main__":
    mcp.run(transport="stdio")
