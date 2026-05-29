#!/usr/bin/env python3
"""
Compliance Auditor — Main Application
Starts all HTTP MCP servers and the FastAPI web UI in a single process.
"""

import asyncio
import multiprocessing
import os
import sys
import json
import aiosqlite
import uvicorn

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database.schema import init_db, DB_PATH

app = FastAPI(title="Compliance Auditor")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def db_fetchall(query: str, params: tuple = ()) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def db_fetchone(query: str, params: tuple = ()):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def db_execute(query: str, params: tuple = ()):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(query, params)
        await db.commit()


def score_to_grade(score: int) -> str:
    if score >= 90: return "A"
    if score >= 80: return "B"
    if score >= 70: return "C"
    if score >= 60: return "D"
    return "F"


def score_to_color(score: int) -> str:
    if score >= 75: return "success"
    if score >= 50: return "warning"
    return "danger"


# ─── Startup ──────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    await init_db()


# ─── Dashboard ────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    frameworks = await db_fetchall(
        """SELECT f.*,
           COUNT(c.id) as total_controls,
           SUM(CASE WHEN c.status='compliant' THEN 1 ELSE 0 END) as compliant_controls
           FROM frameworks f LEFT JOIN controls c ON f.id=c.framework_id
           GROUP BY f.id ORDER BY f.name"""
    )

    for fw in frameworks:
        total = fw["total_controls"] or 1
        fw["readiness_pct"] = round((fw["compliant_controls"] or 0) / total * 100)
        score_row = await db_fetchone(
            "SELECT AVG(score) as avg FROM audit_results WHERE framework_id=?", (fw["id"],)
        )
        fw["audit_score"] = round(score_row["avg"] or 0) if score_row else 0
        fw["grade"] = score_to_grade(fw["audit_score"])
        fw["score_color"] = score_to_color(fw["audit_score"])

    overdue = await db_fetchall(
        "SELECT COUNT(*) as cnt FROM deadlines WHERE status='pending' AND due_date < date('now')"
    )
    critical_gaps = await db_fetchall(
        "SELECT COUNT(*) as cnt FROM gaps WHERE severity='critical' AND status='open'"
    )
    high_risk_vendors = await db_fetchall(
        "SELECT COUNT(*) as cnt FROM vendors WHERE risk_level IN ('high','critical')"
    )
    total_evidence = await db_fetchall("SELECT COUNT(*) as cnt FROM evidence")

    stats = {
        "overdue": overdue[0]["cnt"],
        "critical_gaps": critical_gaps[0]["cnt"],
        "high_risk_vendors": high_risk_vendors[0]["cnt"],
        "total_evidence": total_evidence[0]["cnt"],
    }

    recent_audits = await db_fetchall(
        """SELECT ar.*, c.title as control_title, c.framework_id
           FROM audit_results ar JOIN controls c ON ar.control_id=c.id
           ORDER BY ar.audited_at DESC LIMIT 8"""
    )

    return templates.TemplateResponse(request, "dashboard.html", {
        "frameworks": frameworks,
        "stats": stats,
        "recent_audits": recent_audits,
        "active": "dashboard",
    })


# ─── Controls ─────────────────────────────────────────────────────────────────

@app.get("/controls", response_class=HTMLResponse)
async def controls_page(request: Request, framework: str = "soc2", search: str = ""):
    frameworks = await db_fetchall("SELECT * FROM frameworks ORDER BY name")

    if search:
        controls = await db_fetchall(
            """SELECT c.*, f.name as framework_name FROM controls c
               JOIN frameworks f ON c.framework_id=f.id
               WHERE c.title LIKE ? OR c.description LIKE ? OR c.id LIKE ?
               ORDER BY c.framework_id, c.id""",
            (f"%{search}%", f"%{search}%", f"%{search}%")
        )
    else:
        controls = await db_fetchall(
            "SELECT * FROM controls WHERE framework_id=? ORDER BY category, id",
            (framework,)
        )

    for ctrl in controls:
        ev = await db_fetchone(
            "SELECT COUNT(*) as cnt FROM evidence WHERE control_id=?", (ctrl["id"],)
        )
        ctrl["evidence_count"] = ev["cnt"] if ev else 0
        last = await db_fetchone(
            "SELECT status, score FROM audit_results WHERE control_id=? ORDER BY audited_at DESC LIMIT 1",
            (ctrl["id"],)
        )
        ctrl["last_audit_status"] = last["status"] if last else None
        ctrl["last_audit_score"] = last["score"] if last else None

    categories = list(dict.fromkeys(c["category"] for c in controls if c.get("category")))

    return templates.TemplateResponse(request, "controls.html", {
        "frameworks": frameworks,
        "controls": controls,
        "categories": categories,
        "selected_framework": framework,
        "search": search,
        "active": "controls",
    })


