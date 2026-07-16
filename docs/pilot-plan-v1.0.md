# AI Regulation Monitor v1.0.0 — Internal Pilot Plan

**Document version:** 1.0  
**Pilot duration:** 6 weeks  
**Baseline release:** v1.0.0  
**Audience:** Smart TV compliance engineering team  
**Pilot owner:** Compliance platform lead (assign before Week 1)  
**Status:** Ready for internal validation

---

## 1. Pilot Objective

The internal pilot validates AI Regulation Monitor in real Smart TV compliance workflows before broader rollout and v1.1 investment.

### Primary Objectives

| Objective | Description | Success signal |
|-----------|-------------|----------------|
| **Validate usefulness** | Confirm the platform surfaces regulation changes that matter to Smart TV product teams faster than manual tracking | ≥ 70% of pilot users report the tool is useful or very useful (Week 4 survey) |
| **Measure effort reduction** | Quantify time saved on manual website checks, diff review, and weekly status compilation | ≥ 30% self-reported reduction in manual regulation tracking hours per week |
| **Inform v1.1 planning** | Collect structured feedback on accuracy, workflow gaps, and integration needs | Prioritized v1.1 backlog documented by end of Week 6 |

### Secondary Objectives

- Validate Docker deployment stability for daily/weekly scheduled runs
- Establish baseline KPIs for crawl reliability and AI analysis quality
- Train compliance and engineering leads on dashboard, knowledge base, and weekly reports
- Produce pilot summary report for engineering management

### Out of Scope for Pilot

- External authentication or SSO rollout
- Production integration with Jira, Teams, or GRC systems (captured as v1.1 requests only)
- Non-EU geographic expansion beyond defined German sources
- Model fine-tuning or custom LLM deployment

---

## 2. Target Users

Five roles participate in the pilot. Each has distinct usage patterns and information needs.

### Compliance Engineer

| Aspect | Detail |
|--------|--------|
| **Expected usage** | Daily dashboard review; triage HIGH/MEDIUM changes; validate AI impact assessments; maintain monitor configuration; own weekly report distribution |
| **Information needed** | Full diff text, source URL, impact level, affected modules, recommended actions, regulation relationships, audit trail of pipeline runs |
| **Pilot responsibilities** | Primary platform owner; configure monitors; lead Monday reviews; compile Friday feedback summary |
| **Key pages** | `/changes`, `/detail/{id}`, `/knowledge`, `/reports`, `/manage-monitors` |

### Product Manager

| Aspect | Detail |
|--------|--------|
| **Expected usage** | Weekly review of compliance insights and executive report; prioritize cross-module themes (AI, OTA, cybersecurity) for roadmap discussions |
| **Information needed** | Impact summary by module, executive narrative, key changes list, trend across reporting period |
| **Pilot responsibilities** | Assess report usefulness for management; flag missing product modules or unclear summaries |
| **Key pages** | `/`, `/insights`, `/reports` |

### Firmware Engineer

| Aspect | Detail |
|--------|--------|
| **Expected usage** | Review changes affecting OTA update, bootloader security, device integrity, and radio/RF compliance after Wednesday engineering sync |
| **Information needed** | Diff content, affected modules (OTA, cybersecurity controls), actionable engineering steps, source traceability |
| **Pilot responsibilities** | Validate technical accuracy of recommended actions for firmware scope; report false positives |
| **Key pages** | `/changes`, `/detail/{id}` |

### AI Feature Owner

| Aspect | Detail |
|--------|--------|
| **Expected usage** | Monitor EU AI Act and CRA-related changes; assess impact on embedded AI, voice assistant, and on-device inference features |
| **Information needed** | AI Act/CRA categorization context, HIGH/MEDIUM flags for AI modules, knowledge base search by "AI Act" and "high-risk" |
| **Pilot responsibilities** | Review AI analysis quality for AI-specific regulations; suggest keyword and module taxonomy improvements |
| **Key pages** | `/knowledge`, `/insights`, `/changes` |

### Software Engineer (Platform / Application)

