---
name: frontend-design
description: Generate mobile-first HTML one-pagers, dashboards, and data pages. USE WHEN user says 'create HTML page', 'make one-pager', 'build dashboard', 'HTML report', or any visual HTML output. Ensures all output works on mobile phones without scrolling or zooming.
---

# Mobile-First HTML Generation

All HTML output MUST work on mobile phones without requiring zoom-out or horizontal scrolling. Most recipients open files on their phone — if it doesn't look right immediately, they delete it.

---

## Core Principle

**Phone-first, desktop-second.** Design for 375px viewport first. Desktop is the easy part.

---

## Two Strategies (Pick Based on Content)

### Strategy A: Responsive (for simple pages)
Use when: one-pagers, marketing pages, pages with 4-column or fewer tables.

```html
<meta name="viewport" content="width=device-width, initial-scale=1.0">
```

Add `@media (max-width: 768px)` CSS with:
- Grids stack to 1 column
- Tables auto-fit at `width: 100%`
- Font sizes scale down
- Cards get `overflow-x: auto` for any table that might overflow
- Container gets `overflow-x: hidden` to prevent page-level scroll

### Strategy B: Scaled Desktop (for data-heavy pages)
Use when: pages with wide tables (5+ columns), 12-quarter projections, complex grids that MUST be seen together.

```html
<meta name="viewport" content="width=1400, initial-scale=0.27, shrink-to-fit=yes">
```

This renders the full desktop layout and scales it to fit the phone screen. No mobile CSS needed. User pinch-zooms to read details.

**Calculate initial-scale:** `375 / viewport_width` (e.g., 375/1400 = 0.27)

---

## Mandatory Mobile CSS Checklist (Strategy A)

```css
@media (max-width: 768px) {
    /* 1. Body */
    body { padding: 8px; }

    /* 2. Prevent page-level overflow */
    .container { overflow-x: hidden; max-width: 100vw; }

    /* 3. Cards contain their overflow */
    .card { overflow-x: auto; max-width: 100%; }

    /* 4. Grids stack */
    .grid-2, .grid-3 { grid-template-columns: 1fr; }

    /* 5. Tables auto-fit (no forced min-width) */
    table { display: block; overflow-x: auto; -webkit-overflow-scrolling: touch; }
    thead, tbody { display: table; width: 100%; }

    /* 6. Flex layouts wrap */
    .flex-row { flex-wrap: wrap; }
    .flex-row > * { flex: 1 1 100%; }
}

@media (max-width: 480px) {
    .grid-2 { grid-template-columns: 1fr; }
}
```

---

## Common Mobile Failures & Fixes

| Failure | Root Cause | Fix |
|---------|-----------|-----|
| Page wider than screen, need to zoom out | Table with `white-space: nowrap` overflows card | Add `overflow-x: auto` to card container |
| Table columns cropped | `min-width` on `thead/tbody` too large | Use `width: 100%` instead, let content auto-size |
| Funnel/bar chart numbers clipped | Bar `overflow: hidden` + small width % | Add `min-width: 60px !important` on bar fills |
| Side-by-side cards overflow | `grid-template-columns: 1fr 1fr` at 375px | Stack to `1fr` in media query |
| Text too small after zoom-out | Used Strategy B but text was already small | Bump base `font-size` to 13-14px when using viewport width >1000 |
| Highlight stats row wraps badly | Fixed `flex` widths too wide | Use `flex: 1 1 33%; min-width: 33%` for 3-across |

---

## Testing Protocol

**ALWAYS test with Playwright before delivering:**

1. Start local server: `python -m http.server {port}`
2. Navigate: `browser_navigate` to localhost URL
3. Resize to mobile: `browser_resize` to 375x812 (iPhone)
4. Check page overflow with JS evaluate:
   ```js
   () => ({
     scrollWidth: document.documentElement.scrollWidth,
     viewport: window.innerWidth,
     overflows: document.documentElement.scrollWidth > window.innerWidth
   })
   ```
5. If overflows: find the culprit element:
   ```js
   () => {
     const results = [];
     document.querySelectorAll('*').forEach(el => {
       if (el.scrollWidth > 375) {
         results.push({
           el: el.tagName + '.' + el.className,
           scrollWidth: el.scrollWidth,
           overflow: el.scrollWidth - 375
         });
       }
     });
     return results.sort((a, b) => b.overflow - a.overflow).slice(0, 10);
   }
   ```
6. Screenshot problem sections with `browser_take_screenshot`
7. Fix and re-test until overflow = false AND all content visible

---

## Design System (Fers Standard)

Follow the design rules in `.claude/rules/html-design.md`:

- **Colors:** Black/gray/white dominant. Color only for highlights.
- **Fonts:** `'Segoe UI', Arial, sans-serif` or `'Open Sans'`
- **Cards:** `background: white; border: 2px solid #333; border-radius: 8px; padding: 25px;`
- **No shadows, no gradients, no decorative icons**
- **Big numbers:** `font-size: 64px; font-weight: bold; color: #333;`
- **Labels:** `font-size: 10-11px; text-transform: uppercase; letter-spacing: 1px; color: #999;`

---

## Decision Tree: Which Strategy?

```
Does the page have tables with 5+ columns?
├── YES → Does the user need to see all columns at once?
│   ├── YES → Strategy B (viewport=1400, scale down)
│   └── NO → Strategy A (responsive, tables scroll inside cards)
└── NO → Strategy A (responsive, everything fits)
```

---

## Quick Reference

**Simple page (one-pager, marketing, 3-4 col tables):**
```html
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<!-- + mobile CSS media queries -->
```

**Data-heavy page (financials, 12-quarter tables, dashboards):**
```html
<meta name="viewport" content="width=1400, initial-scale=0.27, shrink-to-fit=yes">
<!-- no mobile CSS needed, desktop layout scales to fit -->
```

**Always verify:** No horizontal scroll on page level. Tables either fit or scroll inside their container. Never clip content.
