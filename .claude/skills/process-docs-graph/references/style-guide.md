# Document Style Guide

**All documents in docs_ver2/ MUST follow these conventions.**

---

## Markdown Documents (.md)

### YAML Front Matter (Required)

Every `.md` document starts with:

```yaml
---
doc_id: [TYPE]-[NUMBER]
title: Document Title
version: "X.Y"
created: YYYY-MM-DD
last_updated: YYYY-MM-DD
owner: Role-[Title]
status: Draft | Review | Final | Deprecated
domain: product | business | financial | fundraising | operations | market-research
phase: pre-seed | seed | round-a | round-b
tags: []
depends_on: []
feeds_into: []
---
```

### Structure Conventions

1. **Title**: `# Document Title` (H1, single, matches front matter title)
2. **Metadata table** immediately after title:
   ```markdown
   | Field | Value |
   |-------|-------|
   | **Key** | Value |
   ```
3. **Sections**: Use `##` (H2) for main sections, `###` (H3) for subsections
4. **Tables**: Use markdown tables for structured data (not bullet lists)
5. **Cross-references**: Link to other docs by doc_id: `See [BP-001](path)`
6. **Footer**: End with `*Confidential | Fers | Month Year*`

### Writing Style

- Professional, factual, concise
- Quantify everything: numbers > adjectives
- Every claim needs a source or explicit assumption
- Use active voice
- No decorative emojis in body text (checkmarks in status tables are OK)

---

## HTML Documents

### Color Palette

| Element | Value | Usage |
|---------|-------|-------|
| Page background | `#f0f0f0` | Body |
| Card background | `white` | Main containers |
| Card border | `2px solid #333` | Card outlines |
| Primary text | `#333` | Headlines, numbers |
| Secondary text | `#666` | Body text |
| Muted text | `#999` | Labels, captions |
| Bar dark | `#4a4a4a` | Primary bars |
| Bar medium | `#888` | Secondary bars |
| Bar light | `#ccc` | Tertiary bars |

### Highlights (Sparingly)

| Type | Background | Text |
|------|-----------|------|
| Success/Good | `#d4edda` | `#155724` |
| Warning | `#fff3cd` | `#856404` |
| Alert | `#f8d7da` | `#721c24` |

### Typography

```css
body { font-family: 'Segoe UI', Arial, sans-serif; background: #f0f0f0; font-size: 12px; }
.card { background: white; border: 2px solid #333; border-radius: 8px; padding: 25px; }
```

- Big numbers: `64px bold #333`
- Headers: `22px 600-weight`
- Labels: `10-11px uppercase letter-spacing:1px`
- Body: `12px line-height:1.4`

### Rules

- NO decorative icons or symbols
- NO gradients (flat colors)
- NO shadows on cards (use borders)
- Grid-based layouts
- Bars for visual data representation

---

## Contributor Colors (Multi-author)

| Contributor | Color | HTML |
|-------------|-------|------|
| CTO | Dark Green | `<span style="color:#006400">` |
| CFO | Dark Blue | `<span style="color:#00008B">` |
| CEO | Dark Red | `<span style="color:#8B0000">` |
| Claude AI | Dark Orange | `<span style="color:#FF8C00">` |

---

## Version Numbering

- **Major** (1.0 → 2.0): Structural changes, new sections, significant rewrites
- **Minor** (1.0 → 1.1): Content updates, corrections, additions within existing structure
- Always update `last_updated` date on any change
- Graph registry must be updated on every version bump
