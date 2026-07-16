# AI Regulation Monitor — v1.1 Roadmap

**Document version:** 1.0  
**Baseline release:** v1.0.0 (July 2026)  
**Target release:** v1.1.0 (Q4 2026 — tentative)  
**Primary users:** Internal Smart TV compliance, product engineering, and platform teams

---

## 1. v1.0 Achievement Summary

AI Regulation Monitor v1.0.0 delivered a complete internal compliance monitoring platform for Smart TV and connected device teams. The release is production-ready for trusted internal networks.

### What We Shipped

| Area | Delivered capability |
|------|-------------------|
| **Monitoring** | Multi-source crawls (daily/weekly), smart link discovery, crawl cache, PDF support, snapshot diff detection |
| **AI analysis** | Impact levels (HIGH/MEDIUM/LOW), affected Smart TV modules, recommended actions, regulation extraction |
| **Knowledge** | Searchable knowledge base, relationships, similarity, timelines, compliance insights dashboard |
| **Reporting** | Weekly AI reports, scheduled generation, optional SMTP email delivery |
| **Dashboard** | Full web UI — monitors, changes, knowledge, insights, reports, monitor management, about page |
| **Operations** | Docker Compose deployment, logging, health API, configuration validation, scheduler status tracking |
| **Demo & docs** | Demo mode CLI, demo data package, architecture/user/deployment guides, management presentation |

### Release Metrics

| Metric | Value |
|--------|-------|
| Automated tests | 270+ (261 at v1.0 baseline; expanded with demo and config validation) |
| Deployment model | Two-container Docker (dashboard + scheduler) |
| Regulation focus | EU sources — AI Act, product compliance, broadcasting-related portals |
| Product modules mapped | HbbTV, AI features, voice assistant, OTA, cybersecurity, network services, and related areas |

### Business Outcomes Enabled

- Engineers spend less time manually checking regulation websites
- Compliance changes surface through a single dashboard instead of ad hoc email chains
- Structured knowledge persists across team turnover
- Weekly reports provide a repeatable management deliverable

---

## 2. Current Limitations

These constraints define the scope of v1.1 planning. They reflect deliberate v1.0 boundaries, not defects.

### Platform & Security

| Limitation | Impact on Smart TV compliance team |
|------------|--------------------------------------|
| No authentication or role-based access | Suitable only on trusted internal networks; no per-team visibility controls |
| Single-node SQLite | Adequate for small teams; may bottleneck with many concurrent dashboard users |
| No built-in backup/restore | Operators must manually back up `data/` and `config/` volumes |
| No audit log for user actions | Cannot trace who acknowledged or dismissed a compliance item |

### Monitoring & Data

| Limitation | Impact |
|------------|--------|
| EU-focused source catalogue | National or APAC regulations require manual monitor setup |
| English-only UI and reports | Non-English source pages are crawled but UI narrative is English |
| Crawl variability | Third-party site redesigns can reduce discovery quality until monitors are tuned |
| No change acknowledgement workflow | Teams cannot mark items as "reviewed" or "accepted risk" in the platform |

### AI & Intelligence

| Limitation | Impact |
|------------|--------|
| Batch analysis only | No interactive Q&A over regulation history |
| Keyword/similarity search | Cannot ask natural-language questions like "What changed about OTA last quarter?" |
| Single LLM provider | OpenAI dependency; no fallback or model selection per task |
| Human validation not tracked | AI triage is shown but sign-off state is external to the tool |

### Integration & Collaboration

| Limitation | Impact |
|------------|--------|
| Email-only notification channel | No Teams or Slack alerts for HIGH-impact changes |
| No Jira/task system integration | Recommended actions are not auto-created as engineering tickets |
| No export API | Knowledge and reports cannot be pulled into GRC or document systems programmatically |
| Demo mode is CLI-only | Dashboard does not yet have a dedicated demo/preview mode for presentations |

---

## 3. User Feedback Collection Plan

v1.1 priorities will be driven by structured feedback from the internal Smart TV compliance team and adjacent stakeholders. Collection runs for **6 weeks** after v1.0 rollout.

### Target Participants

| Group | Representatives | Focus |
|-------|-----------------|-------|
| Compliance / legal liaison | 2–3 | Report quality, audit readiness, source coverage |
| Smart TV engineering leads | 3–5 | Impact accuracy, module mapping, action clarity |
| Product managers | 2–3 | Insights dashboard, weekly report usefulness |
| Platform / DevOps | 1–2 | Deployment, logging, health, backup |

### Collection Methods

**1. Structured survey (Week 2 and Week 6)**  
- 15-question form covering: daily workflow, trust in AI impact levels, missing features, integration needs  
- Distributed via internal email; target ≥ 70% response from active users  
- Stored in shared compliance team folder (spreadsheet or internal form tool)

