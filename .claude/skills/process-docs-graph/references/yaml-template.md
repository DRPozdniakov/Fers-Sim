# YAML Front Matter Template

Copy this block to the top of every new document in `docs_ver2/`:

```yaml
---
doc_id: [PREFIX]-[NUMBER]
title: [Document Title]
version: "1.0"
created: [YYYY-MM-DD]
last_updated: [YYYY-MM-DD]
owner: Role-[CTO|CFO|CEO]
status: Draft
domain: [product|business|financial|fundraising|operations|market-research]
phase: [pre-seed|seed|round-a|round-b]
tags:
  - [tag1]
  - [tag2]
depends_on:
  - [doc_id of upstream dependency]
feeds_into:
  - [doc_id of downstream consumer]
---
```

## Prefix Reference

| Prefix | Type | Phase | Example |
|--------|------|-------|---------|
| FW | Framework | - | FW-001 |
| MR | Market Research | 1 | MR-001 |
| PRD | Product Requirements | 2 | PRD-001 |
| BRD | Business Requirements | 2 | BRD-001 |
| TS | Technical Specification | 2 | TS-001 |
| BP | Business Plan | 3 | BP-001 |
| BD | Business Development | 3 | BD-001 |
| IP | IP / Legal Strategy | 3 | IP-001 |
| JR | Jurisdiction Research | 3 | JR-001 |
| FM | Financial Model | 4 | FM-001 |
| ES | Executive Summary | 5 | ES-001 |
| PD | Pitch Deck | 5 | PD-001 |
| DV | Demo Video | 5 | DV-001 |
| RD | Roadmap | - | RD-001 |
