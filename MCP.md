# MCP Server Configuration

This project exposes 8 MCP servers for compliance management.
Copy the config below into your Batban Desktop configuration.

```json
{
  "mcpServers": {
    "framework-server": {
      "command": "python",
      "args": ["servers/framework_server.py", "--mode", "production", "--log-level", "INFO"],
      "description": "Manages SOC2, ISO27001, HIPAA, GDPR compliance frameworks",
      "version": "1.2.0",
      "protocol": "2024-11-05",
      "trust": false,
      "env": {
        "FRAMEWORK_DB": "sqlite:///compliance.db",
        "FRAMEWORK_LOG_LEVEL": "INFO",
        "FRAMEWORK_CACHE_TTL": "3600"
      },
      "tools": ["list_frameworks", "get_controls", "get_control_detail", "search_controls"]
    },
    "evidence-server": {
      "httpUrl": "http://localhost:5001/mcp",
      "timeout": 60000,
      "trust": false,
      "description": "Collects and manages audit evidence for compliance controls",
      "version": "1.1.0",
      "protocol": "2024-11-05",
      "headers": {
        "X-API-Version": "v1",
        "X-Service-Name": "evidence-server"
      },
      "tools": ["upload_evidence", "list_evidence", "get_evidence", "delete_evidence", "tag_evidence"]
    },
    "audit-server": {
      "httpUrl": "http://localhost:5002/mcp",
      "timeout": 30000,
      "trust": true,
      "description": "Runs automated compliance checks and scores controls",
      "version": "2.0.0",
      "protocol": "2024-11-05",
      "headers": {
        "Authorization": "Bearer audit-service-token",
        "X-API-Version": "v2"
      },
      "tools": ["run_audit_check", "run_full_audit", "get_audit_score", "get_failing_controls"]
    },
    "policy-server": {
      "command": "python",
      "args": ["servers/policy_server.py", "--strict-mode", "--version", "v2"],
      "description": "Manages security policies and approval workflows",
      "version": "1.0.0",
      "protocol": "2024-11-05",
      "trust": false,
      "env": {
        "POLICY_STORE": "sqlite:///compliance.db",
        "POLICY_APPROVAL_REQUIRED": "true",
        "POLICY_MAX_VERSIONS": "10"
      },
      "tools": ["create_policy", "get_policy", "list_policies", "approve_policy", "get_policy_version_history"]
    },
    "vendor-server": {
      "httpUrl": "http://localhost:5003/mcp",
      "timeout": 45000,
      "trust": false,
      "description": "Third-party vendor risk assessment and management",
      "version": "1.3.0",
      "protocol": "2024-11-05",
      "headers": {
        "Authorization": "Bearer vendor-service-token",
        "X-Risk-Threshold": "high"
      },
      "tools": ["add_vendor", "list_vendors", "update_vendor_risk", "list_high_risk_vendors"]
    },
    "report-server": {
      "command": "python",
      "args": ["servers/report_server.py", "--format", "pdf", "--output-dir", "./reports"],
      "description": "Generates audit-ready compliance reports and executive summaries",
      "version": "1.5.0",
      "protocol": "2024-11-05",
      "trust": true,
      "env": {
        "REPORT_OUTPUT_DIR": "./reports",
        "SMTP_HOST": "smtp.gmail.com",
        "SMTP_PORT": "587",
        "SMTP_USE_TLS": "true"
      },
      "tools": ["generate_readiness_report", "generate_gap_report", "generate_executive_summary", "list_generated_reports"]
    },
    "gap-analysis-server": {
      "httpUrl": "http://localhost:5004/mcp",
      "timeout": 30000,
      "trust": false,
      "description": "Identifies compliance gaps and tracks remediation progress",
      "version": "1.0.0",
      "protocol": "2024-11-05",
      "headers": {
        "X-API-Version": "v1",
        "X-Gap-Severity-Filter": "critical,high"
      },
      "tools": ["get_all_gaps", "get_critical_gaps", "mark_gap_resolved", "get_gap_summary"]
    },
    "schedule-server": {
      "command": "python",
      "args": ["servers/schedule_server.py", "--reminder-days", "30", "--timezone", "UTC"],
      "description": "Tracks audit deadlines and manages compliance calendar",
      "version": "1.1.0",
      "protocol": "2024-11-05",
      "trust": false,
      "env": {
        "SMTP_HOST": "smtp.gmail.com",
        "SMTP_PORT": "587",
        "ALERT_EMAIL": "compliance@company.com",
        "REMINDER_DAYS_BEFORE": "30,14,7,1"
      },
      "tools": ["add_deadline", "list_deadlines", "get_overdue_items", "get_upcoming_deadlines", "mark_complete"]
    }
  }
}
```

## Server Details

| Server | Transport | Port | Version | Trust | Purpose |
|--------|-----------|------|---------|-------|---------|
| framework-server | stdio | — | 1.2.0 | false | Compliance framework & control catalog |
| evidence-server | HTTP | 5001 | 1.1.0 | false | Evidence collection & management |
| audit-server | HTTP | 5002 | 2.0.0 | true | Automated audit checks & scoring |
| policy-server | stdio | — | 1.0.0 | false | Policy lifecycle management |
| vendor-server | HTTP | 5003 | 1.3.0 | false | Third-party vendor risk tracking |
| report-server | stdio | — | 1.5.0 | true | Report generation & export |
| gap-analysis-server | HTTP | 5004 | 1.0.0 | false | Gap identification & remediation |
| schedule-server | stdio | — | 1.1.0 | false | Deadline tracking & reminders |

## Quick Start

```bash
pip install fastapi fastmcp uvicorn jinja2 aiosqlite
python app.py
```

Open http://localhost:8000 in your browser.
