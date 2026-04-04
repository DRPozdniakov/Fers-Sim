# File Placement Rules

## Rule: Always Place Files in Semantically Correct Folders

**STRICT RULE: Ask user if unsure where a file belongs.**

---

## Directory Structure & Placement Rules

| Content Type | Correct Folder | Examples |
|--------------|----------------|----------|
| MCP/Neo4j/knowledge graph | `smart_core/` | server.py, config.json, guides |
| Investor documents | `docs_ver2/investor_package/` | PRD, BRD, Business Plan, Executive Summary |
| Phase budgets & plans | `docs_ver2/investor_package/phase_plans/` | PreSeed-Budget-Detail.md, Seed-Phase-Plan.md |
| Document graphs (HTML) | `docs_ver2/graph/` | Document-Graph.html, registry.json |
| Framework/meta docs | `docs_ver2/` | Roadmap_Docs.md, changelog.md |
| Engagement materials | `docs_ver2/engage_data/` | Early-Adopter-Side-Letter.md, LOI-Template.md |
| Market research data | `docs_ver2/market/` | Industry reports, competitor data |
| Funding applications | `funds/` | Grant applications, pitch submissions |
| Imported references | `import/` | External templates, competitor docs |
| Claude configuration | `.claude/` | Skills, rules, settings |

---

## Decision Tree

**Before creating ANY file:**

1. **Is it MCP/Neo4j/tooling code?** → `smart_core/`
2. **Is it for investors?** → `docs_ver2/investor_package/`
3. **Is it a phase plan/budget?** → `docs_ver2/investor_package/phase_plans/`
4. **Is it a document graph visualization?** → `docs_ver2/graph/`
5. **Is it engagement/sales material?** → `docs_ver2/engage_data/`
6. **Is it market research data?** → `docs_ver2/market/`
7. **Is it a grant application?** → `funds/`
8. **Is it an imported reference?** → `import/`
9. **If uncertain** → **ASK THE USER**

---

## Common Mistakes

❌ Putting Python/MCP code in `docs_ver2/` (use `smart_core/`)
❌ Putting investor docs in root (use `docs_ver2/investor_package/`)
❌ Putting phase plans in `docs_ver2/` (use `investor_package/phase_plans/`)
❌ Creating files in root when a semantic folder exists

---

## Examples

✅ **CORRECT:**
```
smart_core/Entity-Extraction-Guide.md (graph documentation)
docs_ver2/investor_package/PRD-001-Fers-Humanoid-Robot.md (investor doc)
docs_ver2/investor_package/phase_plans/Seed-Budget-Detail.md (phase plan)
docs_ver2/graph/Document-Graph.html (graph visualization)
```

❌ **WRONG:**
```
docs_ver2/server.py (MCP code in docs folder)
PRD-001.md (investor doc in root)
Seed-Budget.md (phase plan in wrong location)
```