| Aspect | Detail |
|--------|--------|
| **Expected usage** | Review changes affecting Browser/HbbTV, CI+, network services, and application-layer compliance; occasional knowledge search during feature design |
| **Information needed** | HbbTV/DVB/CI+ related diffs, module mapping to application stack, links to industry standard updates |
| **Pilot responsibilities** | Confirm industry monitor relevance; feedback on crawl noise vs signal for standard-body sites |
| **Key pages** | `/changes`, `/knowledge`, `/monitors` |

### Pilot Team Size (Recommended)

| Role | Headcount |
|------|-----------|
| Compliance Engineer | 1–2 |
| Product Manager | 1 |
| Firmware Engineer | 1 |
| AI Feature Owner | 1 |
| Software Engineer | 1–2 |
| **Total active participants** | **5–7** |

---

## 3. Pilot Scope

### Regulation Domains

The pilot covers EU product and digital regulation, industry standards relevant to Smart TV, and selected German national sources.

#### EU Regulations & Directives

| Domain | Relevance to Smart TV |
|--------|----------------------|
| **EU AI Act** | Embedded AI, voice assistant, content recommendation, on-device inference |
| **Cyber Resilience Act (CRA)** | Product security, vulnerability handling, security updates for connected devices |
| **Radio Equipment Directive (RED)** | RF compliance, cybersecurity requirements for radio equipment, CE marking |
| **Energy Efficiency Regulations** | Standby/off-mode power, ecodesign, energy labelling for displays |

#### Industry Standards & Bodies

| Domain | Relevance to Smart TV |
|--------|----------------------|
| **DVB** | Broadcast standards, CI compatibility, receiver specifications |
| **HbbTV** | Hybrid broadcast-broadband TV application layer |
| **CI Plus** | Common Interface Plus conditional access and content protection |

#### Germany

| Domain | Relevance to Smart TV |
|--------|----------------------|
| **Federal regulatory sources** | National transposition, market surveillance, energy and environmental product rules affecting electronics sold in Germany |

### Geographic & Language Scope

- **Primary:** EU official sources (English pages where available)
- **Secondary:** Germany (English or German pages — UI remains English)
- **Excluded from pilot:** Spain (BOE), other national sources beyond Germany unless added by compliance lead

### Functional Scope (Platform Features)

| In scope | Out of scope |
|----------|--------------|
| Scheduled daily/weekly crawls | Custom LLM training |
| AI impact analysis | Jira/Teams integration |
| Knowledge base and insights | PDF export (v1.1) |
| Weekly AI report + optional email | Change acknowledgement workflow (v1.1) |
| Docker deployment | External user access |

---

## 4. Initial Monitor Configuration

The following monitors define the pilot baseline. Existing v1.0 monitors are retained where they overlap; new monitors are added during Week 1 setup.

### EU Regulations

#### EU AI Act *(existing — enable)*

| Field | Value |
|-------|-------|
| **Monitor name** | EU AI Act |
| **Source URL** | https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai |
| **Category** | AI Regulation |
| **Keywords** | AI Act, artificial intelligence, high-risk, smart TV, voice assistant, consumer electronics |
| **Crawl frequency** | Daily |
| **Crawl mode** | Smart (depth 2, max 10 pages) |
| **Expected output** | Change diffs when AI Act guidance updates; MEDIUM/HIGH impact on AI features and voice assistant modules |

#### Cyber Resilience Act (CRA) *(add Week 1)*

| Field | Value |
|-------|-------|
| **Monitor name** | EU Cyber Resilience Act |
| **Source URL** | https://digital-strategy.ec.europa.eu/en/policies/cyber-resilience-act |
| **Category** | Cybersecurity Regulation |
| **Keywords** | CRA, cyber resilience, vulnerability, security update, connected product, IoT, smart TV |
| **Crawl frequency** | Daily |
| **Crawl mode** | Smart (depth 2, max 10 pages) |
| **Expected output** | Security obligation changes; impact on OTA update, cybersecurity controls, network services |

#### Radio Equipment Directive (RED) *(add Week 1)*

