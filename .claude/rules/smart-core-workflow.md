# Smart Core MCP Workflow Rules

## Rule 1: Always Ping Neo4j First

**BEFORE ANY MCP CALL:** Call `mcp__smart-core__ping` to check Neo4j status.

```
✅ CORRECT:
1. Call ping → returns {"status": "ok"}
2. Proceed with knowledge_call, load_project, etc.

❌ WRONG:
1. Directly call knowledge_call without ping
   → Will hang indefinitely if Neo4j is down
```

**Only need to ping once per session.** If it returned "ok" earlier, proceed without re-ping.

---

## Rule 2: Knowledge Call Before Editing

**BEFORE editing any document in docs_ver2/:**

1. Run `mcp__smart-core__knowledge_call` to find which entities/tags the document contains
2. Check DEPENDS_ON / RESULTS_FROM relationships to identify downstream docs

**🔴 NEVER do single-file fixes for entity/value changes.**

ANY change to a value (amount, valuation, timeline, spec) MUST be traced across ALL documents using `knowledge_call` BEFORE editing.

```
✅ CORRECT:
1. User: "Change Seed round to €1.2M"
2. Run knowledge_call("Seed round funding") → finds 8 documents
3. Edit all 8 documents in one pass
4. Update changelog.md
5. Run load_project

❌ WRONG:
1. User: "Change Seed round to €1.2M"
2. Edit only the file user mentioned
3. Skip knowledge_call
   → Other documents now have inconsistent data
```

---

## Rule 3: After Editing Documents

**MANDATORY sequence after editing any document in docs_ver2/:**

1. **Run `knowledge_call`** to find ALL documents containing the changed entity/value
2. **Edit ALL affected files** in one pass (not just the file the user mentioned)
3. **Update `docs_ver2/changelog.md`** — log every change with:
   - Date
   - File path
   - Old value → New value
   - Reason for change
4. Run `load_project` to re-ingest changed documents
5. Run `store_extraction` with updated entities
6. If entity VALUE changed, run `merge_report` for each affected entity
7. Update downstream documents flagged by merge_report

**The changelog update is MANDATORY and must happen IMMEDIATELY after edits, before any MCP calls.**

---

## Rule 4: Merge Approval Required

**Claude MUST get user approval for cross-document propagation.**

When entity values change across documents:

1. Run `synchronize_project` to detect changes
2. For each change, run `merge_report` to create a pending merge
3. **Ask user for approval using `AskUserQuestion`:**
   - Format: `"Entity: old_value → new_value. Approve?"`
   - Options: Approve / Reject
4. Only after user approves, run `approve_merge` for approved merge_id
5. Run `load_project` to sync graph

**NEVER auto-approve merges.** User controls all cross-document propagation.

Example approval question:
```
Question: "Equity: CTO 35%→30%, CFO/CEO→TBD. Approve?"
Options: [Approve] [Reject]
```

---

## Rule 5: Before Answering Questions

**Before answering questions about the project:**

1. **Ping Neo4j first** — if down, read files directly
2. If up: Use `knowledge_call` (hybrid search) instead of reading multiple files
3. Cross-reference graph entities for consistency
4. If two docs disagree on same entity → flag it to user

---

## Rule 6: Session Start Workflow

**At session start (when working on docs_ver2/):**

1. Call `mcp__smart-core__ping` to check Neo4j
2. If up: Run `knowledge_call` with relevant query to load context
3. If down: Read files directly, skip graph operations

---

## Rule 7: When MCP Tools Are Not Available

**🔴 CRITICAL: Smart Core is NOT optional. It is a core project tool.**

**🔴 NEVER silently fall back to grep. ALWAYS ask the user first.**

**If `mcp__smart-core__*` tools are not in the available/deferred tools list:**

1. **STOP and tell the user immediately:**
   ```
   "Smart Core MCP is not connected to this session.
   Neo4j status: [running/down].
   Options:
   1. Fix Smart Core now (reload VSCode window)
   2. Proceed without Smart Core (grep fallback)
   Which do you prefer?"
   ```

