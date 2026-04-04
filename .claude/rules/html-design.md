# HTML Design Rules

## Rule: Follow Document-Graph.html Design System

**Reference:** `docs_ver2/graph/Document-Graph.html`

**Principle:** Clean, minimal, professional. Majority black/gray/white. Only use color sparingly for important highlights.

---

## Color Palette (Use These Exact Values)

### Core Colors
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

### Highlights (Use Sparingly!)
| Type | Background | Text | When to Use |
|------|------------|------|-------------|
| Success/Good | `#d4edda` | `#155724` | Positive status |
| Warning/Adapt | `#fff3cd` | `#856404` | Attention needed |
| Alert/Build | `#f8d7da` | `#721c24` | Action required |
| Coverage high | — | `#2a7d2a` | >70% coverage |
| Coverage medium | — | `#b8860b` | 40-70% coverage |
| Coverage low | — | `#666` | <40% coverage |

---

## Typography Rules

```css
body {
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 12px;
    background: #f0f0f0;
}

/* Big numbers (metrics, stats) */
.big-number {
    font-size: 64px;
    font-weight: bold;
    color: #333;
}

/* Headers */
h2, h3 {
    font-size: 22px;
    font-weight: 600;
    color: #333;
}

/* Labels */
.label {
    font-size: 10-11px;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #999;
}

/* Body text */
p, .body {
    font-size: 12px;
    line-height: 1.4;
    color: #666;
}
```

---

## Layout Rules

```css
/* Card containers */
.card {
    background: white;
    border: 2px solid #333;
    border-radius: 8px;
    padding: 25px;
    margin: 15px 0;
}

/* Grid layouts */
.grid {
    display: grid;
    gap: 20px;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
}
```

---

## Design Principles

### DO:
✅ Use flat colors (no gradients)
✅ Use borders for card separation (2px solid #333)
✅ Keep layouts grid-based and clean
✅ Use bars for visual data representation
✅ Use uppercase labels with letter-spacing
✅ Keep majority of design in grayscale
✅ Use color highlights only for critical information

### DON'T:
❌ NO decorative icons or symbols
❌ NO gradients
❌ NO shadows on cards (use borders instead)
❌ NO excessive color (keep it minimal)
❌ NO complex layouts (keep it simple)
❌ NO custom fonts (use system fonts)

---

## Example Structure

```html
<!DOCTYPE html>
<html>
<head>
    <style>
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            background: #f0f0f0;
            font-size: 12px;
            padding: 20px;
        }
        .card {
            background: white;
            border: 2px solid #333;
            border-radius: 8px;
            padding: 25px;
            margin: 15px 0;
        }
        .big-number {
            font-size: 64px;
            font-weight: bold;
            color: #333;
        }
        .label {
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #999;
        }
    </style>
</head>
<body>
    <div class="card">
        <div class="label">Total Funding</div>
        <div class="big-number">€1.0M</div>
    </div>
</body>
</html>
```

---

## When to Use Color Highlights

**Only for critical status/alerts:**
- 🟢 Success/Positive: `#d4edda` background
- 🟡 Warning/Caution: `#fff3cd` background
- 🔴 Alert/Action: `#f8d7da` background

**Example:**
```html
<div style="background:#d4edda; color:#155724; padding:10px; border-radius:4px;">
    ✓ Neo4j Connected
</div>
```
