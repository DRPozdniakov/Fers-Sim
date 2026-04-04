---
name: create-project-roadmap
description: Create visual HTML timeline roadmaps for projects. USE WHEN user says 'create a roadmap', 'make a roadmap', 'generate roadmap', 'project timeline', 'visualize timeline', 'roadmap visualization', 'timeline chart', 'project milestones'.
---

# Create Project Roadmap

Generate visual HTML timeline roadmaps with three sections: bubble timeline, detailed phase cards, and expense tables.

---

## When to Use

- User says "create a roadmap"
- User says "make a project timeline"
- User says "visualize my project phases"
- User says "generate roadmap visualization"
- User wants timeline with tasks and milestones

---

## Output

**Type:** export
**Location:** Project root or user-specified location
**Files produced:**
- `ROADMAP_[PROJECT].html` - Interactive HTML visualization (3 sections)
- `ROADMAP_[PROJECT].json` - Project data (optional, for future updates)

---

## Process

### Step 1: Gather Project Information

Collect from user or parse from existing documents:
- **Project name** - displayed in header
- **Subtitle** - tagline for footer (optional)
- **Timeline range** - start date to end date (keep to 24-30 months max)
- **Current date** - for NOW marker (YYYY-MM-DD)

### Step 2: Define Phases (for timeline only)

Only include phases that fit within the timeline range. Put later phases in detailed cards only.

Each phase needs:
- `id` - unique identifier (used in tasks)
- `name` - display name
- `color` - hex color code

**Suggested color palette:**
- Orange: `#e17055`
- Green: `#00b894`
- Cyan: `#00cec9`
- Blue: `#0984e3`
- Purple: `#6c5ce7`
- Yellow: `#fdcb6e`
- Pink: `#e84393`
- Dark: `#2d3436`

### Step 3: Define Tasks with Tiers

Each task needs:
- `code` - 2-4 character code for bubble
- `name` - short task name (1-3 words)
- `phase` - phase id for coloring
- `status` - `planned`, `in-progress`, or `completed`
- `start` - start date (YYYY-MM-DD)
- `end` - end date (YYYY-MM-DD)
- `position` - `above` or `below` timeline
- `tier` - `1`, `2`, or `3` (distance from timeline line)

**Tier system (prevents overlaps):**

| Tier | Distance | Connector | Use for |
|------|----------|-----------|---------|
| 1 | Closest | 220px | Primary tasks |
| 2 | Middle | 140px | Secondary tasks |
| 3 | Farthest | 60px | Supporting tasks |

**Tips:**
- Use all 3 tiers above AND below to fit ~15-20 tasks
- Never place two tasks at the same position+tier if they overlap in time
- Keep names concise, bubbles are sized by duration automatically

### Step 4: Define Milestones (Optional)

Each milestone needs:
- `code` - short code (e.g., `M1`)
- `name` - milestone name
- `date` - target date (YYYY-MM-DD)
- `position` - `above` or `below`
- `tier` - `1`, `2`, or `3`

### Step 5: Consistency Validation (MANDATORY)

Before generating output, validate timeline data against source documents:

**5a. Phase dates must match across all documents:**
Read these files and verify phase timelines are consistent:
- `docs_ver2/investor_package/Full_Roadmap.md` (canonical phase dates)
- `docs_ver2/investor_package/Financial-Model-Fers.md` (funding rounds table)
- `docs_ver2/investor_package/Executive-Summary-Angels.md` (funding timeline)
- `docs_ver2/investor_package/Business-Plan-Fers.md` (section 11 phases)
- `docs_ver2/investor_package/phase_plans/*.md` (phase plan headers)
- `CLAUDE.md` (Funding Rounds line)

**5b. Validate task dates fit within their phase:**
- Every task's `start` and `end` must fall within its phase's date range
- Flag any task that extends beyond its phase (either fix the task or extend the phase)

