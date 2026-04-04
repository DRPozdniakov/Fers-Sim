---
name: process-docs-graph
description: Update the document dependency graph. USE WHEN user says 'update graph', 'sync graph', 'document graph', 'update docs graph', 'process graph', or after creating/updating any document in docs_ver2/.
---

# Process Document Graph

Scan all documents in `docs_ver2/`, extract metadata from YAML front matter, update the dependency graph registry, enforce style consistency, and track version history.

---

## When to Use

- User says "update graph" or "sync graph"
- After creating or updating ANY document in `docs_ver2/`
- User says "show document status" or "what's the graph state"
- User wants to check document dependencies or consistency

---

## Output

**Type:** update
**Location:** `docs_ver2/graph/`
**Files produced/updated:**
- `docs_ver2/graph/registry.json` - Document registry with dependencies, versions, history
- `docs_ver2/graph/Document-Graph.html` - Regenerated D3 graph data from registry.json
- `docs_ver2/graph/docs_htmls/*.html` - All document HTML pages (with per-doc change history from changelog)
- Console output showing what changed

---

## Process

### Step 1: Scan Documents

1. Glob `docs_ver2/**/*.md` and `docs_ver2/**/*.html` (exclude `graph/` folder)
2. For each document, read YAML front matter
3. Extract: `doc_id`, `title`, `version`, `created`, `last_updated`, `status`, `domain`, `phase`, `owner`, `tags`, `depends_on`, `feeds_into`

### Step 2: Load Existing Registry

1. Read `docs_ver2/graph/registry.json`
2. If it doesn't exist, create from `references/registry-template.json`

### Step 2.5: Parse Changelog

1. Read `docs_ver2/changelog.md`
2. Parse into structured entries: split on `## YYYY-MM-DD` date headers, then `### Title` entries
3. Extract affected filenames from table rows (match `[\w-]+\.md` patterns)
4. Build a map: `{ "Financial-Model-Fers.md": [{ date, title, details[] }] }` for each doc
5. This data feeds into Step 5.5 (HTML generation) for per-doc "Recent Changes" sections

### Step 3: Update Registry

For each scanned document:
1. **New document** (doc_id not in registry): Add entry, log to `version_history`
2. **Updated document** (version or last_updated changed): Update entry, log to `version_history`
3. **Deleted document** (in registry but not on disk): Mark as `deleted`, log to `version_history`

### Step 4: Rebuild Dependency Graph

1. From all `depends_on` and `feeds_into` fields, rebuild `dependency_graph.edges`
2. Validate: warn if a document references a doc_id that doesn't exist yet (placeholder)
3. Assign documents to phases based on the fishbone order from the Framework (FW-001)

### Step 5: Consistency Check

Validate each document against the style guide (`references/style-guide.md`):
- [ ] Has YAML front matter with required fields
- [ ] doc_id matches prefix convention
- [ ] version is present and follows X.Y format
- [ ] last_updated is present and recent
- [ ] title in H1 matches front matter title
- [ ] Cross-references use doc_id format
- [ ] No style violations (emojis in body, missing tables, etc.)

Report violations as warnings (don't block the update).

### Step 5.5: Regenerate HTML Pages

1. Run `node docs_ver2/graph/build-html.js` from the project root
2. This script:
   - Reads `registry.json` and `changelog.md`
   - Regenerates all `docs_ver2/graph/docs_htmls/*.html` pages from markdown sources
   - Injects a "Recent Changes" section at the bottom of each doc page (max 10 entries from changelog)
   - Regenerates the `const data = { ... }` block in `Document-Graph.html` from registry.json
   - Adds orange highlight ring on graph nodes for docs changed within last 7 days
   - Updates stats (doc count, date) in Document-Graph.html
3. Verify output: script should report number of HTML files generated and changelog entries found

### Step 5.6: Check Off Changelog Pending Items

1. In `docs_ver2/changelog.md`, find all `- [ ] Regenerate HTML files in graph/docs_htmls/` entries
2. Replace with `- [x] Regenerate HTML files in graph/docs_htmls/`
3. This confirms HTML regeneration is complete for each changelog batch

### Step 6: Output Summary

Print to console:
```
Document Graph Updated | [DATE]
─────────────────────────────────
Total documents: X
  New: X | Updated: X | Unchanged: X | Deleted: X

Status breakdown:
  Draft: X | Review: X | Final: X

Phase coverage:
  Phase 1 (Research):     X/4 documents
  Phase 2 (Product):      X/3 documents
  Phase 3 (Business):     X/4 documents
  Phase 4 (Financial):    X/1 documents
  Phase 5 (Fundraising):  X/4 documents

Style warnings: X
  [list warnings if any]

Dependencies:
  [doc_id] → [doc_id] (status)
```

---

## Registry JSON Schema

```json
{
  "meta": {
    "project": "string",
    "last_updated": "YYYY-MM-DD",
    "total_documents": "number",
    "schema_version": "1.0"
  },
  "documents": [
    {
      "doc_id": "string",
      "title": "string",
      "path": "string (relative from project root)",
      "version": "string (X.Y)",
      "created": "YYYY-MM-DD",
      "last_updated": "YYYY-MM-DD",
      "status": "draft | review | final | deprecated | deleted",
      "domain": "string",
      "phase": "string",
      "owner": "string",
      "depends_on": ["doc_id array"],
      "feeds_into": ["doc_id array"],
      "tags": ["string array"],
      "entities": {}
    }
  ],
  "dependency_graph": {
    "phases": [
      { "id": "string", "name": "string", "order": "number", "documents": ["doc_id array"] }
    ],
    "edges": [
      { "from": "doc_id", "to": "doc_id", "type": "requires | informs" }
    ]
  },
  "version_history": [
    { "date": "YYYY-MM-DD", "action": "created | updated | deleted", "doc_id": "string", "version": "string", "note": "string" }
  ]
}
```

---

## Document ID Prefixes

| Prefix | Type | Phase |
|--------|------|-------|
| FW | Framework / Methodology | - |
| MR | Market Research | 1 |
| PRD | Product Requirements | 2 |
| BRD | Business Requirements | 2 |
| TS | Technical Specification | 2 |
| BP | Business Plan | 3 |
| BD | Business Development | 3 |
| IP | IP / Legal Strategy | 3 |
| JR | Jurisdiction Research | 3 |
| FM | Financial Model | 4 |
| ES | Executive Summary | 5 |
| PD | Pitch Deck | 5 |
| DV | Demo Video | 5 |
| RD | Roadmap | - |

---

## Fishbone Phase Order (from FW-001)

Documents MUST be created in this dependency order. The graph tracks readiness.

```
Phase 1: MR-001 (TAM/SAM/SOM) → MR-002 (Competitive) → MR-003 (Personas) → MR-004 (Tech Landscape)
Phase 2: PRD-001 → BRD-001 → TS-001
Phase 3: BP-001 → BD-001 → IP-001 → JR-001
Phase 4: FM-001
Phase 5: ES-001 → PD-001 → DV-001
```

A document is "ready to create" when ALL its `depends_on` documents have status `draft` or better.

---

## References

- `references/style-guide.md` - Document style conventions (MD + HTML)
- `references/registry-template.json` - Empty registry template
- `references/yaml-template.md` - YAML front matter template for new documents
