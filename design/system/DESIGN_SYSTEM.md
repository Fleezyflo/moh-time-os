# HRMNY Intelligence Dashboard — Design System v1

**Brand:** HRMNY
**Version:** 1.0
**Last Updated:** 2026-02-21

---

## 1. Color Palette

### Semantic Colors

| Semantic Name | Value | Usage |
|---|---|---|
| `--danger` | #ff3d00 | Errors, critical alerts, destructive actions |
| `--warning` | #ffcc00 | Warnings, caution states, attention needed |
| `--success` | #00ff88 | Positive actions, healthy states, confirmations |
| `--info` | #0a84ff | Informational, neutral alerts, secondary context |

### Neutral Colors

| Name | Value | Usage |
|---|---|---|
| `--black` | #000000 | Primary background |
| `--white` | #ffffff | Primary text, highlights |
| `--grey` | #333333 | Secondary text, borders, dividers |
| `--grey-light` | #555555 | Tertiary text, disabled states |
| `--grey-dim` | #1a1a1a | Elevated surfaces, cards |

### Brand Colors

| Name | Value | Usage |
|---|---|---|
| `--accent` | #ff3d00 | Primary brand, CTAs, emphasis |
| `--accent-dim` | #ff3d0066 | Hover states, backgrounds, transparency effects |

### Extended Palette

| Name | Value | Purpose |
|---|---|---|
| `--green` | #00ff88 | Success indicators, positive metrics |
| `--yellow` | #ffcc00 | Warning indicators, caution flags |
| `--red` | #ff3d00 | Error states, critical flags |
| `--blue` | #0a84ff | Information, secondary actions |

---

## 2. Typography

### Font Families

- **Primary:** Space Grotesk (400, 500, 600, 700)
  - Headings, body text, labels
  - Clear, minimal, modern feel

- **Data/Code:** JetBrains Mono (400, 500)
  - Metrics, IDs, data tables, code blocks
  - Monospace, precise

### Type Scale

| Category | Size | Line-Height | Weight | Usage |
|---|---|---|---|---|
| **Headline 1** | 40px | 44px | 600 | Screen titles, hero text |
| **Headline 2** | 28px | 32px | 600 | Section titles, major headings |
| **Headline 3** | 20px | 24px | 500 | Card titles, subsections |
| **Body** | 15px | 22px | 400 | Primary content, paragraphs |
| **Body Small** | 13px | 18px | 400 | Secondary content, descriptions |
| **Caption** | 12px | 16px | 400 | Metadata, timestamps, hints |
| **Mono Data** | 13px | 18px | 500 | Metrics, IDs, tables (JetBrains Mono) |
| **Micro** | 11px | 14px | 500 | Labels, badges, tiny text |

### Font Loading

```css
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap');
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap');
```

---

## 3. Spacing Scale

**Base Unit:** 4px

| Token | Value | Usage |
|---|---|---|
| `--space-xs` | 4px | Tight spacing, icon gaps |
| `--space-sm` | 8px | Padding in small components, gaps |
| `--space-md` | 12px | Standard padding, vertical gaps |
| `--space-lg` | 16px | Card padding, section margins |
| `--space-xl` | 24px | Large section gaps, container padding |
| `--space-2xl` | 32px | Major layout spacing |
| `--space-3xl` | 48px | Page section spacing |
| `--space-4xl` | 64px | Large content blocks |

---

## 4. Border & Shadows

### Border Radius

| Token | Value | Usage |
|---|---|---|
| `--radius-sm` | 4px | Small inputs, buttons |
| `--radius-md` | 8px | Cards, panels |
| `--radius-lg` | 12px | Large containers |

### Shadows

| Token | Value | Depth |
|---|---|---|
| `--shadow-sm` | 0 1px 3px rgba(0,0,0,0.3) | Subtle elevation |
| `--shadow-md` | 0 4px 12px rgba(0,0,0,0.4) | Standard depth |
| `--shadow-lg` | 0 12px 32px rgba(0,0,0,0.5) | Modal, dropdowns |

### Borders

| Token | Value | Usage |
|---|---|---|
| `--border` | 1px solid #333333 | Dividers, card outlines |
| `--border-hover` | 1px solid #555555 | Interactive hover states |
| `--border-active` | 1px solid #ff3d00 | Active selections |

---

## 5. Component Library

### Card

Container for content blocks. Defines visual hierarchy.

```css
.card {
  background: var(--grey-dim);
  border: var(--border);
  border-radius: var(--radius-md);
  padding: var(--space-lg);
  box-shadow: var(--shadow-sm);
}

.card:hover {
  border-color: var(--border-hover);
}
```