2. **Do NOT proceed with any document editing or audit until user responds.**

3. **Diagnose (quick check, <30 seconds):**
   - Neo4j running? `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:7474 --connect-timeout 3`
   - If Neo4j is UP but MCP tools missing → VSCode needs reload (most common case)
   - If Neo4j is DOWN → Start Neo4j service first

4. **Fix procedure (tell user exactly what to do):**
   ```
   "Neo4j is running. Smart Core MCP just needs VSCode to reconnect.
   Please: Ctrl+Shift+P → 'Developer: Reload Window'
   I'll wait and retry after reload."
   ```

5. **If user chooses to proceed without Smart Core:**
   - Use grep for ALL cross-document references
   - Still follow FULL workflow: find all refs → edit all → changelog
   - **Flag at end of session** that `load_project` and `store_extraction` must run next session
   - Add a warning banner to any generated reports: "⚠️ Generated without Smart Core — entity cross-referencing not available"

**NEVER silently launch agents or start work using grep when Smart Core should be available. The user must explicitly authorize the fallback.**

---

## Rule 8: Smart Core Is A Priority Tool

**Smart Core exists to prevent cross-document inconsistencies. Ignoring it defeats its purpose.**

- It is NOT a nice-to-have — it is the primary tool for document editing workflows
- EVERY session that touches docs_ver2/ should start with an MCP ping
- If MCP was unavailable in a previous session, the FIRST action in the next session is `load_project` to re-sync
- All rules in `.claude/rules/` reference Smart Core — they are not optional

---

## Rule 9: Path Format for MCP Tools

**Paths in Smart Core must match how `load_project` stored them.**

On Windows, `load_project` stores paths with **backslashes** (e.g., `docs_ver2\investor_package\PRD-001.md`). The `store_extraction` tool looks up documents by exact path match.

**Check `load_project` output to see the actual stored format, then use the same format.**

```
✅ CORRECT (match load_project output):
store_extraction("docs_ver2\\investor_package\\PRD-001.md", ...)

❌ WRONG (forward slashes don't match stored paths):
store_extraction("docs_ver2/investor_package/PRD-001.md", ...)
→ Returns "Document not found" because path doesn't match
```

**If `store_extraction` returns "Document not found":**
1. Check the exact path format from `load_project` output
2. Use that exact format (including slash direction)
3. If path was never loaded, run `load_project` first

**TODO for server improvement:** Normalize paths in the server so both slash formats work. Until then, match the stored format.

---

## Rule 10: Changelog Is Step 1, Not An Afterthought

**🔴 CRITICAL: Update changelog.md BEFORE running any MCP sync tools.**

The correct order after editing docs is:

```
1. Edit all affected files
2. Update docs_ver2/changelog.md  ← IMMEDIATELY, while changes are fresh
3. load_project                   ← re-ingest (including updated changelog)
4. store_extraction               ← update entities
5. merge_report / commit_changes  ← record in graph history
```

**Common failure mode:** Getting distracted by MCP troubleshooting and forgetting changelog entirely. The changelog is a human-readable audit trail — it must be updated even if MCP is broken.

**Changelog entry format:**
```markdown
## YYYY-MM-DD

### [Change Category]
- **What changed:** Old Value → New Value
- **Files updated:** list of files
- **Reason:** why the change was made
```

---

## Rule 11: When MCP Tools Error, Debug Before Retrying

**If an MCP tool returns an error, READ the error message before retrying.**

Common errors and fixes:

| Error | Root Cause | Fix |
|-------|-----------|-----|
| `Document not found: <path>` | Path format mismatch or load_project not run | Check path format (use `/`), run load_project first |
| `is not in the subpath of` | Root directory miscalculated | Check CONFIG_PATH parent chain in server.py |
| `Neo4j unavailable` | Neo4j not running | Start Neo4j service, check port 7687 |
| `embedding model not ready` | Server still loading | Wait 15-20s, re-ping |
| Tool hangs / no response | Neo4j down but not detected | Kill and restart MCP server |

