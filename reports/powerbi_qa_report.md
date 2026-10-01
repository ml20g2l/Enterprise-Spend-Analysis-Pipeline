# Power BI QA report

Status: **PASS within reviewed scope**  
Reviewed: **2026-10-01**

## Scope

The review combines PBIX package inspection, the exported three-page PDF, the
three README PNGs, and the reconciled MySQL/dbt controls. Package inspection
does not access or print credentials. Static exports cannot prove interactive
slicer, cross-highlight, drill, or refresh behaviour; those remain Power BI
Desktop checks.

## Structural QA

- PBIX package: valid
- Embedded data model: present
- Expected pages: 3/3
- PBIX canvas: 1280×720 on all pages
- Page containers: 35 / 45 / 35
- PDF pages: 3/3, unencrypted
- README images: 3/3, readable at full resolution
- Source layer: five dbt marts in MySQL
- Record origin: `synthetic_fictional_company`
- Visible `COMPLANCE` label: corrected to `COMPLIANCE`

The package checks can be reproduced with
`python -m src.analysis.inspect_powerbi` and the Power BI regression tests.

## Rendered visual review

### Page 1 — Executive Spend Overview

- Page title, reporting period, synthetic marker, slicers, and four KPI cards
  are visible and aligned.
- Monthly trend, currency mix, department allocation, and top-vendor visuals
  render without clipping or overlap.
- Displayed control values agree with the reconciled source: 5,000 expenses,
  £1.16bn rounded total, £232.19k average expense, and 73.20% compliance.
- Currency labels reconcile to approximately £753.15m GBP, £269.48m EUR, and
  £138.31m USD after GBP conversion.

### Page 2 — Contract & Vendor Performance

- Five KPI cards and all four analytical sections are visible and aligned.
- Displayed values agree with the controls: 73.20% compliance, £305.92m
  non-compliant spend, 26.35% non-compliant share, and £44.35m high-risk spend.
- Department/category labels, scatter legend, and watchlist columns are legible.
- The corrected `COMPLIANCE` card label is visible in the export.

### Page 3 — Approval & Operational Performance

- Five KPI cards, combo chart, priority matrix, department bars, and heatmap
  render without overlap.
- Displayed values agree with the controls: 5,000 requests, 60.99 approval
  hours, 111.09 request-to-payment hours, 1,919 breaches, and 38.38% breach rate.
- Heatmap percentages and month labels are legible at full resolution. GitHub
  readers may need to open the image for the smallest cell text.

## Interaction checks to retain as manual evidence

- Month, department, category, and risk slicers change only intended visuals.
- Resetting each page to `All` restores the control totals above.
- Navigation buttons open the correct pages.
- Vendor visuals marked `FULL PERIOD` do not imply unsupported monthly detail.
- Refresh prompts for local MySQL credentials without storing them in Git.

## Quantitative controls

- Expense count: 5,000
- Total spend: £1,160,936,638.63
- Contract compliance: 73.20%
- Non-compliant spend: £305,916,170.54
- Approval requests: 5,000
- SLA breaches: 1,919 (38.38%)
- Average approval cycle: 60.99 hours
- Average request to payment: 111.09 hours

All figures describe the fictional corporate scenario, not DEFRA operations.