| Field | Value |
|-------|-------|
| **Monitor name** | EU Radio Equipment Directive |
| **Source URL** | https://single-market-economy.ec.europa.eu/sectors/ict/radio-equipment-directive_en |
| **Category** | Product Compliance |
| **Keywords** | RED, radio equipment, cybersecurity, CE marking, EMC, wireless, display |
| **Crawl frequency** | Weekly |
| **Crawl mode** | Smart (depth 1, max 8 pages) |
| **Expected output** | RED guidance and delegated act references; impact on RF and cybersecurity modules |

#### Energy Efficiency Regulations *(existing partial — refine)*

| Field | Value |
|-------|-------|
| **Monitor name** | EU Electrical and Electronic Products |
| **Source URL** | https://single-market-economy.ec.europa.eu/sectors/electrical-and-electronic-engineering-industries_en |
| **Category** | Product Compliance |
| **Keywords** | energy efficiency, ecodesign, standby, off-mode, display, electronic products, repair |
| **Crawl frequency** | Weekly |
| **Crawl mode** | Single page |
| **Expected output** | Ecodesign and energy labelling updates affecting TV power consumption |

### Industry Standards

#### DVB

| Field | Value |
|-------|-------|
| **Monitor name** | DVB Project |
| **Source URL** | https://dvb.org/ |
| **Category** | Industry Standard |
| **Keywords** | DVB, broadcast, receiver, specification, CI, satellite, terrestrial |
| **Crawl frequency** | Weekly |
| **Crawl mode** | Smart (depth 1, max 5 pages) |
| **Expected output** | New or revised DVB specifications; LOW/MEDIUM impact on broadcast stack modules |

#### HbbTV

| Field | Value |
|-------|-------|
| **Monitor name** | HbbTV Association |
| **Source URL** | https://www.hbbtv.org/ |
| **Category** | Industry Standard |
| **Keywords** | HbbTV, hybrid broadcast, broadband TV, application, specification, test suite |
| **Crawl frequency** | Weekly |
| **Crawl mode** | Smart (depth 1, max 5 pages) |
| **Expected output** | HbbTV spec and profile updates; impact on Browser/HbbTV module |

#### CI Plus

| Field | Value |
|-------|-------|
| **Monitor name** | CI Plus LLP |
| **Source URL** | https://www.ci-plus.com/ |
| **Category** | Industry Standard |
| **Keywords** | CI Plus, common interface, conditional access, content protection, CAM |
| **Crawl frequency** | Weekly |
| **Crawl mode** | Single page |
| **Expected output** | CI+ specification announcements; impact on CI/conditional access integration |

### Germany

#### BMUKN — Environment & Energy *(existing — enable)*

| Field | Value |
|-------|-------|
| **Monitor name** | BMUKN (Federal Ministry) |
| **Source URL** | https://www.bundesumweltministerium.de/en |
| **Category** | National Policy (Germany) |
| **Keywords** | Germany, energy efficiency, electronic products, repair, environment |
| **Crawl frequency** | Weekly |
| **Expected output** | National policy signals affecting energy and product regulations |

#### Bundesnetzagentur (BNetzA) *(add Week 1)*

| Field | Value |
|-------|-------|
| **Monitor name** | Bundesnetzagentur |
| **Source URL** | https://www.bundesnetzagentur.de/en |
| **Category** | National Regulation (Germany) |
| **Keywords** | Germany, market surveillance, radio, telecommunications, compliance, RED |
| **Crawl frequency** | Weekly |
| **Crawl mode** | Single page |
| **Expected output** | Market surveillance and telecom/radio enforcement updates for Germany |

### Supporting Monitors *(optional — keep enabled)*

| Monitor | Purpose |
|---------|---------|
| European Commission | Broad EU digital policy signal |
| European Union Portal | Cross-cutting EU law and policy |

### Pilot Monitor Summary

| Category | Count | Daily | Weekly |
|----------|-------|-------|--------|
| EU regulation | 4 | 2 | 2 |
| Industry standard | 3 | 0 | 3 |
| Germany | 2 | 0 | 2 |
| Supporting (optional) | 2 | 2 | 0 |
| **Total (full pilot set)** | **11** | **4** | **7** |

---

## 5. Success Metrics

KPIs are measured weekly and summarized in the Week 5 analysis report.

### Technical KPIs

