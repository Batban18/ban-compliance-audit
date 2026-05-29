#!/usr/bin/env python3
"""Report Server — stdio MCP server for compliance report generation."""

import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastmcp import FastMCP
import aiosqlite

DB_PATH = os.environ.get("DB_PATH", "compliance.db")
REPORT_DIR = os.environ.get("REPORT_OUTPUT_DIR", "./reports")
mcp = FastMCP("report-server")


async def _framework_summary(db, framework_id: str) -> dict:
    db.row_factory = aiosqlite.Row
    async with db.execute("SELECT * FROM frameworks WHERE id=?", (framework_id,)) as cur:
        fw = dict(await cur.fetchone() or {})

    async with db.execute(
        "SELECT status, COUNT(*) as cnt FROM controls WHERE framework_id=? GROUP BY status",
        (framework_id,)
    ) as cur:
        status_counts = {r["status"]: r["cnt"] for r in await cur.fetchall()}

    async with db.execute(
        "SELECT AVG(score) as avg FROM audit_results WHERE framework_id=?", (framework_id,)
    ) as cur:
        row = await cur.fetchone()
        avg_score = round(row[0] or 0)

    return {**fw, "status_counts": status_counts, "avg_audit_score": avg_score}


@mcp.tool()
async def generate_readiness_report(framework: str) -> dict:
    """Generate a compliance readiness report for a framework."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        summary = await _framework_summary(db, framework)

        async with db.execute(
            "SELECT * FROM controls WHERE framework_id=? ORDER BY status, id", (framework,)
        ) as cur:
            controls = [dict(r) for r in await cur.fetchall()]

        async with db.execute(
            "SELECT * FROM gaps WHERE framework_id=? AND status='open' ORDER BY severity", (framework,)
        ) as cur:
            gaps = [dict(r) for r in await cur.fetchall()]

    total = len(controls)
    compliant = sum(1 for c in controls if c["status"] == "compliant")
    readiness_pct = round((compliant / total * 100) if total else 0)

    content = {
        "report_type": "readiness",
        "framework": summary.get("name", framework),
        "generated_at": datetime.now().isoformat(),
        "readiness_percentage": readiness_pct,
        "controls": {"total": total, "compliant": compliant, "breakdown": {}},
        "open_gaps": len(gaps),
        "critical_gaps": sum(1 for g in gaps if g["severity"] == "critical"),
        "controls_detail": controls,
    }

    for c in controls:
        s = c["status"]
        content["controls"]["breakdown"][s] = content["controls"]["breakdown"].get(s, 0) + 1

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO reports (name, report_type, framework_id, content) VALUES (?,?,?,?)",
            (f"Readiness Report — {framework} — {datetime.now().strftime('%Y-%m-%d')}", "readiness", framework, json.dumps(content))
        )
        await db.commit()

    return content


@mcp.tool()
async def generate_gap_report(framework: str) -> dict:
    """Generate a gap analysis report showing all open compliance gaps."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        summary = await _framework_summary(db, framework)

        async with db.execute(
            "SELECT g.*, c.title as control_title, c.category FROM gaps g JOIN controls c ON g.control_id=c.id WHERE g.framework_id=? ORDER BY g.severity, g.due_date",
            (framework,)
        ) as cur:
            gaps = [dict(r) for r in await cur.fetchall()]

    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    gaps.sort(key=lambda g: severity_order.get(g.get("severity", "low"), 3))

    content = {
        "report_type": "gap_analysis",
        "framework": summary.get("name", framework),
        "generated_at": datetime.now().isoformat(),
        "total_gaps": len(gaps),
        "by_severity": {},
        "gaps": gaps,
    }
    for g in gaps:
        sev = g.get("severity", "unknown")
        content["by_severity"][sev] = content["by_severity"].get(sev, 0) + 1

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO reports (name, report_type, framework_id, content) VALUES (?,?,?,?)",
            (f"Gap Report — {framework} — {datetime.now().strftime('%Y-%m-%d')}", "gap_analysis", framework, json.dumps(content))
        )
        await db.commit()

    return content


@mcp.tool()
async def generate_evidence_report(framework: str) -> dict:
    """Generate an evidence coverage report for all controls in a framework."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT c.id, c.title, c.status, COUNT(e.id) as evidence_count
               FROM controls c LEFT JOIN evidence e ON c.id=e.control_id
               WHERE c.framework_id=? GROUP BY c.id ORDER BY evidence_count ASC""",
            (framework,)
        ) as cur:
            rows = [dict(r) for r in await cur.fetchall()]

    no_evidence = [r for r in rows if r["evidence_count"] == 0]
    content = {
        "report_type": "evidence_coverage",
        "framework": framework,
        "generated_at": datetime.now().isoformat(),
        "total_controls": len(rows),
        "controls_with_evidence": sum(1 for r in rows if r["evidence_count"] > 0),
        "controls_without_evidence": len(no_evidence),
        "total_evidence_items": sum(r["evidence_count"] for r in rows),
        "controls": rows,
        "gaps": no_evidence,
    }

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO reports (name, report_type, framework_id, content) VALUES (?,?,?,?)",
            (f"Evidence Report — {framework} — {datetime.now().strftime('%Y-%m-%d')}", "evidence_coverage", framework, json.dumps(content))
        )
        await db.commit()

    return content


@mcp.tool()
async def generate_executive_summary(framework: str) -> dict:
    """Generate a concise executive summary for leadership reporting."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        summary = await _framework_summary(db, framework)

        async with db.execute(
            "SELECT COUNT(*) FROM gaps WHERE framework_id=? AND status='open' AND severity='critical'",
            (framework,)
        ) as cur:
            critical_gaps = (await cur.fetchone())[0]

        async with db.execute(
            "SELECT COUNT(*) FROM deadlines WHERE framework_id=? AND status='pending' AND due_date < date('now')",
            (framework,)
        ) as cur:
            overdue = (await cur.fetchone())[0]

        async with db.execute(
            "SELECT COUNT(*) FROM vendors WHERE risk_level IN ('high','critical')",
        ) as cur:
            high_risk_vendors = (await cur.fetchone())[0]

    total = sum(summary["status_counts"].values())
    compliant = summary["status_counts"].get("compliant", 0)
    score = summary["avg_audit_score"]
    grade = "A" if score >= 90 else "B" if score >= 80 else "C" if score >= 70 else "D" if score >= 60 else "F"

    content = {
        "report_type": "executive_summary",
        "framework": summary.get("name", framework),
        "generated_at": datetime.now().isoformat(),
        "overall_score": score,
        "grade": grade,
        "readiness": round(compliant / total * 100) if total else 0,
        "critical_gaps": critical_gaps,
        "overdue_items": overdue,
        "high_risk_vendors": high_risk_vendors,
        "recommendation": (
            "Immediate action required on critical gaps." if critical_gaps > 0
            else "On track. Continue monitoring and evidence collection."
        ),
        "status_breakdown": summary["status_counts"],
    }

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO reports (name, report_type, framework_id, content) VALUES (?,?,?,?)",
            (f"Executive Summary — {framework} — {datetime.now().strftime('%Y-%m-%d')}", "executive_summary", framework, json.dumps(content))
        )
        await db.commit()

    return content


@mcp.tool()
async def list_generated_reports() -> list[dict]:
    """List all previously generated reports."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, name, report_type, framework_id, generated_at FROM reports ORDER BY generated_at DESC"
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


if __name__ == "__main__":
    mcp.run(transport="stdio")
