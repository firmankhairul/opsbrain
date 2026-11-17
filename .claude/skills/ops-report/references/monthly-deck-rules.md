# Example MSP Deck Presentation Rules & Design System 2026

Source: [Example MSP Brand & Presentation Kit](https://example-msp/ics-kit-guideline) (Updated October 2026)
Reference templates:
- `monthly-report/template/ICS_Compute_Deck_Template.pptx`
- `monthly-report/template/ICS_Compute_Deck_Guide.pptx`

---

## 1. Five-Step Deck Production Workflow

```
[1. Brief] ──> [2. Content Map] ──> [3. Template Basis] ──> [4. Visual Rules] ──> [5. Review & Revise]
```

1. **Write the Brief:**
   Define target audience (executive, engineering, financial), required decision/outcome, key message, approved factual claims, language, and slide count.
2. **Map Content Before Layout:**
   Inventory messages, figures, evidence, and missing data. Group content into slides. Each slide must have one purpose, a direct informative title, and evidence.
3. **Use the Template as Basis:**
   Work from a copy of `ICS_Compute_Deck_Template.pptx`. Preserve 16:9 widescreen canvas (10 × 5.625 in / 960 × 540 px). Duplicate native layouts and keep shapes/text editable.
4. **Apply Example MSP Brand Visual Rules:**
   Apply Instrument Sans, approved palette, 56 px safe margin, and correct logo variants.
5. **Review & Revise:**
   Execute visual inspection against the verification checklist before sharing.

---

## 2. Template Layout Mapping

The compact template contains 8 core layouts:

| Layout Index | Name / Purpose | Key Elements & Usage |
|---|---|---|
| **Layout 1** | Dark Cover | Dark background, large title (36–40px), subtitle, **Secondary Red Logo (Wide)** top left. |
| **Layout 2** | Light / White Cover | Alternative white background cover with photo/graphic option. Secondary Red Logo top left. |
| **Layout 3** | Section Divider | Category / phase marker, high-contrast dark background. Primary Red Logo. No slide number. |
| **Layout 4** | Content & Narrative | Clean content area, up to 3 concise points or 1 photo/graphic. Primary Red Logo top right. |
| **Layout 5** | Comparison | Two-column balanced comparison (e.g. As-Is vs To-Be, Option A vs Option B). |
| **Layout 6** | Process Flow | 3–4 stage horizontal workflow. Keep native shapes, connectors, and text editable. |
| **Layout 7** | Use Case / Topology | Business narrative on left (40%), architecture topology / diagram on right (60%). |
| **Layout 8** | Thank You / Closing | Contact details, company URLs, **Primary Red Logo** top left. No slide number. |

---

## 3. Strict Visual & Brand Rules

### Typography
- **Typeface:** `Instrument Sans` exclusively for deck presentations.
  - Titles: Medium (500)
  - Body: Regular (400)
  - Emphasis: Semibold (600)
  - **Hard Constraint:** Semibold is the maximum weight. *Never use Bold (700+), ExtraBold, or synthetic bold.*
- **Size Scale (960 × 540 px canvas):**
  - Cover title: 36–40 px (27–30 pt)
  - Slide title: 24–28 px (18–21 pt), UPPERCASE
  - Subheading: 16–18 px (12–13.5 pt)
  - Body text: 12–14 px (9–10.5 pt) — *minimum 12 px*
  - Source/footer: 10–11 px (7.5–8.25 pt), Cool Grey

### Color Tokens
- **Bright Red (`#EC1C24`):** Main path, active state, emphasis in diagrams.
- **Dark Red (`#BC1823`):** Table headers, primary brand accent, major buttons.
- **True Black (`#000000`):** Slide backgrounds, high-contrast ink.
- **Cool Grey (`#5A5852`):** Muted body text, captions, secondary borders.
- **Paper (`#F3F0E9`):** Approved warm-light background.
- **True White (`#FFFFFF`):** High-contrast text on dark backgrounds.

### Logo & Numbering Rules
- **Secondary Red Logo (Wide):** Strictly on Slide 1 & 2 (Covers). Top left, minimum 100 px wide.
- **Primary Red Logo:** On every other slide (content, dividers, topology, closing). Minimum 50 px high.
- **Slide Numbers:** Two-digit format (`01`, `02`, `03`) at bottom right of content slides only. Exclude numbers from cover, divider, and closing slides.
- **Safe Margin:** Keep all text, tables, and diagrams at least `56 px` from slide canvas borders.

---

## 4. Review & Revision Checklist

Before distributing or finalizing any `.pptx` deck:
- [ ] Canvas is 16:9 widescreen (960 × 540 px / 10 × 5.625 inches).
- [ ] Safe margins of 56 px respected on all sides (no edge clipping).
- [ ] Instrument Sans used consistently; no synthetic bold or weights exceeding Semibold.
- [ ] Secondary red logo on covers only; Primary red logo everywhere else.
- [ ] Two-digit slide numbers on content slides only.
- [ ] All diagram shapes, connectors, and text boxes remain natively editable in PowerPoint (not rasterized screenshots).
- [ ] Table headers use `#BC1823` with white text; alternating rows contrast clearly.
- [ ] Factual claims, figures, units, and customer account details match source data exactly.
- [ ] Placeholders (e.g. `‹#›`, `TEAM DECK TEMPLATE`, sample citations) completely removed.
