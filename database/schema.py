import aiosqlite
import os
from datetime import datetime, timedelta

DB_PATH = os.environ.get("DB_PATH", "compliance.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS frameworks (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    version TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS controls (
    id TEXT PRIMARY KEY,
    framework_id TEXT NOT NULL,
    category TEXT,
    title TEXT NOT NULL,
    description TEXT,
    guidance TEXT,
    status TEXT DEFAULT 'not_started',
    FOREIGN KEY (framework_id) REFERENCES frameworks(id)
);

CREATE TABLE IF NOT EXISTS evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    control_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    description TEXT,
    tags TEXT,
    uploaded_at TEXT DEFAULT (datetime('now')),
    file_path TEXT,
    FOREIGN KEY (control_id) REFERENCES controls(id)
);

CREATE TABLE IF NOT EXISTS audit_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    control_id TEXT NOT NULL,
    framework_id TEXT NOT NULL,
    status TEXT NOT NULL,
    score INTEGER DEFAULT 0,
    findings TEXT,
    audited_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (control_id) REFERENCES controls(id)
);

CREATE TABLE IF NOT EXISTS policies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    content TEXT,
    framework_id TEXT,
    control_ids TEXT,
    version INTEGER DEFAULT 1,
    status TEXT DEFAULT 'draft',
    approver TEXT,
    approved_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS policy_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    policy_id INTEGER NOT NULL,
    version INTEGER NOT NULL,
    content TEXT,
    changed_at TEXT DEFAULT (datetime('now')),
    changed_by TEXT,
    FOREIGN KEY (policy_id) REFERENCES policies(id)
);

CREATE TABLE IF NOT EXISTS vendors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    service TEXT,
    risk_level TEXT DEFAULT 'medium',
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS vendor_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor_id INTEGER NOT NULL,
    score INTEGER,
    findings TEXT,
    assessed_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (vendor_id) REFERENCES vendors(id)
);

CREATE TABLE IF NOT EXISTS gaps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    framework_id TEXT NOT NULL,
    control_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    severity TEXT DEFAULT 'medium',
    status TEXT DEFAULT 'open',
    owner TEXT,
    due_date TEXT,
    resolved_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (framework_id) REFERENCES frameworks(id),
    FOREIGN KEY (control_id) REFERENCES controls(id)
);

