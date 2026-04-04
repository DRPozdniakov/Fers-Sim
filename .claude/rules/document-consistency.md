# Document Consistency Rules

## Rule 1: Cross-Document Consistency is Mandatory

**Every figure, metric, timeline, and claim MUST align across all documents.**

**Special priority: Pitch Deck is single source of truth for investor-facing data.**

All supporting documents (PRD, BRD, Business Plan, Executive Summary, Financial Model) must match Pitch Deck exactly.

---

## Rule 2: Before Changing Any Number

**MANDATORY before changing any value:**

1. Run `mcp__smart-core__knowledge_call` to find ALL occurrences
2. List all affected documents
3. Edit ALL documents in one pass
4. Update changelog.md

**Common entities that appear in multiple documents:**
- Funding amounts (Seed €1M, Round A €7-10M, etc.)
- Valuations (pre-money, post-money)
- Team equity splits
- Product specifications (DOF, payload, price)
- Timeline milestones
- Market size (TAM/SAM/SOM)
- Customer metrics (payback period, ROI)

---

## Rule 3: Changelog Updates Are Mandatory

**After EVERY edit to docs_ver2/, update `docs_ver2/changelog.md`:**

Format:
```markdown
## YYYY-MM-DD

### [Document Name](path/to/document.md)
- **Section Name:** Old Value → New Value
- **Reason:** Why the change was made
- **Impact:** Which other documents were updated
```

**This is NOT optional.** Changelog tracks all changes for audit trail.

---

## Rule 4: Verify YAML Front Matter

**All documents in docs_ver2/ MUST have YAML front matter:**

Required fields:
```yaml
---
doc_id: "UNIQUE-ID"
title: "Document Title"
version: "X.Y"
last_updated: "YYYY-MM-DD"
status: "Draft|Active|Archive"
domain: "Business|Product|Technical|Finance"
phase: "PreSeed|Seed|RoundA|RoundB"
owner: "Role"
deputies: ["Role1", "Role2"]
tags_yaml: ["tag1", "tag2"]
depends_on: ["DOC-ID-1"]
feeds_into: ["DOC-ID-2"]
---
```

**When creating new documents, always include front matter.**

---

## Rule 5: Check Dependencies

**Before editing a document, check:**
- `depends_on` — what this doc relies on
- `feeds_into` — what docs depend on this

**Use `knowledge_call` to find actual graph relationships, not just YAML metadata.**

---

## Common Consistency Violations

❌ Changing Seed round in Financial Model but not Business Plan
❌ Updating team equity in one doc but not Executive Summary
❌ Changing product spec in PRD but not Pitch Deck
❌ Modifying timeline in Roadmap but not Phase Plans
❌ Editing any document without updating changelog
