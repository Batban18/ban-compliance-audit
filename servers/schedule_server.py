#!/usr/bin/env python3
"""Schedule Server — stdio MCP server for deadline tracking and reminders."""

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastmcp import FastMCP
import aiosqlite

DB_PATH = os.environ.get("DB_PATH", "compliance.db")
mcp = FastMCP("schedule-server")


@mcp.tool()
async def add_deadline(title: str, framework: str, due_date: str, owner: str = "") -> dict:
    """Add a compliance deadline. due_date format: YYYY-MM-DD."""
    try:
        datetime.strptime(due_date, "%Y-%m-%d")
    except ValueError:
        return {"error": "due_date must be YYYY-MM-DD format"}

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id FROM frameworks WHERE id=?", (framework,)) as cur:
            if not await cur.fetchone():
                return {"error": f"Framework '{framework}' not found"}

        await db.execute(
            "INSERT INTO deadlines (title, framework_id, due_date, owner) VALUES (?,?,?,?)",
            (title, framework, due_date, owner)
        )
        await db.commit()
        async with db.execute("SELECT last_insert_rowid()") as cur:
            did = (await cur.fetchone())[0]
        return {"success": True, "deadline_id": did, "title": title, "due_date": due_date, "owner": owner}


@mcp.tool()
async def list_deadlines() -> list[dict]:
    """List all deadlines with their status, sorted by due date."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT d.*, f.name as framework_name,
                      CASE WHEN d.status='pending' AND d.due_date < date('now') THEN 1 ELSE 0 END as is_overdue,
                      CAST(julianday(d.due_date) - julianday('now') AS INTEGER) as days_remaining
               FROM deadlines d LEFT JOIN frameworks f ON d.framework_id=f.id
               ORDER BY d.due_date ASC"""
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


@mcp.tool()
async def get_overdue_items() -> list[dict]:
    """Get all overdue compliance deadlines."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT d.*, f.name as framework_name,
                      CAST(julianday('now') - julianday(d.due_date) AS INTEGER) as days_overdue
               FROM deadlines d LEFT JOIN frameworks f ON d.framework_id=f.id
               WHERE d.status='pending' AND d.due_date < date('now')
               ORDER BY d.due_date ASC"""
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


@mcp.tool()
async def get_upcoming_deadlines(days: int = 30) -> list[dict]:
    """Get deadlines due within the next N days (default: 30)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT d.*, f.name as framework_name,
                      CAST(julianday(d.due_date) - julianday('now') AS INTEGER) as days_remaining
               FROM deadlines d LEFT JOIN frameworks f ON d.framework_id=f.id
               WHERE d.status='pending'
                 AND d.due_date >= date('now')
                 AND d.due_date <= date('now', ? || ' days')
               ORDER BY d.due_date ASC""",
            (str(days),)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


@mcp.tool()
async def mark_complete(deadline_id: int) -> dict:
    """Mark a deadline as completed."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, status FROM deadlines WHERE id=?", (deadline_id,)) as cur:
            row = await cur.fetchone()
            if not row:
                return {"error": f"Deadline #{deadline_id} not found"}
            if row[1] == "completed":
                return {"message": f"Deadline #{deadline_id} already completed"}

        await db.execute(
            "UPDATE deadlines SET status='completed', completed_at=datetime('now') WHERE id=?",
            (deadline_id,)
        )
        await db.commit()
        return {"success": True, "deadline_id": deadline_id, "status": "completed"}


@mcp.tool()
async def send_reminder(deadline_id: int) -> dict:
    """Send a reminder for a deadline (marks reminder_sent flag and logs action)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT d.*, f.name as framework_name FROM deadlines d LEFT JOIN frameworks f ON d.framework_id=f.id WHERE d.id=?",
            (deadline_id,)
        ) as cur:
            row = await cur.fetchone()
            if not row:
                return {"error": f"Deadline #{deadline_id} not found"}
            dl = dict(row)

        await db.execute(
            "UPDATE deadlines SET reminder_sent=1 WHERE id=?", (deadline_id,)
        )
        await db.commit()

    alert_email = os.environ.get("ALERT_EMAIL", "compliance@company.com")
    return {
        "success": True,
        "deadline_id": deadline_id,
        "title": dl["title"],
        "due_date": dl["due_date"],
        "owner": dl["owner"],
        "reminder_sent_to": alert_email,
        "message": f"Reminder queued for '{dl['title']}' due {dl['due_date']} — owner: {dl['owner'] or 'unassigned'}",
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