CREATE TABLE IF NOT EXISTS deadlines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    framework_id TEXT,
    due_date TEXT NOT NULL,
    owner TEXT,
    status TEXT DEFAULT 'pending',
    reminder_sent INTEGER DEFAULT 0,
    completed_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (framework_id) REFERENCES frameworks(id)
);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    report_type TEXT NOT NULL,
    framework_id TEXT,
    content TEXT,
    generated_at TEXT DEFAULT (datetime('now'))
);
"""

SEED_FRAMEWORKS = [
    ("soc2", "SOC 2 Type II", "Service Organization Control 2 - Trust Services Criteria", "2022"),
    ("iso27001", "ISO 27001:2022", "Information Security Management System standard", "2022"),
    ("hipaa", "HIPAA", "Health Insurance Portability and Accountability Act", "2013"),
    ("pci-dss", "PCI-DSS v4.0", "Payment Card Industry Data Security Standard", "4.0"),
    ("nist-csf", "NIST CSF 2.0", "NIST Cybersecurity Framework", "2.0"),
]

SEED_CONTROLS = [
    # SOC 2
    ("SOC2-CC1.1", "soc2", "Control Environment", "COSO Principle 1: Commitment to Integrity",
     "The entity demonstrates a commitment to integrity and ethical values.", "Implement code of conduct, ethics training", "compliant"),
    ("SOC2-CC2.1", "soc2", "Communication", "Information Quality Policy",
     "The entity obtains or generates relevant quality information.", "Define information quality criteria", "in_progress"),
    ("SOC2-CC3.1", "soc2", "Risk Assessment", "Risk Identification",
     "The entity specifies objectives with sufficient clarity to enable risk identification.", "Document risk register", "not_started"),
    ("SOC2-CC6.1", "soc2", "Logical Access", "Access Control Policy",
     "Logical access security software, infrastructure, and architectures are implemented.", "MFA, least privilege, access reviews", "compliant"),
    ("SOC2-CC6.2", "soc2", "Logical Access", "User Registration",
     "Prior to issuing system credentials, entity registers and authorizes new users.", "Formal onboarding process", "in_progress"),
    ("SOC2-CC7.1", "soc2", "System Operations", "Vulnerability Management",
     "Detection and monitoring to identify threats against the achievement of objectives.", "Monthly vulnerability scans", "not_started"),
    ("SOC2-CC8.1", "soc2", "Change Management", "Change Control Process",
     "Changes to infrastructure, data, software, and procedures are authorized and managed.", "Change advisory board, ticket system", "compliant"),
    ("SOC2-A1.1", "soc2", "Availability", "Performance Monitoring",
     "The entity maintains, monitors and evaluates current processing capacity.", "APM tooling, SLA dashboards", "in_progress"),
    # ISO 27001
    ("ISO-A.5.1", "iso27001", "Information Security Policies", "Policies for Information Security",
     "Information security policy and topic-specific policies shall be defined.", "Create and publish InfoSec policy", "compliant"),
    ("ISO-A.6.1", "iso27001", "Organization", "Information Security Roles",
     "All information security responsibilities shall be defined and allocated.", "RACI matrix for security roles", "in_progress"),
    ("ISO-A.8.1", "iso27001", "Asset Management", "Inventory of Assets",
     "Assets associated with information and processing facilities shall be inventoried.", "CMDB, asset tagging", "not_started"),
    ("ISO-A.9.1", "iso27001", "Access Control", "Access Control Policy",
     "An access control policy shall be established, documented and reviewed.", "IAM policy document", "compliant"),
    ("ISO-A.12.1", "iso27001", "Operations Security", "Documented Operating Procedures",
     "Operating procedures shall be documented and made available to users.", "Runbooks, SOPs", "in_progress"),
    ("ISO-A.16.1", "iso27001", "Incident Management", "Responsibilities and Procedures",
     "Management responsibilities shall ensure a quick effective response to incidents.", "Incident response plan, runbooks", "not_started"),
    # HIPAA
    ("HIPAA-164.308a1", "hipaa", "Administrative Safeguards", "Security Management Process",
     "Implement policies to prevent, detect, contain, and correct security violations.", "Risk analysis, risk management policy", "compliant"),
    ("HIPAA-164.308a3", "hipaa", "Administrative Safeguards", "Workforce Security",
     "Implement policies to ensure workforce access is appropriate.", "Background checks, termination procedures", "in_progress"),
    ("HIPAA-164.312a1", "hipaa", "Technical Safeguards", "Access Control",
     "Implement technical policies restricting access to ePHI.", "Role-based access, unique user IDs", "not_started"),
    ("HIPAA-164.312e1", "hipaa", "Technical Safeguards", "Transmission Security",
     "Implement technical measures to guard against unauthorized access to ePHI in transit.", "TLS 1.2+, VPN for remote access", "compliant"),
    # PCI-DSS
    ("PCI-1.1", "pci-dss", "Network Security", "Firewall Configuration",
     "Install and maintain network security controls.", "Firewall ruleset review, network diagrams", "compliant"),
    ("PCI-2.1", "pci-dss", "Secure Configuration", "System Components",
     "Apply secure configurations to all system components.", "CIS benchmarks, hardening guides", "in_progress"),
    ("PCI-3.1", "pci-dss", "Account Data Protection", "Data Retention",
     "Protect stored account data.", "Data minimization, encryption at rest", "not_started"),
    ("PCI-8.1", "pci-dss", "User Identification", "User Management",
     "Identify users and authenticate access to system components.", "Unique IDs, MFA for all admin access", "compliant"),
    # NIST CSF
    ("NIST-ID.AM-1", "nist-csf", "Identify", "Asset Management",
     "Physical devices and systems within the organization are inventoried.", "Hardware asset inventory", "in_progress"),
    ("NIST-PR.AC-1", "nist-csf", "Protect", "Access Control",
     "Identities and credentials are managed for authorized devices and users.", "IAM system, privileged access management", "compliant"),
    ("NIST-DE.CM-1", "nist-csf", "Detect", "Continuous Monitoring",
     "The network is monitored to detect potential cybersecurity events.", "SIEM, IDS/IPS deployment", "not_started"),
    ("NIST-RS.RP-1", "nist-csf", "Respond", "Response Planning",
     "Response plan is executed during or after an incident.", "Tested incident response plan", "in_progress"),
]

SEED_VENDORS = [
    ("AWS", "Cloud Infrastructure", "low", "Primary cloud provider, SOC 2 Type II certified"),
    ("Salesforce", "CRM Platform", "medium", "Processes customer PII, annual assessments required"),
    ("Okta", "Identity Provider", "low", "SSO and MFA provider, SOC 2 certified"),
    ("Zendesk", "Customer Support", "medium", "Handles support tickets, access customer data"),
    ("SendGrid", "Email Service", "low", "Transactional email only"),
    ("DataBricks", "Data Analytics", "high", "Processes sensitive analytics data"),
    ("Stripe", "Payment Processing", "high", "PCI-DSS compliant payment processor"),
]

SEED_GAPS = [
    ("soc2", "SOC2-CC3.1", "Risk Register Not Established",
     "No formal risk register exists; risk identification process is ad hoc.", "critical", "open", "CISO", 30),
    ("soc2", "SOC2-CC7.1", "Vulnerability Scanning Not Automated",
     "Vulnerability scans are manual and infrequent.", "high", "open", "Security Team", 45),
    ("iso27001", "ISO-A.8.1", "Asset Inventory Incomplete",
     "IT asset inventory covers only 60% of known assets.", "high", "open", "IT Ops", 60),
    ("iso27001", "ISO-A.16.1", "Incident Response Plan Missing",
     "No documented incident response plan; previous incidents handled ad hoc.", "critical", "open", "CISO", 14),
    ("hipaa", "HIPAA-164.312a1", "ePHI Access Controls Insufficient",
     "Role-based access to ePHI not fully implemented in legacy systems.", "critical", "open", "IT Security", 21),
    ("pci-dss", "PCI-3.1", "PANs Stored Unencrypted in Logs",
     "Application logs contain full PANs in some error paths.", "critical", "open", "Dev Team", 7),
    ("nist-csf", "NIST-DE.CM-1", "SIEM Not Deployed",
     "No centralized security information and event management system.", "high", "open", "Security Team", 90),
]

SEED_DEADLINES = [
    ("SOC 2 Type II Audit Preparation", "soc2", 45, "Compliance Manager"),
    ("ISO 27001 Internal Audit", "iso27001", 30, "Quality Manager"),
    ("HIPAA Risk Assessment Annual Review", "hipaa", 60, "Privacy Officer"),
    ("PCI-DSS SAQ Submission", "pci-dss", 15, "PCI Coordinator"),
    ("Vendor Risk Assessment - DataBricks", "soc2", 20, "Vendor Manager"),
    ("Policy Review Cycle Q2", "soc2", -5, "Compliance Manager"),  # overdue
    ("Penetration Test Scheduling", "nist-csf", -10, "CISO"),  # overdue
]


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()

        row = await db.execute("SELECT COUNT(*) FROM frameworks")
        count = (await row.fetchone())[0]
        if count > 0:
            return

        await db.executemany(
            "INSERT INTO frameworks (id, name, description, version) VALUES (?,?,?,?)",
            SEED_FRAMEWORKS
        )

        await db.executemany(
            "INSERT INTO controls (id, framework_id, category, title, description, guidance, status) VALUES (?,?,?,?,?,?,?)",
            SEED_CONTROLS
        )

        await db.executemany(
            "INSERT INTO vendors (name, service, risk_level, notes) VALUES (?,?,?,?)",
            SEED_VENDORS
        )

        now = datetime.now()
        for fw, ctrl, title, desc, severity, status, owner, days_offset in SEED_GAPS:
            due = (now + timedelta(days=days_offset)).strftime("%Y-%m-%d")
            await db.execute(
                "INSERT INTO gaps (framework_id, control_id, title, description, severity, status, owner, due_date) VALUES (?,?,?,?,?,?,?,?)",
                (fw, ctrl, title, desc, severity, status, owner, due)
            )

        for title, fw, days_offset, owner in SEED_DEADLINES:
            due = (now + timedelta(days=days_offset)).strftime("%Y-%m-%d")
            await db.execute(
                "INSERT INTO deadlines (title, framework_id, due_date, owner) VALUES (?,?,?,?)",
                (title, fw, due, owner)
            )

        # Seed some audit results
        audit_data = [
            ("SOC2-CC1.1", "soc2", "pass", 95, "Control environment well documented"),
            ("SOC2-CC6.1", "soc2", "pass", 88, "MFA enforced, access reviews quarterly"),
            ("SOC2-CC8.1", "soc2", "pass", 92, "Change management process mature"),
            ("SOC2-CC2.1", "soc2", "partial", 60, "Information quality policy exists but not enforced"),
            ("SOC2-CC3.1", "soc2", "fail", 10, "No formal risk register found"),
            ("SOC2-CC7.1", "soc2", "fail", 20, "Vulnerability scans not automated"),
            ("ISO-A.5.1", "iso27001", "pass", 90, "InfoSec policy published and reviewed"),
            ("ISO-A.9.1", "iso27001", "pass", 85, "Access control policy documented"),
            ("ISO-A.8.1", "iso27001", "fail", 40, "Asset inventory incomplete"),
            ("HIPAA-164.308a1", "hipaa", "pass", 88, "Risk analysis completed"),
            ("HIPAA-164.312e1", "hipaa", "pass", 95, "TLS enforced across all endpoints"),
            ("PCI-1.1", "pci-dss", "pass", 90, "Firewall rules reviewed and approved"),
            ("PCI-8.1", "pci-dss", "pass", 95, "MFA required for all admin access"),
        ]
        await db.executemany(
            "INSERT INTO audit_results (control_id, framework_id, status, score, findings) VALUES (?,?,?,?,?)",
            audit_data
        )

        await db.commit()
