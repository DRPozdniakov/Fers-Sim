# Claude Code Rules for Fers Project

This directory contains enforceable rules that Claude Code applies to all work on the Fers project.

**Why rules?** CLAUDE.md is 1000+ lines and easy to miss critical patterns. Rules extract enforceable workflows into focused files that are always applied.

---

## Available Rules

| Rule File | Purpose | Priority |
|-----------|---------|----------|
| [`smart-core-workflow.md`](smart-core-workflow.md) | MCP/Neo4j workflow (ping first, knowledge_call before edits, merge approval) | 🔴 CRITICAL |
| [`entity-extraction.md`](entity-extraction.md) | **Complete entity extraction workflow (when, how, what, quality)** | 🔴 CRITICAL |
| [`entity-naming.md`](entity-naming.md) | Entity naming patterns quick reference (→ entity-extraction.md) | 🔴 CRITICAL |
| [`document-consistency.md`](document-consistency.md) | Cross-document consistency, changelog updates | 🔴 CRITICAL |
| [`mcp-best-practices.md`](mcp-best-practices.md) | MCP development standards (logging, security, tool descriptions) | 🔴 CRITICAL |
| [`file-placement.md`](file-placement.md) | Where to place files in the project structure | 🟡 IMPORTANT |
| [`html-design.md`](html-design.md) | HTML design system (colors, typography, layout) | 🟢 GUIDELINE |

---

## How Rules Work

**Claude Code automatically loads all `.md` files in `.claude/rules/` and enforces them during work.**

Rules override default behavior — they are MANDATORY unless explicitly overridden by user instructions.

---

## Rule Priority Levels

| Level | Meaning | Example |
|-------|---------|---------|
| 🔴 CRITICAL | MUST follow — violations break the system | Ping Neo4j before MCP calls |
| 🟡 IMPORTANT | SHOULD follow — violations create inconsistency | File placement, changelog updates |
| 🟢 GUIDELINE | Preferred patterns — violations are acceptable if justified | HTML color palette |

---

## When Rules Conflict with User Instructions

**User instructions always win.**

If a user explicitly asks Claude to skip a step (e.g., "don't update changelog for now"), Claude should follow the user's request but **warn about the consequences**.

Example:
```
User: "Change Seed round to €1.2M in Financial Model only"

Claude: "⚠️ Warning: This will create cross-document inconsistency.
Smart Core shows 8 other documents reference Round-Seed.
Recommend updating all documents now to maintain consistency.

Proceed with single-file edit only? [Yes] [No, update all]"
```

---

## Adding New Rules

**When to add a rule:**
- Pattern appears in 3+ places
- Violation breaks critical workflows
- Easy to forget or miss

**How to add a rule:**
1. Create new `.md` file in `.claude/rules/`
2. Use clear heading structure (## Rule 1, ## Rule 2)
3. Include examples (✅ CORRECT, ❌ WRONG)
4. Add to this README table

**Keep rules focused:** One rule file = one domain (workflow, naming, consistency, etc.)

---

## Relationship to CLAUDE.md

**CLAUDE.md** = Project context and knowledge
**`.claude/rules/`** = Enforceable patterns and workflows

**Think of it like:**
- CLAUDE.md = User manual (what the project is)
- Rules = Operating procedures (how to work on it)

**Overlap is OK:** Critical patterns can appear in both. Rules reinforce CLAUDE.md.

---

## Testing Rules

**To verify a rule is working:**
1. Ask Claude to perform an action that should trigger the rule
2. Check if Claude follows the rule without being reminded
3. Check if Claude warns when the rule might be violated

**Example test:**
```
User: "Update the Seed round to €1.2M"

Expected behavior (from smart-core-workflow.md):
1. Claude calls ping first
2. Claude calls knowledge_call to find all occurrences
3. Claude lists all affected documents
4. Claude updates all documents in one pass
5. Claude updates changelog.md
6. Claude runs load_project
```

---

## Future Rule Ideas

Potential rules to add as the project grows:

- **Pitch Deck Sync Rules** - enforce Pitch Deck as single source of truth
- **Testing Rules** - when to run tests, how to validate changes
- **Git Commit Rules** - commit message format, when to commit
- **Security Rules** - what NOT to include in docs (confidential info)
- **Review Rules** - when to ask user for review before proceeding

---

## Questions?

If Claude violates a rule or a rule needs updating, discuss with the project owner.

Rules are living documents — they should evolve as the project grows.