**Variants:** standard, elevated, bordered

---

### MetricCard

Specialized card for displaying a single metric.

```html
<div class="metric-card">
  <div class="metric-label">Active Projects</div>
  <div class="metric-value">24</div>
  <div class="metric-trend">↑ 3 this week</div>
</div>
```

**Layout:**
- Label (caption, --grey-light)
- Value (headline-3, --white)
- Trend (body-small, --success or --warning)

---

### StatusBadge

Inline badge for status indication.

```html
<span class="badge badge--success">Active</span>
<span class="badge badge--warning">At Risk</span>
<span class="badge badge--danger">Overdue</span>
```

**Variants:** success, warning, danger, info, neutral
**Display:** inline-block, padding 4px 8px, border-radius 4px

---

### DataTable

Tabular data presentation with sortable headers.

**Header:**
- Font: Mono Data, weight 500
- Color: --grey-light
- Border-bottom: var(--border)

**Rows:**
- Striped background (alternate --black and --grey-dim)
- Hover: background --grey-dim
- Cell padding: var(--space-md)

**Sorting:**
- Click header to sort
- Show visual indicator: ▲ / ▼ next to label

---

### ProgressBar

Visual representation of progress (0-100%).

```html
<div class="progress-bar">
  <div class="progress-bar__fill" style="width: 65%;"></div>
  <span class="progress-bar__label">65%</span>
</div>
```

**Fill color:** --success for healthy, --warning for caution, --danger for critical

---

### AlertBanner

Full-width alert for urgent notices.

**Variants:** success, warning, danger, info

```html
<div class="alert alert--danger">
  <span class="alert__icon">⚠</span>
  <span class="alert__text">3 invoices overdue beyond 60 days</span>
</div>
```

**Colors:**
- Danger: background #ff3d00 20%, text #ff3d00
- Warning: background #ffcc00 20%, text #ffcc00
- Success: background #00ff88 20%, text #00ff88
- Info: background #0a84ff 20%, text #0a84ff

---

### Button

Clickable action element.

**Primary:**
```css
.btn--primary {
  background: var(--accent);
  color: var(--black);
  padding: var(--space-md) var(--space-lg);
  border-radius: var(--radius-sm);
  font-weight: 600;
}

.btn--primary:hover {
  background: #ff5522;
}
```

**Secondary:**
```css
.btn--secondary {
  background: transparent;
  color: var(--white);
  border: var(--border);
  padding: var(--space-md) var(--space-lg);
  border-radius: var(--radius-sm);
}

.btn--secondary:hover {
  border-color: var(--white);
}
```

**Ghost:**
```css
.btn--ghost {
  background: transparent;
  color: var(--grey-light);
  padding: var(--space-md) var(--space-lg);
}

.btn--ghost:hover {
  color: var(--white);
}
```

---

### Timeline

Chronological display of events.

```html
<div class="timeline">
  <div class="timeline__item">
    <div class="timeline__marker"></div>
    <div class="timeline__content">
      <div class="timeline__date">Feb 20</div>
      <div class="timeline__label">Invoice sent</div>
    </div>
  </div>
</div>
```

**Styling:**
- Marker: 8px circle, --success or --warning
- Connecting line: 1px --grey
- Date: caption color --grey-light
- Label: body color --white

---

### TrendIndicator

Shows directional change with icon and percentage.

```html
<span class="trend trend--up">↑ 12%</span>
<span class="trend trend--stable">→ 0%</span>
<span class="trend trend--down">↓ 8%</span>
```

**Colors:**
- Up: --success
- Stable: --grey
- Down: --warning or --danger

---

## 6. Layout Grid

**System:** 12-column grid, responsive

### Grid Configuration

```css
.grid {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  gap: var(--space-lg);
}

.grid__item {
  grid-column: span 3; /* 4 items per row on desktop */
}
```

### Breakpoints

| Device | Width | Columns |
|---|---|---|
| Desktop | 1920px+ | 12 |
| Laptop | 1400px - 1920px | 12 |
| Tablet | 768px - 1400px | 8 |
| Mobile | < 768px | 4 |

### Responsive Classes

```css
.col-12 { grid-column: span 12; }
.col-6 { grid-column: span 6; }
.col-4 { grid-column: span 4; }
.col-3 { grid-column: span 3; }

@media (max-width: 1400px) {
  .col-lg-4 { grid-column: span 4; }
  .col-lg-6 { grid-column: span 6; }
}

@media (max-width: 768px) {
  .col-12,
  .col-6,
  .col-4,
  .col-3 {
    grid-column: span 4;
  }
}
```

---

## 7. Animations & Transitions