**5c. Validate no phase gaps:**
- Phase N end date should be close to Phase N+1 start date (max 1 quarter gap)
- Flag gaps > 1 quarter as potential inconsistency

**5d. Cross-check milestones:**
- Milestone dates from Full_Roadmap.md must match the JS milestone data
- CE certification, Round closes, team expansions — all must align

**If any inconsistency is found:** Fix the source documents FIRST, then generate the roadmap. Never generate a roadmap with known inconsistencies.

### Step 6: Generate JSON Data

Structure the data following `references/schema.md`

### Step 7: Build Detailed Roadmap HTML

Create phase cards with workstreams and tree-style task breakdowns. Include ALL phases (even those beyond the timeline). See `references/schema.md` for HTML structure.

Key elements:
- `.phase-card` with colored left border
- `.workstream` groups with `.workstream-title`
- `.task-tree` with `.tree-item` entries using `├──` and `└──` connectors
- Status dots: `○` planned, `◔` in-progress, `●` complete
- Price tags with `.price` class

### Step 8: Build Expenses HTML

Create expense cards per phase with budget tables. See `references/schema.md` for HTML structure.

Key elements:
- `.expense-card` with colored left border
- `.expense-table` with category rows
- `.expense-total` row for totals
- Optional note paragraph

### Step 9: Create HTML File

1. Read `references/template.html`
2. Replace `{{ROADMAP_JSON}}` with the timeline JSON data
3. Replace `{{DETAILED_ROADMAP_HTML}}` with the detailed roadmap cards HTML
4. Replace `{{EXPENSES_HTML}}` with the expenses section HTML
5. Write to output location

---

## Three-Section Layout

### Section 1: Timeline Visualization (Top)
- Bubble timeline with phase-colored backgrounds
- Tier-based task positioning (3 levels above + 3 below)
- NOW marker, past overlay, month labels
- Status indicators (completed/in-progress/planned)
- Legend

### Section 2: Detailed Roadmap Cards (Middle)
- Grid of phase cards (responsive, min 340px per card)
- Each card has workstreams with tree-style task breakdowns
- Status dots per task
- Price/budget annotations
- Current phase gets red "CURRENT" badge

### Section 3: Business Expenses (Bottom)
- Grid of expense cards (responsive, min 280px per card)
- Budget tables with line items and totals
- Phase-colored left borders
- Optional notes per card

---

## Quality Criteria

What makes a GOOD roadmap:
- Timeline limited to 24-30 months (later phases in cards only)
- Tasks use all 3 tiers above/below to prevent overlaps
- Short codes (2-4 chars) are readable
- Detailed cards cover ALL phases including future ones
- Expense tables show budget breakdowns per phase

What makes a BAD roadmap:
- Timeline spans too many years (causes cramming)
- All tasks on same tier (causes overlaps)
- Missing detailed cards or expense tables
- Codes too long or cryptic
- Phase dates in HTML don't match source documents (inconsistency)
- Tasks extending beyond their phase without explanation
- Gaps between phases with no explanation (e.g., Round A ends Q1 but Round B starts 2029)

---

## References

- `references/template.html` - HTML template with 3 placeholders
- `references/schema.md` - Complete JSON schema + HTML structure docs
- `references/data-template.json` - Empty template to fill
- `references/example.json` - Complete example with tiers

---

## Quick Example

```json
{
  "project": "My Project",
  "timeline": { "start": "2026-01-01", "end": "2028-06-30", "now": "2026-03-15" },
  "phases": [
    { "id": "p1", "name": "Phase 1", "color": "#e17055" }
  ],
  "tasks": [
    { "code": "T1", "name": "Task One", "phase": "p1", "status": "completed", "start": "2026-01-01", "end": "2026-02-15", "position": "above", "tier": 1 }
  ],
  "milestones": [
    { "code": "M1", "name": "Launch", "date": "2026-06-01", "position": "above", "tier": 1 }
  ]
}
```
