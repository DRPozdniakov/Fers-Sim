# Roadmap Data Schema

## Three Sections

The roadmap HTML has three sections:
1. **Timeline visualization** — driven by JSON data (`{{ROADMAP_JSON}}`)
2. **Detailed Roadmap** — hand-crafted HTML cards (`{{DETAILED_ROADMAP_HTML}}`)
3. **Business Expenses** — hand-crafted HTML expense tables (`{{EXPENSES_HTML}}`)

## JSON Structure (Timeline)

```json
{
  "project": "PROJECT NAME",
  "subtitle": "Project tagline or description",
  "timeline": {
    "start": "YYYY-MM-DD",
    "end": "YYYY-MM-DD",
    "now": "YYYY-MM-DD"
  },
  "phases": [...],
  "tasks": [...],
  "milestones": [...]
}
```

## Fields

### Root Object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `project` | string | Yes | Project name (displayed in header) |
| `subtitle` | string | No | Tagline shown in footer |
| `timeline` | object | Yes | Timeline boundaries |
| `phases` | array | Yes | Project phases (color-coded sections) |
| `tasks` | array | Yes | Individual tasks on timeline |
| `milestones` | array | No | Key milestone markers |

### Timeline Object

| Field | Type | Format | Description |
|-------|------|--------|-------------|
| `start` | string | `YYYY-MM-DD` | Timeline start date |
| `end` | string | `YYYY-MM-DD` | Timeline end date |
| `now` | string | `YYYY-MM-DD` | Current date marker |

**Tip:** Keep the timeline to 24-30 months max. Put later phases in detailed cards only.

### Phase Object

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier (used in tasks) |
| `name` | string | Display name |
| `color` | string | Hex color code (e.g., `#e17055`) |

### Task Object

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `code` | string | 2-4 chars | Short code shown in circle |
| `name` | string | - | Task name (1-3 words) |
| `phase` | string | phase.id | Links to phase for coloring |
| `status` | string | `planned`, `in-progress`, `completed` | Task status |
| `start` | string | `YYYY-MM-DD` | Start date |
| `end` | string | `YYYY-MM-DD` | End date |
| `position` | string | `above`, `below` | Position relative to timeline |
| `tier` | number | `1`, `2`, `3` | Distance from timeline (1=closest, 3=farthest) |

### Milestone Object

| Field | Type | Description |
|-------|------|-------------|
| `code` | string | Short code (e.g., `M1`) |
| `name` | string | Milestone name |
| `date` | string | Date in `YYYY-MM-DD` format |
| `position` | string | `above` or `below` |
| `tier` | number | Distance from timeline (1, 2, or 3) |

## Tier System

Tasks and milestones use tiers to prevent overlaps:

| Tier | Distance from line | Connector height | Use for |
|------|-------------------|-----------------|---------|
| 1 | Closest (5px) | 220px | Primary/important tasks |
| 2 | Middle (85px) | 140px | Secondary tasks |
| 3 | Farthest (165px) | 60px | Supporting tasks |

**Rules:**
- Alternate `position` (above/below) AND vary `tier` to prevent overlaps
- Never place two tasks at the same position+tier if they overlap in time
- Use tier 1 for the most important tasks per phase

## Detailed Roadmap HTML

Replace `{{DETAILED_ROADMAP_HTML}}` with phase cards. Structure:

```html
<div class="detailed-roadmap">
    <h2 style="font-size: 1.1rem; font-weight: 600; color: #333; margin-bottom: 20px; text-transform: uppercase; letter-spacing: 1px;">Detailed Roadmap</h2>
    <div class="phase-grid">
        <!-- One phase-card per phase -->
        <div class="phase-card" style="border-left: 4px solid #COLOR;">
            <div class="phase-header" style="background: #COLOR20;">
                <span class="phase-marker" style="background: #COLOR;">&#9654;</span>
                <span class="phase-title">Phase Name</span>
                <span class="phase-timing">Q1 2026 &#8594; Q3 2026</span>
                <!-- OR for current phase: -->
                <span class="phase-status current">Current</span>
            </div>
            <div class="phase-content">
                <div class="workstream">
                    <div class="workstream-title">Workstream Name <span style="font-weight:400; color:#888;">~&#8364;50K</span></div>
                    <div class="task-tree">
                        <div class="tree-item">&#9500;&#9472;&#9472; Task name <span class="price">&#8364;10K</span> <span class="status-dot in-progress">&#9684;</span></div>
                        <div class="tree-item">&#9492;&#9472;&#9472; Last task <span class="status-dot planned">&#9675;</span></div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
```

**Status dot symbols:**
- Planned: `<span class="status-dot planned">&#9675;</span>` (empty circle)
- In Progress: `<span class="status-dot in-progress">&#9684;</span>` (half circle)
- Complete: `<span class="status-dot complete">&#9679;</span>` (filled circle)

**Tree connectors:**
- Middle item: `&#9500;&#9472;&#9472;` (├──)
- Last item: `&#9492;&#9472;&#9472;` (└──)

## Expenses HTML

Replace `{{EXPENSES_HTML}}` with expense cards. Structure:

```html
<div class="expenses-section">
    <h2 style="font-size: 1.1rem; font-weight: 600; color: #333; margin-bottom: 5px; text-transform: uppercase; letter-spacing: 1px;">Business Expenses by Phase</h2>
    <p style="font-size: 0.55rem; color: #666; margin-bottom: 15px;">Budget allocation per funding round</p>
    <div class="expenses-grid">
        <div class="expense-card" style="border-left-color: #COLOR;">
            <h4 style="color: #COLOR;">Phase Name (Duration)</h4>
            <table class="expense-table">
                <tr><td>Category</td><td>&#8364;Amount</td></tr>
                <tr class="expense-total"><td><strong>Total</strong></td><td>&#8364;Total</td></tr>
            </table>
            <p style="font-size: 0.45rem; color: #888; margin-top: 8px;">Note text</p>
        </div>
    </div>
</div>
```

## Visual Behavior

- **Bubbles**: Sized by task duration (`50 + (days/365) * 100` px), colored by phase, 35% opacity
- **Status indicators**:
  - `completed`: Green with checkmark
  - `in-progress`: Pulsing animation with orange border
  - `planned`: Phase-colored gradient
- **NOW marker**: Red vertical line at current date
- **Past overlay**: Gray gradient over completed timeline section
- **Tier positioning**: Tasks placed at different distances from timeline to prevent overlaps

## Tips

1. Keep timeline to 24-30 months — put later phases in detail cards only
2. Use all 3 tiers above AND below to fit ~15-20 tasks without overlap
3. Alternate `position` (above/below) AND vary `tier`
4. Use short codes (2-4 chars) for readability
5. Keep task names concise (1-3 words)
6. Use `&#8364;` for € symbol in HTML sections
7. Use `&#8594;` for → arrow in HTML sections
