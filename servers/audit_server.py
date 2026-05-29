#!/usr/bin/env python3
"""Audit Server — HTTP MCP server on :5002 for automated audit checks and scoring."""

import os
import sys
import random
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastmcp import FastMCP
import aiosqlite

DB_PATH = os.environ.get("DB_PATH", "compliance.db")
mcp = FastMCP("audit-server")

STATUS_SCORES = {"compliant": 90, "in_progress": 55, "not_started": 10}

FINDINGS_MAP = {
    "compliant": [
        "Control is fully implemented and operating effectively.",
        "Evidence reviewed; control meets all requirements.",
        "Testing passed. No exceptions noted.",
    ],
    "in_progress": [
        "Control partially implemented; remediation underway.",
        "Documentation exists but operational effectiveness not yet demonstrated.",
        "Implementation in progress; estimated completion next quarter.",
    ],
    "not_started": [
        "Control not yet implemented. Immediate action required.",
        "No evidence of control implementation found.",
        "Gap identified; owner must be assigned and remediation plan created.",
    ],
}


@mcp.tool()
async def run_audit_check(control_id: str) -> dict:
    """Run an automated audit check for a single control."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT c.*, f.id as framework_id FROM controls c JOIN frameworks f ON c.framework_id=f.id WHERE c.id=?",
            (control_id,)
        ) as cur:
            ctrl = await cur.fetchone()
            if not ctrl:
                return {"error": f"Control '{control_id}' not found"}
            ctrl = dict(ctrl)

        async with db.execute(
            "SELECT COUNT(*) FROM evidence WHERE control_id=?", (control_id,)
        ) as cur:
            evidence_count = (await cur.fetchone())[0]

        status = ctrl["status"]
        base_score = STATUS_SCORES.get(status, 0)
        evidence_bonus = min(evidence_count * 5, 20)
        score = min(base_score + evidence_bonus, 100)

        findings = random.choice(FINDINGS_MAP.get(status, FINDINGS_MAP["not_started"]))
        audit_status = "pass" if score >= 75 else ("partial" if score >= 40 else "fail")

        await db.execute(
            "INSERT INTO audit_results (control_id, framework_id, status, score, findings) VALUES (?,?,?,?,?)",
            (control_id, ctrl["framework_id"], audit_status, score, findings)
        )
        await db.commit()

        return {
            "control_id": control_id,
            "control_title": ctrl["title"],
            "status": audit_status,
            "score": score,
            "evidence_items": evidence_count,
            "findings": findings,
            "audited_at": datetime.now().isoformat(),
        }


@mcp.tool()
async def run_full_audit(framework: str) -> dict:
    """Run audit checks across all controls in a framework."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id FROM controls WHERE framework_id=?", (framework,)
        ) as cur:
            controls = [r["id"] for r in await cur.fetchall()]

    if not controls:
        return {"error": f"Framework '{framework}' not found or has no controls"}

    results = []
    for cid in controls:
        result = await run_audit_check(cid)
        results.append(result)

    passed = sum(1 for r in results if r.get("status") == "pass")
    partial = sum(1 for r in results if r.get("status") == "partial")
    failed = sum(1 for r in results if r.get("status") == "fail")
    avg_score = sum(r.get("score", 0) for r in results) // len(results) if results else 0

    return {
        "framework": framework,
        "total_controls": len(controls),
        "passed": passed,
        "partial": partial,
        "failed": failed,
        "average_score": avg_score,
        "overall_status": "pass" if avg_score >= 75 else ("partial" if avg_score >= 40 else "fail"),
        "results": results,
        "audited_at": datetime.now().isoformat(),
    }


@mcp.tool()
async def get_audit_score(framework: str) -> dict:
    """Get the current compliance score for a framework based on latest audit results."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT ar.control_id, ar.status, ar.score, ar.audited_at
               FROM audit_results ar
               INNER JOIN (
                   SELECT control_id, MAX(audited_at) as max_at
                   FROM audit_results WHERE framework_id=?
                   GROUP BY control_id
               ) latest ON ar.control_id=latest.control_id AND ar.audited_at=latest.max_at
               WHERE ar.framework_id=?""",
            (framework, framework)
        ) as cur:
            rows = [dict(r) for r in await cur.fetchall()]

        async with db.execute(
            "SELECT COUNT(*) FROM controls WHERE framework_id=?", (framework,)
        ) as cur:
            total = (await cur.fetchone())[0]

    if not rows:
        return {"framework": framework, "score": 0, "audited_controls": 0, "total_controls": total, "message": "No audit data"}

    avg = sum(r["score"] for r in rows) // len(rows)
    return {
        "framework": framework,
        "score": avg,
        "audited_controls": len(rows),
        "total_controls": total,
        "pass": sum(1 for r in rows if r["status"] == "pass"),
        "partial": sum(1 for r in rows if r["status"] == "partial"),
        "fail": sum(1 for r in rows if r["status"] == "fail"),
        "grade": "A" if avg >= 90 else "B" if avg >= 80 else "C" if avg >= 70 else "D" if avg >= 60 else "F",
    }


@mcp.tool()
async def get_audit_history(control_id: str) -> list[dict]:
    """Get the full audit history for a control."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM audit_results WHERE control_id=? ORDER BY audited_at DESC LIMIT 20",
            (control_id,)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


@mcp.tool()
async def get_failing_controls(framework: str) -> list[dict]:
    """Get all controls currently failing audit checks in a framework."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT c.id, c.title, c.category, c.status as control_status,
                      ar.status as audit_status, ar.score, ar.findings, ar.audited_at
               FROM controls c
               LEFT JOIN audit_results ar ON c.id=ar.control_id
               AND ar.audited_at=(SELECT MAX(audited_at) FROM audit_results WHERE control_id=c.id)
               WHERE c.framework_id=? AND (ar.status='fail' OR ar.status IS NULL)
               ORDER BY ar.score ASC""",
            (framework,)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


if __name__ == "__main__":
    import uvicorn
    app = mcp.http_app()
    uvicorn.run(app, host="0.0.0.0", port=5002, log_level="warning")