**NEVER retry the same failing call without fixing the root cause.**

---

## Rule 12: load_project Cleans Stale Nodes

**`load_project` now automatically removes stale Document nodes** — documents that exist in the graph but not on disk.

This means:
- After `load_project`, the graph matches the filesystem exactly
- No need to manually clean up renamed/deleted documents
- The response includes `stale_nodes_removed` count

**If you see stale nodes persisting**, it means load_project hasn't been run since the files changed.

---

## Common Mistakes to Avoid

❌ Calling MCP tools without pinging first
❌ Editing one file without checking cross-document impacts
❌ Skipping changelog updates or doing them last
❌ Auto-approving merge requests
❌ Using file reads when knowledge_call would be better
❌ Forgetting to run load_project after edits
❌ **Silently falling back to grep without ASKING the user first**
❌ **Launching agents with grep fallback without user authorization**
❌ Treating Smart Core as optional or "nice-to-have"
❌ Proposing to "skip MCP for now" without exhausting fix options
❌ Using wrong slash format in store_extraction (check load_project output)
❌ Retrying failed MCP calls without reading the error message
❌ Getting distracted by MCP debugging and forgetting the changelog
❌ **Proceeding with audit/editing when MCP tools are missing from session**

---

## MCP Troubleshooting Guide

**Quick reference for when Smart Core MCP tools are unavailable.**

### Symptom → Diagnosis → Fix

| Symptom | Diagnosis | Fix |
|---------|-----------|-----|
| `mcp__smart-core__ping` → "No such tool" | MCP server not registered in VSCode session | **Reload VSCode window** (`Ctrl+Shift+P` → "Developer: Reload Window") |
| `mcp__smart-core__ping` → hangs | Neo4j down or MCP server process hung | Check Neo4j: `curl http://127.0.0.1:7474`. If down, start Neo4j Desktop. If up, kill hung Python process and reload VSCode |
| `ping` returns `{"status": "warming"}` | Embedding model still loading | Wait 15-20 seconds, retry ping |
| `store_extraction` → "Document not found" | Path format mismatch | Check `load_project` output for exact path format (backslash vs forward slash). Use same format |
| `load_project` → "is not in the subpath of" | Root directory miscalculated | Check `CONFIG_PATH.parent` chain in server.py. Should go up to project root (Fers/) |
| `load_project` → "docs directory not found" | `project_docs_path` in config.json is wrong | Check config.json `processing.project_docs_path`. Should be `"docs_ver2"` (relative) |
| Tools available but return errors | Config or database issue | Check `config.json` is valid JSON. Check Neo4j credentials match |

### Most Common Case: "Tools Not Available After Config Change"

**Root cause:** Editing `config.json` or `server.py` triggers MCP server restart. If the restart fails silently or VSCode doesn't re-register, tools disappear.

**Fix (10 seconds):**
1. `Ctrl+Shift+P` → "Developer: Reload Window"
2. Wait 15-20 seconds for embedding model to load
3. Try `mcp__smart-core__ping` again

### MCP Server Configuration Location

```
.mcp.json (project root)
├── command: Python 3.12 interpreter path
├── args: smart_core/app/smart-core-mcp/server.py
└── env: DB_URI, DB_USER, DB_PASSWORD, DB_NAME
```

### Emergency: Manual Server Test

If reload doesn't work, test the server manually:
```bash
cd "c:/Users/drpoz/OneDrive/Desktop/Fers"
DB_URI="bolt://127.0.0.1:7687" DB_USER="neo4j" DB_PASSWORD="65433456" DB_NAME="smart-core" \
  timeout 15 python smart_core/app/smart-core-mcp/server.py
```

If this fails, the error message will show the actual problem (missing dependency, config parse error, etc.).
