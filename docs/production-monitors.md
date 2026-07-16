# Production Monitor Configuration — Smart TV Compliance Pilot

**Configuration file:** `config/monitors.json`  
**Version:** v1.0.0 pilot  
**Last updated:** July 2026  
**Monitors:** 8 enabled sources

This document describes the production-like monitor set for the internal Smart TV compliance pilot. All monitors use smart crawling with keyword-guided link discovery.

---

## Monitor Summary

| ID | Name | Category | Frequency | Crawl depth | Max pages |
|----|------|----------|-----------|-------------|-----------|
| `eu_ai_act` | EU AI Act | AI Regulation | Weekly | 2 | 10 |
| `eu_cra` | Cyber Resilience Act (CRA) | Cybersecurity Regulation | Weekly | 2 | 10 |
| `eu_red` | Radio Equipment Directive (RED) | Product Compliance | Weekly | 2 | 10 |
| `eu_energy_efficiency` | Energy Efficiency Regulation | Energy Regulation | Weekly | 2 | 10 |
| `hbbtv` | HbbTV | Broadcast Standard | Weekly | 1 | 5 |
| `dvb` | DVB | Broadcast Standard | Weekly | 1 | 5 |
| `ci_plus` | CI Plus | TV Interface Standard | Weekly | 1 | 5 |
| `de_bnetza` | Germany BNetzA | German Regulation | Weekly | 2 | 10 |

---

## Monitor Details

### EU AI Act

| Field | Value |
|-------|-------|
| **Source URL** | https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai |
| **Source purpose** | Official EU AI Act policy hub — regulatory framework, guidance, and implementation updates for artificial intelligence systems |
| **Keywords** | AI Act, Artificial Intelligence Act, high-risk AI system, cybersecurity, transparency |
| **Crawl strategy** | Smart crawl, depth 2, max 10 pages — follows linked guidance and FAQ pages within the EC digital strategy domain |
| **Expected regulation types** | AI Act amendments, delegated acts, guidance documents, compliance timelines, high-risk system classifications |
| **Update frequency** | Weekly (Monday pipeline run) |
| **Expected output** | Change diffs when policy pages update; AI impact on AI features, voice assistant, transparency obligations |

---

### Cyber Resilience Act (CRA)

| Field | Value |
|-------|-------|
| **Source URL** | https://digital-strategy.ec.europa.eu/en/policies/cyber-resilience-act |
| **Source purpose** | EU Cyber Resilience Act — product security requirements for connected hardware and software |
| **Keywords** | Cyber Resilience Act, CRA, vulnerability, security update, incident reporting |
| **Crawl strategy** | Smart crawl, depth 2, max 10 pages |
| **Expected regulation types** | CRA implementation guidance, vulnerability disclosure rules, security update obligations, incident reporting requirements |
| **Update frequency** | Weekly |
| **Expected output** | Security obligation changes; impact on OTA update, cybersecurity controls, network services |

---

### Radio Equipment Directive (RED)

| Field | Value |
|-------|-------|
| **Source URL** | https://single-market-economy.ec.europa.eu/sectors/ict/radio-equipment-directive_en |
| **Source purpose** | EU RED — radio equipment compliance including Article 3 essential requirements and cybersecurity provisions |
| **Keywords** | Radio Equipment Directive, RED, Article 3, cybersecurity |
| **Crawl strategy** | Smart crawl, depth 2, max 10 pages — follows linked harmonised standards and guidance |
| **Expected regulation types** | RED delegated acts, Article 3 cybersecurity requirements, harmonised standard references, CE marking updates |
| **Update frequency** | Weekly |
| **Expected output** | RF and cybersecurity compliance changes; impact on radio module, network services, cybersecurity controls |

---

### Energy Efficiency Regulation

| Field | Value |
|-------|-------|
| **Source URL** | https://single-market-economy.ec.europa.eu/single-market/goods/building-blocks/ecodesign_en |
| **Source purpose** | EU ecodesign and energy labelling framework for electronic products including displays |
| **Keywords** | energy label, ecodesign, standby power |
| **Crawl strategy** | Smart crawl, depth 2, max 10 pages |
| **Expected regulation types** | Ecodesign regulations, energy labelling classes, standby/off-mode power limits, repairability requirements |
| **Update frequency** | Weekly |
| **Expected output** | Power consumption rule changes; impact on standby power, energy label compliance, product documentation |

---

### HbbTV

| Field | Value |
|-------|-------|
| **Source URL** | https://www.hbbtv.org/ |
| **Source purpose** | HbbTV Association — hybrid broadcast-broadband TV specifications and releases |
| **Keywords** | HbbTV, HbbTV Association, specification, release |
| **Crawl strategy** | Smart crawl, depth 1, max 5 pages — specification and news sections only |
| **Expected regulation types** | HbbTV specification versions, test suite updates, profile releases, implementation guidelines |
| **Update frequency** | Weekly |
| **Expected output** | Standard version announcements; impact on Browser/HbbTV application layer |

---

### DVB

| Field | Value |
|-------|-------|
| **Source URL** | https://dvb.org/ |
| **Source purpose** | DVB Project — digital video broadcasting specifications including DVB-I |
| **Keywords** | DVB, DVB-I, DVB specification |
| **Crawl strategy** | Smart crawl, depth 1, max 5 pages |
| **Expected regulation types** | DVB specification updates, DVB-I service discovery, receiver interoperability requirements |
| **Update frequency** | Weekly |
| **Expected output** | Broadcast stack specification changes; impact on DVB receiver modules |

---

### CI Plus

