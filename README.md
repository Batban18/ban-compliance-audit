# Compliance Auditor

A local compliance management tool with 8 MCP servers covering the full audit lifecycle.

## Quick Start

```bash
pip install fastapi fastmcp uvicorn jinja2 aiosqlite
python app.py
```

Open http://localhost:8000

## MCP Server Setup

Add three core servers to get started:

```json
{
  "mcpServers": {
    "framework-server": {
      "command": "python",
      "args": ["servers/framework_server.py"],
      "trust": false
    },
    "audit-server": {
      "httpUrl": "http://localhost:5002/mcp",
      "timeout": 30000,
      "trust": false
    },
    "report-server": {
      "command": "python",
      "args": ["servers/report_server.py"],
      "trust": false
    }
  }
}
```

For all 8 servers see [MCP.md](MCP.md) or [config/mcp-servers.json](config/mcp-servers.json).

## Features

- **Dashboard** — compliance score, overdue items, critical gaps at a glance
- **Controls** — browse SOC 2, ISO 27001, HIPAA, PCI-DSS, NIST CSF control libraries
- **Evidence** — upload and tag evidence artifacts per control
- **Audit** — run automated checks, view pass/fail history, get scoring
- **Gap Analysis** — identify and track remediation of compliance gaps
- **Vendors** — third-party risk assessment and tracking
- **Policies** — create, version, and approve compliance policies
- **Schedule** — deadline tracking with overdue alerts

## Architecture

```
app.py                     FastAPI web app + MCP proxy routes
servers/
  framework_server.py      stdio — control catalog (SOC2, ISO27001, HIPAA, PCI-DSS, NIST)
  evidence_server.py       HTTP :5001 — evidence upload & retrieval
  audit_server.py          HTTP :5002 — automated audit checks & scoring
  policy_server.py         stdio — policy CRUD + approval workflow
  vendor_server.py         HTTP :5003 — vendor risk management
  report_server.py         stdio — report generation
  gap_analysis_server.py   HTTP :5004 — gap identification & remediation
  schedule_server.py       stdio — deadline & reminder management
database/
  schema.py                SQLite schema + seed data
```

## Database

SQLite (`compliance.db`) is auto-created on first run with seed data for all frameworks.