**2. Bi-weekly office hours (30 minutes)**  
- Open session after weekly report delivery  
- Demo new workflows; capture pain points in a shared feedback log  
- Rotating facilitator from compliance team

**3. Usage observation (ongoing)**  
- Track: monitor run frequency, report opens, knowledge searches, HIGH-impact change views  
- Source: application logs (`logs/app.log`), run history (`data/run_history.json`), optional simple access log in v1.1  
- Monthly summary presented to engineering management

**4. Post-incident reviews**  
- When a regulation change is discovered late or AI impact is disputed, conduct a 15-minute retrospective  
- Document: root cause, monitor gap, AI prompt gap, or process gap  
- Feed into v1.1 backlog as tagged items

**5. Feedback backlog triage (Week 7)**  
- Product owner + compliance lead rank items using the priority matrix (Section 5)  
- Publish v1.1 scope decision memo to stakeholders

### Feedback Categories

| Tag | Example |
|-----|---------|
| `accuracy` | "AI marked LOW but we assessed HIGH for OTA" |
| `workflow` | "Need to mark changes as reviewed" |
| `integration` | "Send HIGH alerts to Teams channel" |
| `coverage` | "Add UK OPSS and Germany BNetzA sources" |
| `ops` | "Automated backup of SQLite database" |
| `ux` | "Export report to PDF for management" |

---

## 4. v1.1 Feature Roadmap

v1.1 theme: **Operate, collaborate, and trust** — harden v1.0 for daily Smart TV compliance team use without the architectural leap of v2.0.

### Proposed Features

#### A. Collaboration & Notifications (High demand expected)

| Feature | Description |
|---------|-------------|
| **Microsoft Teams webhook alerts** | Post HIGH/MEDIUM change summaries to a compliance channel |
| **Change acknowledgement** | Mark changes as Reviewed / In Progress / Accepted Risk with timestamp and optional note |
| **Report PDF export** | Download weekly report as PDF for management distribution |

#### B. Workflow & Usability

| Feature | Description |
|---------|-------------|
| **Review queue dashboard** | Filter changes by unreviewed status and age |
| **Monitor templates** | Pre-built monitor packs for EU AI Act, RED, cybersecurity themes |
| **Dashboard demo mode** | Read-only UI loading `data/demo/` for stable presentations |
| **Bulk monitor import/export** | JSON import/export for monitor configuration |

#### C. Operations & Reliability

| Feature | Description |
|---------|-------------|
| **Scheduled database backup** | Nightly SQLite backup to `data/backups/` with retention policy |
| **Enhanced health dashboard** | `/about` or `/health` extension showing last job times, disk usage, API key status |
| **Basic access logging** | Log dashboard page views and report generation events |
| **Lightweight auth (optional)** | HTTP basic auth or SSO proxy header support for internal deployment |

#### D. AI & Data Quality

| Feature | Description |
|---------|-------------|
| **Impact override** | Allow compliance lead to override AI impact level with reason (stored, not retraining) |
| **Analysis feedback flag** | "Incorrect analysis" flag for feedback collection |
| **Module taxonomy config** | Configurable Smart TV module list in `config/modules.json` |
| **Improved diff summary** | Shorter AI-generated change summary for Changes list view |

#### E. Reporting & Export

| Feature | Description |
|---------|-------------|
| **Custom report period** | Generate report for arbitrary date range from dashboard |
| **Knowledge CSV export** | Export filtered knowledge items for GRC tools |
| **Report comparison** | Side-by-side diff of two weekly reports |

### Out of Scope for v1.1 (Deferred to v2.0)

- RAG chatbot and natural-language Q&A
- Vector database and semantic search
- Jira ticket auto-creation
- Multi-language regulation analysis
- Multi-country packaged source library
- Replacement of SQLite with PostgreSQL

### Tentative Timeline

| Milestone | Target |
|-----------|--------|
| Feedback collection complete | Week 7 post-v1.0 |
| v1.1 scope locked | Week 8 |
| Development sprint 1 (collaboration + workflow) | Weeks 9–12 |
| Development sprint 2 (ops + export) | Weeks 13–16 |
| v1.1.0 release candidate | Week 17 |
| Internal rollout | Week 18 |

---

## 5. Priority Matrix

Features ranked by **business value** (Y) vs **implementation effort** (X) for the Smart TV compliance team.

