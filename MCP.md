# MCP Server Configuration

This project exposes 8 MCP servers for compliance management.
Copy the config below into your Batban Desktop configuration.

```json
{
  "mcpServers": {
    "framework-server": {
      "command": "python",
      "args": ["servers/framework_server.py"],
      "trust": false
    },
    "evidence-server": {
      "httpUrl": "http://localhost:5001/mcp",
      "timeout": 30000,
      "trust": false
    },
    "audit-server": {
      "httpUrl": "http://localhost:5002/mcp",
      "timeout": 30000,
      "trust": false
    },
    "policy-server": {
      "command": "python",
      "args": ["servers/policy_server.py"],
      "trust": false
    },
    "vendor-server": {
      "httpUrl": "http://localhost:5003/mcp",
      "timeout": 30000,
      "trust": false
    },
    "report-server": {
      "command": "python",
      "args": ["servers/report_server.py"],
      "trust": false
    },
    "gap-analysis-server": {
      "httpUrl": "http://localhost:5004/mcp",
      "timeout": 30000,
      "trust": false
    },
    "schedule-server": {
      "command": "python",
      "args": ["servers/schedule_server.py"],
      "trust": false
    }
  }
}
```

## Server Details

| Server | Transport | Port | Purpose |
|--------|-----------|------|---------|
| framework-server | stdio | — | Compliance framework & control catalog |
| evidence-server | HTTP | 5001 | Evidence collection & management |
| audit-server | HTTP | 5002 | Automated audit checks & scoring |
| policy-server | stdio | — | Policy lifecycle management |
| vendor-server | HTTP | 5003 | Third-party vendor risk tracking |
| report-server | stdio | — | Report generation & export |
| gap-analysis-server | HTTP | 5004 | Gap identification & remediation |
| schedule-server | stdio | — | Deadline tracking & reminders |

## Quick Start

```bash
pip install fastapi fastmcp uvicorn jinja2 aiosqlite
python app.py
```

Open http://localhost:8000 in your browser.