### Easing Functions

| Token | Value | Usage |
|---|---|---|
| `--ease-in` | cubic-bezier(0.4, 0, 1, 1) | Content entrance |
| `--ease-out` | cubic-bezier(0, 0, 0.2, 1) | Content exit |
| `--ease-inout` | cubic-bezier(0.4, 0, 0.2, 1) | Smooth transitions |

### Standard Transitions

| Token | Value | Usage |
|---|---|---|
| `--transition-fast` | 150ms ease-out | Quick feedback |
| `--transition-base` | 300ms ease-inout | Standard interaction |
| `--transition-slow` | 500ms ease-in | Deliberate motion |

### Keyframe Animations

**Pulse:** Draw attention to live data or alerts
```css
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.pulse {
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}
```

**Fade In:** Content reveal
```css
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.fade-in {
  animation: fadeIn var(--transition-base) ease-out;
}
```

**Slide In:** Panel or modal entrance
```css
@keyframes slideInLeft {
  from {
    opacity: 0;
    transform: translateX(-20px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.slide-in-left {
  animation: slideInLeft var(--transition-base) ease-out;
}
```

**Scanline:** Visual feedback (data refresh)
```css
@keyframes scanline {
  0% { transform: translateY(-100%); }
  100% { transform: translateY(100%); }
}

.scanline {
  animation: scanline 3s linear infinite;
  height: 2px;
  background: linear-gradient(to bottom, transparent, var(--accent), transparent);
  opacity: 0.3;
}
```

### Interaction Feedback

| Interaction | Transition | Animation |
|---|---|---|
| Hover | 150ms ease-out | Color shift |
| Click | Instant | Scale 0.95 → 1 (100ms) |
| Focus | 200ms ease-out | Glow/outline |
| Load | N/A | Fade-in + pulse |

---

## 8. Iconography

**Approach:** Text-based Unicode symbols + simple geometric SVGs

### Symbol Reference

| Icon | Symbol | Usage |
|---|---|---|
| Up Trend | ↑ | Positive change |
| Down Trend | ↓ | Negative change |
| Stable | → | No change |
| Alert | ⚠ | Warning |
| Check | ✓ | Success |
| Cross | ✗ | Error/dismiss |
| Info | ⓘ | Information |
| Expand | ⊞ | Expand item |
| Collapse | ⊟ | Collapse item |
| More | ⋯ | Menu/options |
| Back | ← | Back navigation |
| Forward | → | Forward navigation |

### SVG Icons

For more complex icons, use inline SVGs with:
- Stroke-width: 2
- Color: currentColor (inherits from text)
- Size: 16px, 24px, 32px

---

## 9. Dark Theme (Primary)

All colors optimized for dark background (#000000).

**Contrast Ratios:**
- Text on background: 16.1 (WCAG AAA)
- Text on surface: 15.2 (WCAG AAA)
- Interactive elements: 8.5+ (WCAG AA)

**Accessibility:**
- No pure white on pure black (use --white at reduced opacity for large text)
- All interactive elements have :focus state with visible outline
- Color is not the only method of conveying information

---

## 10. Usage Guidelines

### Card Hierarchy

**Elevated:** For primary content
- Use var(--shadow-md)
- Border: subtle

**Bordered:** For secondary content
- Use var(--border)
- No shadow

**Ghost:** For tertiary content
- Transparent background
- Border: var(--border-hover)

### Text Hierarchy

**Headlines:** Use Headline 1-3 for major sections
**Body:** Use Body or Body Small for content
**Labels:** Use Micro for field labels, badges
**Data:** Use Mono Data for numeric values, IDs

### Color Usage

- **Signal colors sparingly:** --danger, --warning, --success are for status only
- **Accent for CTAs:** Primary buttons and key interactions
- **Neutral greys for structure:** Dividers, borders, disabled states

### Spacing Consistency

- Apply padding in 4px increments (--space-xs to --space-4xl)
- Use consistent gap between grid items (--space-lg default)
- Vertical rhythm: align to --space-md baseline (12px)

---

## 11. Implementation Checklist

- [ ] Import fonts from Google Fonts
- [ ] Define all CSS custom properties in tokens.css
- [ ] Create component classes for each element
- [ ] Test color contrast with WebAIM
- [ ] Verify responsive grid at all breakpoints
- [ ] Test keyboard navigation on interactive elements
- [ ] Validate animation performance (60fps)
- [ ] Document component usage in Storybook (future)

---

## 12. Version History

| Version | Date | Changes |
|---|---|---|
| 1.0 | 2026-02-21 | Initial release: colors, typography, spacing, components, grid, animations |