| KPI | Definition | Target (6-week pilot) | Measurement source |
|-----|------------|----------------------|-------------------|
| **Crawl success rate** | Successful crawls ÷ total crawl attempts per monitor | ≥ 90% | Pipeline run history, `logs/app.log` |
| **AI analysis completion rate** | Changes with completed analysis ÷ total detected changes | ≥ 95% | `data/run_history.json`, Changes page |
| **AI analysis accuracy** | User-rated correct impact level ÷ rated items | ≥ 75% | Wednesday feedback form |
| **False positive rate** | Changes marked "not relevant" ÷ total changes reviewed | ≤ 25% | Monday review log |
| **Report delivery success** | Weekly reports generated on schedule | 100% (6/6 weeks) | `data/reports/`, scheduler status |
| **Platform uptime** | Dashboard health check passing | ≥ 99% during business hours | `GET /health`, Docker healthcheck |

### Business KPIs

| KPI | Definition | Target (6-week pilot) | Measurement source |
|-----|------------|----------------------|-------------------|
| **Time saved per week** | Self-reported manual tracking hours before minus after | ≥ 30% reduction (pilot average) | Week 1 vs Week 4 survey |
| **User satisfaction** | "Satisfied" or "Very satisfied" with platform | ≥ 70% of participants | Week 4 survey |
| **Action usefulness** | Recommended actions rated useful or very useful | ≥ 65% of rated changes | Wednesday feedback form |
| **Weekly active usage** | Participants logging ≥ 1 dashboard visit per week | ≥ 80% of enrolled users | Access log or self-report |
| **Knowledge base usage** | ≥ 1 knowledge search per user per week (Weeks 2–4) | ≥ 50% of participants | Self-report + search audit |
| **Report consumption** | Weekly report opened or emailed to stakeholders | 6/6 weeks | Email logs, self-report |

### Qualitative Success Criteria

- At least **3 concrete engineering actions** traced to platform-detected changes during the pilot
- Zero **missed HIGH-impact changes** that were later found manually (target; document any exceptions)
- Documented **v1.1 priority list** with ≥ 10 ranked items from participant feedback

---

## 6. Feedback Process

Structured feedback ensures pilot learnings feed directly into [roadmap-v1.1.md](roadmap-v1.1.md).

### Weekly Cadence

#### Monday — Review Generated Changes (30 minutes)

| Activity | Owner | Output |
|----------|-------|--------|
| Open Dashboard and Changes page after weekend/Monday 08:00 run | Compliance Engineer | Annotated change list |
| Triage HIGH and MEDIUM items | Compliance + AI Feature Owner | Priority queue for engineering |
| Mark false positives and missed context | All roles (async) | Entries in feedback log |
| Distribute weekly report when generated (Monday 08:30) | Compliance Engineer | Email or Teams message to pilot group |

**Monday checklist:**
- [ ] Review all new changes since last Monday
- [ ] Validate AI impact level for HIGH/MEDIUM items
- [ ] Log false positives in feedback form
- [ ] Share weekly report link with pilot team

#### Wednesday — Engineering Feedback (30 minutes)

| Activity | Owner | Output |
|----------|-------|--------|
| Firmware, software, and AI owners review assigned changes | Engineering participants | Impact accuracy ratings |
| Rate recommended actions (useful / not useful) | Engineering participants | Action usefulness data |
| Raise crawl or keyword gaps | Any participant | Monitor tuning requests |
| Optional: live 15-min sync call | Compliance Engineer | Recorded notes |

**Wednesday checklist:**
- [ ] Each engineering role reviews ≥ 1 change (or confirms "no relevant changes")
- [ ] Complete short feedback form (see below)
- [ ] File issues for incorrect AI analysis or broken crawls

#### Friday — Feedback Summary (20 minutes)

| Activity | Owner | Output |
|----------|-------|--------|
| Compile week's feedback | Compliance Engineer | Weekly pilot summary (1 page) |
| Update issue tracker | Compliance Engineer | Open/closed issue counts |
| Share summary with pilot team and management | Compliance Engineer | Email or shared doc |
| Tag items for v1.1 backlog | Compliance Engineer | Categorized feature requests |

