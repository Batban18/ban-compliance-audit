#!/usr/bin/env python3
"""Vendor Server — HTTP MCP server on :5003 for vendor risk management."""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastmcp import FastMCP
import aiosqlite

DB_PATH = os.environ.get("DB_PATH", "compliance.db")
mcp = FastMCP("vendor-server")

RISK_LEVELS = {"low", "medium", "high", "critical"}


@mcp.tool()
async def add_vendor(name: str, service: str, risk_level: str = "medium") -> dict:
    """Add a new vendor. risk_level: low | medium | high | critical."""
    if risk_level not in RISK_LEVELS:
        return {"error": f"Invalid risk_level. Use: {', '.join(RISK_LEVELS)}"}

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO vendors (name, service, risk_level) VALUES (?,?,?)",
            (name, service, risk_level)
        )
        await db.commit()
        async with db.execute("SELECT last_insert_rowid()") as cur:
            vid = (await cur.fetchone())[0]
        return {"success": True, "vendor_id": vid, "name": name, "risk_level": risk_level}


@mcp.tool()
async def list_vendors() -> list[dict]:
    """List all vendors with latest assessment score."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT v.*,
                      (SELECT score FROM vendor_assessments WHERE vendor_id=v.id ORDER BY assessed_at DESC LIMIT 1) as latest_score,
                      (SELECT COUNT(*) FROM vendor_assessments WHERE vendor_id=v.id) as assessment_count
               FROM vendors v ORDER BY risk_level DESC, name"""
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


@mcp.tool()
async def get_vendor(vendor_id: int) -> dict:
    """Get full vendor details including assessment history."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM vendors WHERE id=?", (vendor_id,)) as cur:
            row = await cur.fetchone()
            if not row:
                return {"error": f"Vendor #{vendor_id} not found"}
            vendor = dict(row)

        async with db.execute(
            "SELECT * FROM vendor_assessments WHERE vendor_id=? ORDER BY assessed_at DESC",
            (vendor_id,)
        ) as cur:
            vendor["assessments"] = [dict(r) for r in await cur.fetchall()]

        return vendor


@mcp.tool()
async def update_vendor_risk(vendor_id: int, risk_level: str, notes: str = "") -> dict:
    """Update the risk level of a vendor."""
    if risk_level not in RISK_LEVELS:
        return {"error": f"Invalid risk_level. Use: {', '.join(RISK_LEVELS)}"}

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id FROM vendors WHERE id=?", (vendor_id,)) as cur:
            if not await cur.fetchone():
                return {"error": f"Vendor #{vendor_id} not found"}

        await db.execute(
            "UPDATE vendors SET risk_level=?, notes=?, updated_at=datetime('now') WHERE id=?",
            (risk_level, notes, vendor_id)
        )
        await db.commit()
        return {"success": True, "vendor_id": vendor_id, "risk_level": risk_level}


@mcp.tool()
async def add_vendor_assessment(vendor_id: int, score: int, findings: str = "") -> dict:
    """Add a vendor assessment with a score (0-100) and findings."""
    if not 0 <= score <= 100:
        return {"error": "Score must be 0-100"}

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id FROM vendors WHERE id=?", (vendor_id,)) as cur:
            if not await cur.fetchone():
                return {"error": f"Vendor #{vendor_id} not found"}

        await db.execute(
            "INSERT INTO vendor_assessments (vendor_id, score, findings) VALUES (?,?,?)",
            (vendor_id, score, findings)
        )
        risk_level = "low" if score >= 80 else "medium" if score >= 60 else "high" if score >= 40 else "critical"
        await db.execute(
            "UPDATE vendors SET risk_level=?, updated_at=datetime('now') WHERE id=?",
            (risk_level, vendor_id)
        )
        await db.commit()
        return {"success": True, "vendor_id": vendor_id, "score": score, "derived_risk": risk_level}


@mcp.tool()
async def list_high_risk_vendors() -> list[dict]:
    """List all vendors with high or critical risk level."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT v.*,
                      (SELECT score FROM vendor_assessments WHERE vendor_id=v.id ORDER BY assessed_at DESC LIMIT 1) as latest_score
               FROM vendors v WHERE v.risk_level IN ('high','critical') ORDER BY risk_level DESC, name"""
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


@mcp.tool()
async def get_vendors_missing_assessment() -> list[dict]:
    """Get vendors that have never been assessed."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT v.* FROM vendors v
               WHERE NOT EXISTS (SELECT 1 FROM vendor_assessments va WHERE va.vendor_id=v.id)
               ORDER BY risk_level DESC, name"""
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


if __name__ == "__main__":
    import uvicorn
    app = mcp.http_app()
    uvicorn.run(app, host="0.0.0.0", port=5003, log_level="warning")