```
                        EFFORT
                 Low              High
              ┌─────────────────┬─────────────────┐
         High │ QUICK WINS      │ STRATEGIC       │
              │                 │                 │
    VALUE     │ • Teams alerts  │ • Lightweight   │
              │ • Review queue  │   auth          │
              │ • PDF export    │ • Backup/restore│
              │ • Demo dashboard│   automation    │
              │ • Impact override│ • Report compare│
              ├─────────────────┼─────────────────┤
         Low  │ FILL-INS        │ DEFER           │
              │                 │                 │
              │ • Module config │ • Jira integration│
              │ • Bulk monitor  │ • RAG chatbot   │
              │   import/export │ • Vector search │
              │ • Access logging│ • Multi-language│
              └─────────────────┴─────────────────┘
```

### Recommended v1.1 Priority Order

| Priority | Feature | Rationale |
|----------|---------|-----------|
| P0 | Teams webhook alerts | Highest collaboration ask; closes email-only gap |
| P0 | Change acknowledgement + review queue | Core daily workflow for compliance team |
| P1 | Report PDF export | Management reporting without manual formatting |
| P1 | Dashboard demo mode | Stable demos for leadership (extends CLI demo) |
| P1 | Scheduled database backup | Operational risk reduction |
| P2 | Impact override + feedback flag | Improves AI trust without model retraining |
| P2 | Custom report period | Flexibility for quarterly reviews |
| P2 | Module taxonomy config | Aligns AI output with internal product naming |
| P3 | Lightweight auth | Needed only if dashboard moves beyond trusted VLAN |
| P3 | Knowledge CSV export | GRC integration lite |

*Final order subject to feedback collection results (Section 3).*

---

## 6. Future AI Architecture Direction

v1.1 improves operability and team workflow. **v2.0** introduces a new AI layer. This section describes the directional architecture — not committed v1.1 scope.

### Current AI Architecture (v1.0)

```
Regulation Content → Diff → Single-shot LLM Prompt → Structured JSON → Storage → Dashboard
```

- **Pattern:** Batch, stateless analysis per change  
- **Storage:** SQLite relational + markdown snapshots  
- **Retrieval:** SQL search and keyword similarity  
- **Limitation:** No conversational context; each analysis is isolated

### Target AI Architecture (v2.0+)

```
                    ┌─────────────────────────────────────┐
                    │         Knowledge Ingestion          │
                    │  Snapshots │ Diffs │ Knowledge Items │
                    └─────────────────┬───────────────────┘
                                      │
                              Embedding Pipeline
                                      │
                    ┌─────────────────▼───────────────────┐
                    │      Vector Store (regulation index) │
                    │   chunks + metadata + module tags    │
                    └─────────────────┬───────────────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              │                       │                       │
        RAG Chatbot            Semantic Search          Report Agent
    (compliance Q&A)         (cross-regulation)      (multi-step summary)
              │                       │                       │
              └───────────────────────┼───────────────────────┘
                                      │
                    ┌─────────────────▼───────────────────┐
                    │   Orchestration Layer (agent router)  │
                    │   retrieve → reason → cite sources    │
                    └─────────────────┬───────────────────┘
                                      │
                    Dashboard │ Teams │ Jira │ API
```

### Architectural Principles

| Principle | Description |
|-----------|-------------|
| **Citation-first** | Every AI answer links to source snapshot, diff, and URL |
| **Human-in-the-loop** | Overrides and feedback from v1.1 train prompt and retrieval tuning |
| **Module-aware retrieval** | Embeddings tagged with Smart TV module taxonomy |
| **Incremental migration** | Vector index built from existing knowledge base — no big-bang rewrite |
| **Provider abstraction** | Interface layer to support OpenAI and alternative models per task |

### Smart TV Compliance Use Cases Enabled by v2.0 AI

| Use case | Example query |
|----------|---------------|
| Historical lookup | "What OTA-related regulation changes occurred in the last 6 months?" |
| Cross-regulation analysis | "Does the latest AI Act guidance conflict with our RED cybersecurity interpretation?" |
| Onboarding | New engineer asks "What regulations affect voice assistant in EU markets?" |
| Report drafting | Agent assembles quarterly compliance brief from vector-indexed changes |

### v1.1 → v2.0 Bridge

v1.1 deliberately lays groundwork:

- **Acknowledgement and feedback flags** → labelled data for retrieval tuning  
- **Module taxonomy config** → embedding metadata schema  
- **Export and logging** → training corpus boundaries and audit trail  
- **Teams integration** → delivery channel for future agent notifications  

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | July 2026 | Platform team | Initial v1.1 roadmap post-v1.0 release |

## Related Documents

- [Release Notes v1.0](release_notes_v1.0.md)
- [Architecture](architecture.md)
- [Demo Guide](demo-guide.md)
- [Demo Script v1.0](demo-script-v1.0.md)
- [Test Report](test_report.md)

---

*This roadmap is a planning document. Scope and dates will be updated after user feedback collection (Section 3).*