**Friday summary template:**
1. Changes detected this week (count by impact)
2. False positives and accuracy notes
3. Time saved estimates (anecdotal or survey)
4. Open issues and monitor tuning actions
5. Feature requests captured

### Feedback Form (Weekly — Wednesday)

Use internal form or shared spreadsheet with these fields:

| Field | Type | Required |
|-------|------|----------|
| Participant name / role | Text | Yes |
| Week number | Number | Yes |
| Changes reviewed (count) | Number | Yes |
| AI impact accuracy (1–5) | Rating | Yes |
| Action usefulness (1–5) | Rating | Yes |
| False positives (describe) | Text | If any |
| Missed regulations (describe) | Text | If any |
| Time saved this week (hours) | Number | Optional |
| Feature requests | Text | Optional |
| Overall satisfaction (1–5) | Rating | Yes |

### Issue Tracking

| Issue type | Label | Example | Resolution owner |
|------------|-------|---------|------------------|
| Crawl failure | `pilot-crawl` | CRA monitor returned empty page | Platform / DevOps |
| Incorrect AI analysis | `pilot-ai` | LOW should be MEDIUM for OTA item | Compliance + platform |
| Monitor gap | `pilot-coverage` | Missing ETSI cybersecurity reference | Compliance Engineer |
| UI/UX problem | `pilot-ux` | Diff hard to read on mobile | Platform backlog (v1.1) |
| Feature request | `pilot-feature` | Teams notification for HIGH items | v1.1 backlog |

**Tracking tool:** Internal issue tracker, shared spreadsheet, or git issues in project repository — assign one channel in Week 1.

### Feature Request Handling

1. All requests logged with `pilot-feature` tag  
2. Compliance lead categorizes: `v1.1-candidate`, `v2.0-deferred`, `wont-fix`, `pilot-workaround`  
3. Week 6 prioritization workshop maps `v1.1-candidate` items to [roadmap-v1.1.md](roadmap-v1.1.md) priority matrix  

---

## 7. Six Week Timeline

### Week 1 — Setup and Onboarding

| Day | Activity |
|-----|----------|
| Mon | Deploy Docker environment; verify `/health`; assign pilot owner |
| Tue | Configure pilot monitors (Section 4); validate API keys |
| Wed | Pilot kickoff meeting (60 min): demo script walkthrough, role assignments |
| Thu | Run `python main.py run-once`; verify Changes and Knowledge pages |
| Fri | Baseline survey: manual tracking hours, expectations; confirm feedback channels |

**Deliverables:** Running environment, 11 monitors configured, participant roster, baseline survey results

---

### Weeks 2–3 — Daily Usage

| Activity | Frequency |
|----------|-----------|
| Scheduled daily/weekly crawls via `python main.py scheduler` or Docker scheduler | Automatic |
| Monday change review | Weekly |
| Wednesday engineering feedback | Weekly |
| Friday summary | Weekly |
| Monitor tuning based on false positives | As needed |

**Focus areas:**
- **Week 2:** EU AI Act, CRA, RED monitors — validate AI module mapping  
- **Week 3:** Industry monitors (DVB, HbbTV, CI+) — validate noise level and relevance  

**Deliverables:** 2 weekly summary reports, issue log with ≥ 5 entries, crawl success baseline

---

### Week 4 — Feedback Collection

| Activity | Detail |
|----------|--------|
| Mid-pilot survey | Full 15-question survey (all participants) |
| Structured interviews | 30-min session with 2–3 engineering leads |
| Demo retrospective | Optional replay of `python main.py demo` for comparison |
| Monitor audit | Confirm all 11 monitors ran successfully in Weeks 2–4 |

**Deliverables:** Survey results (≥ 70% response), interview notes, updated KPI dashboard

---

### Week 5 — Analysis

| Activity | Detail |
|----------|--------|
| Compile technical KPIs | Crawl rate, analysis accuracy, false positive rate |
| Compile business KPIs | Time saved, satisfaction, action usefulness |
| Root cause review | Top 5 false positives; top 3 AI inaccuracies |
| Draft pilot outcome report | 3–5 pages for engineering management |