@app.post("/controls/{control_id}/status")
async def update_control_status(control_id: str, status: str = Form(...)):
    valid = {"not_started", "in_progress", "compliant"}
    if status not in valid:
        raise HTTPException(400, f"Invalid status. Use: {valid}")
    await db_execute("UPDATE controls SET status=? WHERE id=?", (status, control_id))
    return RedirectResponse("/controls", status_code=303)


# ─── Evidence ─────────────────────────────────────────────────────────────────

@app.get("/evidence", response_class=HTMLResponse)
async def evidence_page(request: Request, control_id: str = ""):
    controls = await db_fetchall(
        "SELECT id, title, framework_id FROM controls ORDER BY framework_id, id"
    )

    if control_id:
        items = await db_fetchall(
            """SELECT e.*, c.title as control_title FROM evidence e
               JOIN controls c ON e.control_id=c.id WHERE e.control_id=?
               ORDER BY e.uploaded_at DESC""",
            (control_id,)
        )
    else:
        items = await db_fetchall(
            """SELECT e.*, c.title as control_title FROM evidence e
               JOIN controls c ON e.control_id=c.id ORDER BY e.uploaded_at DESC LIMIT 50"""
        )

    return templates.TemplateResponse(request, "evidence.html", {
        "controls": controls,
        "items": items,
        "selected_control": control_id,
        "active": "evidence",
    })


@app.post("/evidence/upload")
async def upload_evidence(
    control_id: str = Form(...),
    filename: str = Form(...),
    description: str = Form(...),
    tags: str = Form(""),
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO evidence (control_id, filename, description, tags) VALUES (?,?,?,?)",
            (control_id, filename, description, tags)
        )
        await db.commit()
    return RedirectResponse(f"/evidence?control_id={control_id}", status_code=303)


@app.post("/evidence/{evidence_id}/delete")
async def delete_evidence(evidence_id: int):
    await db_execute("DELETE FROM evidence WHERE id=?", (evidence_id,))
    return RedirectResponse("/evidence", status_code=303)


# ─── Gaps ─────────────────────────────────────────────────────────────────────

@app.get("/gaps", response_class=HTMLResponse)
async def gaps_page(request: Request, framework: str = ""):
    frameworks = await db_fetchall("SELECT * FROM frameworks ORDER BY name")

    if framework:
        gaps = await db_fetchall(
            """SELECT g.*, c.title as control_title, c.category, f.name as framework_name
               FROM gaps g JOIN controls c ON g.control_id=c.id
               JOIN frameworks f ON g.framework_id=f.id
               WHERE g.framework_id=? ORDER BY g.severity, g.status, g.due_date""",
            (framework,)
        )
    else:
        gaps = await db_fetchall(
            """SELECT g.*, c.title as control_title, c.category, f.name as framework_name
               FROM gaps g JOIN controls c ON g.control_id=c.id
               JOIN frameworks f ON g.framework_id=f.id
               ORDER BY g.severity, g.status, g.due_date"""
        )

    summary = {"critical": 0, "high": 0, "medium": 0, "low": 0, "open": 0, "resolved": 0}
    for g in gaps:
        summary[g.get("severity", "low")] = summary.get(g.get("severity", "low"), 0) + 1
        summary[g.get("status", "open")] = summary.get(g.get("status", "open"), 0) + 1

    from datetime import date
    return templates.TemplateResponse(request, "gaps.html", {
        "frameworks": frameworks,
        "gaps": gaps,
        "summary": summary,
        "selected_framework": framework,
        "today": date.today().isoformat(),
        "active": "gaps",
    })


@app.post("/gaps/{gap_id}/resolve")
async def resolve_gap(gap_id: int):
    await db_execute(
        "UPDATE gaps SET status='resolved', resolved_at=datetime('now') WHERE id=?", (gap_id,)
    )
    return RedirectResponse("/gaps", status_code=303)


@app.post("/gaps/add")
async def add_gap(
    framework_id: str = Form(...),
    control_id: str = Form(...),
    title: str = Form(...),
    description: str = Form(""),
    severity: str = Form("medium"),
    owner: str = Form(""),
    due_date: str = Form(""),
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO gaps (framework_id, control_id, title, description, severity, owner, due_date) VALUES (?,?,?,?,?,?,?)",
            (framework_id, control_id, title, description, severity, owner, due_date or None)
        )
        await db.commit()
    return RedirectResponse("/gaps", status_code=303)


# ─── Vendors ──────────────────────────────────────────────────────────────────

