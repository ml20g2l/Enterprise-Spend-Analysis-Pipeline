# DEFRA public-spend findings

## Decision question

What should be addressed before the published DEFRA rows are used for supplier,
entity, or monthly-spend decisions? This report uses only the real public CSVs;
it does not use the fictional corporate scenario.

## Scope and method

- Population: all 13,830 published rows across the 12 controlled files.
- Transaction dates: 3 March 2025 to 27 February 2026.
- Time assignment: parsed `transaction_date`, not the month in the filename.
- Amount: net published GBP amount, including negative rows.
- Duplicate policy: all source rows remain in the primary total. A sensitivity
  total retaining only the first exact-row hash is shown separately; this is
  not treated as a confirmed economic-transaction total.

The published-row total is **£5,752.25m**. It is a sum of disclosed rows, not a
claim about audited expenditure or unique economic transactions.

## Findings

### 1. Supplier-label concentration is material but not yet decision-ready

There are 2,146 distinct published supplier labels. The top five labels account
for **38.68%** of net value and the top ten for **45.25%**. `ENVIRONMENT AGENCY`
alone accounts for **£1,618.57m (28.14%)**.

This is a concentration signal, not yet a supplier-risk conclusion. The leading
label may represent intra-group or public-body flows, and no supplier master has
been applied. A procurement view should first distinguish commercial vendors,
public bodies, grants, and internal/group counterparties.

| Published supplier label | Net GBP | Share |
|---|---:|---:|
| ENVIRONMENT AGENCY | £1,618.57m | 28.14% |
| NATURAL ENGLAND | £243.41m | 4.23% |
| SHARED SERVICES CONNECTED LTD | £155.78m | 2.71% |
| KIER INTERGRATED SERVICES LTD | £111.25m | 1.93% |
| BAM NUTTALL LTD | £96.18m | 1.67% |

### 2. Entity naming must be conformed before comparison

`EA` and `Environment Agency` appear as separate entity values and account for
**£909.72m (15.82%)** and **£755.30m (13.13%)** respectively. `DEFRA` accounts
for **£3,769.77m (65.54%)**.

The two Environment Agency labels are clear evidence of taxonomy fragmentation.
Entity-level charts built directly from the source labels would split one
organisation and understate its combined share. A governed mapping table should
preserve the original value while providing a conformed analytical label.

### 3. Exact-row repetition changes the total enough to disclose

The source contains **134 additional exact-row occurrences**. The published-row
total is £5,752.25m; keeping only the first row in each exact-record group gives
**£5,716.72m**, a difference of **£35.53m (0.62%)**.

Equality does not prove duplicate payment, so automatic deletion would be
unsafe. Any public analysis should show a duplicate sensitivity range or use a
reviewed disposition rather than silently selecting one total.

### 4. Monthly movement is descriptive, not causal

Using transaction date, October 2025 is the largest month at **£779.18m** and
January 2026 is the smallest at **£239.92m**. March 2025 has the most rows
(2,487), while August 2025 has the fewest (807).

One disclosed year cannot establish seasonality, and monthly totals may be
affected by reporting timing, high-value projects, credits, and repeated rows.
The pattern is suitable for follow-up drill-down, not a causal performance claim.

### 5. Missing references constrain compliance analysis

- 7,533 rows (**54.47%**) have a blank contract number.
- 123 rows have a blank transaction number.
- 44 negative rows total **-£4.51m**.
- 72 rows have a transaction month different from their source-file month.
- 258 rows carry at least one soft warning; zero rows fail the current hard
  quarantine rules.

A blank contract reference is not evidence of off-contract or maverick spend.
Contract compliance requires a contract master and relationship/date matching,
which the real public source does not provide.

## Recommendation

Before using the real data for procurement prioritisation:

1. create conformed entity and counterparty mappings while retaining source labels;
2. classify counterparty type before interpreting supplier concentration;
3. publish both source-row and reviewed-duplicate sensitivity totals;
4. use transaction date for time analysis and retain source month as lineage; and
5. avoid contract-compliance claims until an authoritative contract master is available.

These steps address the largest risks to interpretation. They do not require
changing the original CSVs.

## Reproduction and sources

Run `python -m src.analysis.defra_spend_analysis` from the repository root. The
script profiles the preserved files in a temporary directory and prints the
aggregates used here.

Sources: the 12 repository CSVs under `data/raw/defra/`, their controlled
[`source_inventory.csv`](source_inventory.csv), and the official DEFRA links
recorded in that inventory. Data-quality definitions are documented in
[`data_quality_report.md`](data_quality_report.md).