| Field | Value |
|-------|-------|
| **Source URL** | https://www.ci-plus.com/ |
| **Source purpose** | CI Plus LLP — Common Interface Plus conditional access and content protection |
| **Keywords** | CI Plus, CI+ specification, security |
| **Crawl strategy** | Smart crawl, depth 1, max 5 pages |
| **Expected regulation types** | CI+ specification revisions, security updates, CAM compatibility requirements |
| **Update frequency** | Weekly |
| **Expected output** | CI/conditional access changes; impact on TV interface and content protection modules |

---

### Germany BNetzA

| Field | Value |
|-------|-------|
| **Source URL** | https://www.bundesnetzagentur.de/en |
| **Source purpose** | German Federal Network Agency — market surveillance, radio equipment, and product security for Germany |
| **Keywords** | Bundesnetzagentur, product security, radio equipment |
| **Crawl strategy** | Smart crawl, depth 2, max 10 pages |
| **Expected regulation types** | National enforcement guidance, market surveillance notices, radio equipment compliance updates |
| **Update frequency** | Weekly |
| **Expected output** | Germany-specific compliance signals; impact on market entry and radio product requirements |

---

## Crawl Strategy Reference

### Regulation websites (depth 2, max 10 pages)

Applied to: EU AI Act, CRA, RED, Energy Efficiency, BNetzA

```
Entry URL → linked guidance / FAQ / PDF pages (depth ≤ 2)
         → max 10 pages per run
         → crawl cache skips unchanged URLs
         → keyword ranking prioritises relevant links
```

### Standard body websites (depth 1, max 5 pages)

Applied to: HbbTV, DVB, CI Plus

```
Entry URL → specification / news sections (depth ≤ 1)
         → max 5 pages per run
         → lower depth limits reduce noise from marketing pages
```

---

## Validation Checklist

Use this checklist during pilot Week 1 setup and ongoing monitor health reviews.

### Source Format

| Monitor | Primary format | PDF regulations expected | Notes |
|---------|---------------|--------------------------|-------|
| EU AI Act | HTML | Yes — linked PDFs for acts and guidance | EC portal hosts HTML summaries with PDF downloads |
| CRA | HTML | Yes — regulation text and annexes as PDF | Check PDF handler processes linked documents |
| RED | HTML | Yes — delegated acts and standards lists often PDF | Article 3 cybersecurity docs may be PDF |
| Energy Efficiency | HTML | Yes — ecodesign regulations published as PDF | Standby power limits in regulation annexes |
| HbbTV | HTML | Possible — specification PDFs linked from site | Primary pages HTML; specs may be PDF downloads |
| DVB | HTML | Possible — specification documents as PDF | News HTML; spec downloads often PDF |
| CI Plus | HTML | Possible — CI+ spec PDFs for members/public | Entry page HTML; deep spec links may be PDF |
| BNetzA | HTML | Yes — German enforcement documents often PDF | English pages available; some PDF-only content |

### Expected AI Extraction Fields

When a change triggers analysis, the AI analyzer and regulation extractor populate:

| Field | Description |
|-------|-------------|
| `impact_level` | HIGH, MEDIUM, LOW, or NONE |
| `affected_modules` | Smart TV product modules (see below) |
| `reason` | Plain-language impact explanation |
| `recommended_actions` | Engineering and compliance next steps |
| `confidence` | Model confidence (HIGH, MEDIUM, LOW) |
| `regulation_extraction.title` | Regulation or update title |
| `regulation_extraction.summary` | Brief content summary |
| `regulation_extraction.category` | Regulation category |
| `regulation_extraction.regulation_type` | e.g. AMENDMENT, GUIDANCE, DIRECTIVE |
| `regulation_extraction.key_requirements` | Extracted obligation list |
| `regulation_extraction.actions_required` | Compliance actions |
| `evidence` | Source URLs and discovery path |

### Expected Compliance Modules

AI analysis maps changes to these Smart TV product modules:

| Module | Typical monitors |
|--------|-----------------|
| **AI features** | EU AI Act, CRA |
| **Voice assistant** | EU AI Act |
| **Browser / HbbTV** | HbbTV, DVB, EU AI Act (transparency) |
| **Cybersecurity controls** | CRA, RED, CI Plus |
| **OTA update** | CRA, RED |
| **Network services** | CRA, RED, BNetzA |
| **Remote control / voice input** | EU AI Act |
| **Radio / RF module** | RED, BNetzA, DVB |
| **Energy / standby power** | Energy Efficiency |
| **CI / conditional access** | CI Plus, DVB |

### Week 1 Validation Steps

- [ ] Run `python -m json.tool config/monitors.json` — valid JSON syntax
- [ ] Run `python main.py status` — 8 monitors loaded, 8 enabled
- [ ] Run `python main.py run-once` — crawl success for all 8 sources
- [ ] Check `logs/app.log` — no persistent crawl errors
- [ ] Verify at least one snapshot saved per monitor in `data/raw/`
- [ ] Review Changes page — confirm diffs appear on second run (baseline + delta)
- [ ] Validate AI analysis fields on one change detail page
- [ ] Confirm knowledge item created for analyzed change
- [ ] Review weekly report includes pilot monitor changes

### Ongoing Health Checks

| Check | Command / location | Expected |
|-------|-------------------|----------|
| Monitor config valid | `python -c "from app.source.source_loader import load_monitors; load_monitors()"` | No exception |
| Crawl success rate | `data/run_history.json` | ≥ 90% per week |
| Scheduler jobs | `python main.py scheduler` (or Docker scheduler) | Weekly runs for all monitors |
| Health API | `GET /health` | `database: ok`, `configuration: ok` |

---

## Related Documents

- [Pilot Plan v1.0](pilot-plan-v1.0.md)
- [User Guide](user-guide.md)
- [Configuration](configuration.md)
- [Deployment](deployment.md)

---

*Aligned with AI Regulation Monitor v1.0.0 — Smart TV compliance pilot*