@app.get("/vendors", response_class=HTMLResponse)
async def vendors_page(request: Request):
    vendors = await db_fetchall(
        """SELECT v.*,
                  (SELECT score FROM vendor_assessments WHERE vendor_id=v.id ORDER BY assessed_at DESC LIMIT 1) as latest_score,
                  (SELECT COUNT(*) FROM vendor_assessments WHERE vendor_id=v.id) as assessment_count
           FROM vendors v ORDER BY risk_level DESC, name"""
    )

    return templates.TemplateResponse(request, "vendors.html", {
        "vendors": vendors,
        "active": "vendors",
    })


@app.post("/vendors/add")
async def add_vendor(
    name: str = Form(...),
    service: str = Form(...),
    risk_level: str = Form("medium"),
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO vendors (name, service, risk_level) VALUES (?,?,?)",
            (name, service, risk_level)
        )
        await db.commit()
    return RedirectResponse("/vendors", status_code=303)


@app.post("/vendors/{vendor_id}/assess")
async def assess_vendor(vendor_id: int, score: int = Form(...), findings: str = Form("")):
    risk_level = "low" if score >= 80 else "medium" if score >= 60 else "high" if score >= 40 else "critical"
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO vendor_assessments (vendor_id, score, findings) VALUES (?,?,?)",
            (vendor_id, score, findings)
        )
        await db.execute(
            "UPDATE vendors SET risk_level=?, updated_at=datetime('now') WHERE id=?",
            (risk_level, vendor_id)
        )
        await db.commit()
    return RedirectResponse("/vendors", status_code=303)


# ─── Reports ──────────────────────────────────────────────────────────────────

@app.get("/reports", response_class=HTMLResponse)
async def reports_page(request: Request):
    frameworks = await db_fetchall("SELECT * FROM frameworks ORDER BY name")
    reports = await db_fetchall(
        "SELECT id, name, report_type, framework_id, generated_at FROM reports ORDER BY generated_at DESC LIMIT 30"
    )
    return templates.TemplateResponse(request, "reports.html", {
        "frameworks": frameworks,
        "reports": reports,
        "active": "reports",
    })


@app.post("/reports/generate")
async def generate_report(framework: str = Form(...), report_type: str = Form(...)):
    import json as _json
    from datetime import datetime as _dt

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        if report_type == "readiness":
            async with db.execute(
                "SELECT status, COUNT(*) as cnt FROM controls WHERE framework_id=? GROUP BY status", (framework,)
            ) as cur:
                rows = [dict(r) for r in await cur.fetchall()]
            total = sum(r["cnt"] for r in rows)
            compliant = sum(r["cnt"] for r in rows if r["status"] == "compliant")
            content = {"readiness_pct": round(compliant/total*100) if total else 0, "breakdown": {r["status"]: r["cnt"] for r in rows}}

        elif report_type == "gap_analysis":
            async with db.execute(
                "SELECT severity, COUNT(*) as cnt FROM gaps WHERE framework_id=? AND status='open' GROUP BY severity", (framework,)
            ) as cur:
                rows = [dict(r) for r in await cur.fetchall()]
            content = {"open_gaps": sum(r["cnt"] for r in rows), "by_severity": {r["severity"]: r["cnt"] for r in rows}}

        elif report_type == "executive_summary":
            async with db.execute("SELECT AVG(score) as avg FROM audit_results WHERE framework_id=?", (framework,)) as cur:
                score = round((await cur.fetchone())[0] or 0)
            content = {"score": score, "grade": score_to_grade(score)}

        else:
            content = {"message": "Report generated"}

        name = f"{report_type.replace('_',' ').title()} — {framework} — {_dt.now().strftime('%Y-%m-%d %H:%M')}"
        await db.execute(
            "INSERT INTO reports (name, report_type, framework_id, content) VALUES (?,?,?,?)",
            (name, report_type, framework, _json.dumps(content))
        )
        await db.commit()

    return RedirectResponse("/reports", status_code=303)


@app.get("/reports/{report_id}")
async def get_report(report_id: int):
    report = await db_fetchone("SELECT * FROM reports WHERE id=?", (report_id,))
    if not report:
        raise HTTPException(404)
    try:
        report["content"] = json.loads(report["content"])
    except Exception:
        pass
    return JSONResponse(report)


# ─── Schedule ─────────────────────────────────────────────────────────────────

@app.get("/schedule", response_class=HTMLResponse)
async def schedule_page(request: Request):
    frameworks = await db_fetchall("SELECT * FROM frameworks ORDER BY name")
    deadlines = await db_fetchall(
        """SELECT d.*, f.name as framework_name,
                  CAST(julianday(d.due_date) - julianday('now') AS INTEGER) as days_remaining
           FROM deadlines d LEFT JOIN frameworks f ON d.framework_id=f.id
           ORDER BY d.due_date ASC"""
    )
    for d in deadlines:
        d["is_overdue"] = d["status"] == "pending" and (d["days_remaining"] or 0) < 0

    return templates.TemplateResponse(request, "schedule.html", {
        "frameworks": frameworks,
        "deadlines": deadlines,
        "active": "schedule",
    })