**Deliverables:** Pilot metrics report, issue trend analysis, draft management summary

---

### Week 6 — v1.1 Prioritization

| Activity | Detail |
|----------|--------|
| Prioritization workshop (90 min) | Compliance lead + PM + 2 engineering reps |
| Map feedback to v1.1 roadmap | Align with [roadmap-v1.1.md](roadmap-v1.1.md) |
| Go/no-go recommendation | Continue internal rollout vs extend pilot |
| Final pilot report | Share with Smart TV compliance engineering leadership |

**Deliverables:** v1.1 ranked backlog (≥ 10 items), pilot final report, rollout recommendation

---

## 8. Risks and Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Too many false alerts** | Medium | High — user fatigue, ignored dashboard | Start with weekly frequency for industry monitors; tune keywords Week 2; track false positive KPI; compliance lead filters Monday review |
| **Missing regulations** | Medium | High — compliance gap | Maintain manual spot-check parallel for Week 2 only; `pilot-coverage` issue tag; add monitors within 48h of gap report |
| **AI incorrect analysis** | Medium | High — wrong engineering priority | Human review required before action; Wednesday accuracy ratings; impact override requested for v1.1; document all disputes |
| **Low user adoption** | Medium | High — pilot fails to generate feedback | Executive sponsor email at kickoff; Monday report tied to existing compliance standup; 30-min not 60-min weekly commitment; show time-saved metrics in Week 3 |
| **API cost or rate limits** | Low | Medium | Crawl cache enabled; smart crawl page limits; monitor daily vs weekly mix |
| **Crawl failures on site redesign** | Medium | Medium | Monitor `logs/error.log`; fallback to single-page mode; alert in Friday summary |
| **SMTP / report email failure** | Low | Low | Reports still available in dashboard; check `email_status` on Reports page |
| **Single SQLite instance corruption** | Low | High | Daily manual backup of `data/` during pilot; document restore procedure Week 1 |
| **Participant turnover** | Low | Medium | Document roles in shared wiki; cross-train second compliance engineer |

### Escalation Path

| Severity | Example | Escalate to | Response time |
|----------|---------|-------------|---------------|
| P1 | Platform down > 4 hours | Platform / DevOps lead | Same day |
| P2 | Crawl failure for EU AI Act or CRA | Compliance + platform | 24 hours |
| P3 | Incorrect HIGH impact | Compliance Engineer review | Next Monday |
| P4 | Feature request | v1.1 backlog | Week 6 workshop |

---

## Appendix A — Pilot Environment Setup

```bash
# 1. Clone and configure
cp .env.example .env
# Set OPENAI_API_KEY, FIRECRAWL_API_KEY, SMTP_PASSWORD (optional)

# 2. Enable demo flag for training (optional)
# config/demo.json → "enabled": true

# 3. Docker deployment
docker compose build
docker compose up -d

# 4. Verify
curl http://localhost:8080/health
python main.py status

# 5. Initial run
python main.py run-once
```

## Appendix B — Key Documents

| Document | Purpose |
|----------|---------|
| [User Guide](user-guide.md) | Day-to-day platform usage |
| [Demo Script v1.0](demo-script-v1.0.md) | Kickoff walkthrough |
| [Demo Guide](demo-guide.md) | CLI demo mode |
| [Roadmap v1.1](roadmap-v1.1.md) | Post-pilot feature planning |
| [Configuration](configuration.md) | Environment variables |
| [Deployment](deployment.md) | Docker and operations |

## Appendix C — Pilot Roles RACI (Summary)

| Activity | Compliance | PM | Firmware | AI Owner | Software | Platform |
|----------|:---:|:---:|:---:|:---:|:---:|:---:|
| Monitor configuration | R | I | C | C | C | A |
| Monday review | R | I | I | C | I | — |
| Wednesday feedback | C | I | R | R | R | — |
| Friday summary | R | I | — | — | — | — |
| Issue resolution | A | — | C | C | C | R |
| v1.1 prioritization | R | R | C | C | C | C |

*R = Responsible, A = Accountable, C = Consulted, I = Informed*

---

*Document version: 1.0 — aligned with AI Regulation Monitor release v1.0.0*