@app.post("/schedule/add")
async def add_deadline(
    title: str = Form(...),
    framework_id: str = Form(...),
    due_date: str = Form(...),
    owner: str = Form(""),
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO deadlines (title, framework_id, due_date, owner) VALUES (?,?,?,?)",
            (title, framework_id, due_date, owner)
        )
        await db.commit()
    return RedirectResponse("/schedule", status_code=303)


@app.post("/schedule/{deadline_id}/complete")
async def complete_deadline(deadline_id: int):
    await db_execute(
        "UPDATE deadlines SET status='completed', completed_at=datetime('now') WHERE id=?", (deadline_id,)
    )
    return RedirectResponse("/schedule", status_code=303)


# ─── API endpoints ────────────────────────────────────────────────────────────

@app.get("/api/frameworks")
async def api_frameworks():
    return await db_fetchall("SELECT * FROM frameworks")


@app.get("/api/controls/{framework}")
async def api_controls(framework: str):
    return await db_fetchall(
        "SELECT * FROM controls WHERE framework_id=? ORDER BY category, id", (framework,)
    )


@app.get("/api/audit/score/{framework}")
async def api_audit_score(framework: str):
    rows = await db_fetchall(
        """SELECT ar.status, ar.score FROM audit_results ar
           INNER JOIN (
               SELECT control_id, MAX(audited_at) as max_at FROM audit_results WHERE framework_id=? GROUP BY control_id
           ) latest ON ar.control_id=latest.control_id AND ar.audited_at=latest.max_at
           WHERE ar.framework_id=?""",
        (framework, framework)
    )
    if not rows:
        return {"score": 0, "grade": "F"}
    avg = sum(r["score"] for r in rows) // len(rows)
    return {"score": avg, "grade": score_to_grade(avg), "controls_audited": len(rows)}


@app.post("/api/audit/run/{framework}")
async def api_run_audit(framework: str):
    controls = await db_fetchall(
        "SELECT id, status FROM controls WHERE framework_id=?", (framework,)
    )
    results = []
    STATUS_SCORES = {"compliant": 90, "in_progress": 55, "not_started": 10}
    async with aiosqlite.connect(DB_PATH) as db:
        for ctrl in controls:
            score = STATUS_SCORES.get(ctrl["status"], 10)
            status = "pass" if score >= 75 else ("partial" if score >= 40 else "fail")
            await db.execute(
                "INSERT INTO audit_results (control_id, framework_id, status, score, findings) VALUES (?,?,?,?,?)",
                (ctrl["id"], framework, status, score, f"Automated check — {ctrl['status']}")
            )
            results.append({"control_id": ctrl["id"], "status": status, "score": score})
        await db.commit()

    avg = sum(r["score"] for r in results) // len(results) if results else 0
    return {"framework": framework, "controls_checked": len(results), "average_score": avg, "grade": score_to_grade(avg)}


# ─── Server launchers ─────────────────────────────────────────────────────────

def run_evidence_server():
    from servers.evidence_server import mcp as evidence_mcp
    app_ = evidence_mcp.http_app()
    uvicorn.run(app_, host="0.0.0.0", port=5001, log_level="warning")


def run_audit_server():
    from servers.audit_server import mcp as audit_mcp
    app_ = audit_mcp.http_app()
    uvicorn.run(app_, host="0.0.0.0", port=5002, log_level="warning")


def run_vendor_server():
    from servers.vendor_server import mcp as vendor_mcp
    app_ = vendor_mcp.http_app()
    uvicorn.run(app_, host="0.0.0.0", port=5003, log_level="warning")


def run_gap_server():
    from servers.gap_analysis_server import mcp as gap_mcp
    app_ = gap_mcp.http_app()
    uvicorn.run(app_, host="0.0.0.0", port=5004, log_level="warning")


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  Compliance Auditor")
    print("=" * 60)
    print("  Web UI       → http://localhost:8000")
    print("  evidence-server (HTTP MCP) → http://localhost:5001/mcp")
    print("  audit-server   (HTTP MCP) → http://localhost:5002/mcp")
    print("  vendor-server  (HTTP MCP) → http://localhost:5003/mcp")
    print("  gap-server     (HTTP MCP) → http://localhost:5004/mcp")
    print("=" * 60)

    procs = []
    for target in [run_evidence_server, run_audit_server, run_vendor_server, run_gap_server]:
        p = multiprocessing.Process(target=target, daemon=True)
        p.start()
        procs.append(p)

    try:
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
    finally:
        for p in procs:
            p.terminate()
