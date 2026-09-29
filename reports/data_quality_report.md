# DEFRA data-quality report

## Scope and grain

The source grain is one row in one monthly DEFRA CSV. A row is preserved even when it is identical to another row. The profiling layer adds lineage and typed fields but does not assert that a source row is a unique economic transaction.

## Results

| Check | Result | Rate | Interpretation |
|---|---:|---:|---|
| Source files | 12 | — | Expected March 2025 to February 2026 set is complete. |
| Raw rows | 13,830 | 100.00% | Reconciles to the sum of source-file rows. |
| Parsed transaction dates | 13,830 | 100.00% | Invalid dates are quarantined. |
| Parsed amounts | 13,830 | 100.00% | Invalid amounts are quarantined. |
| In analysis period | 13,830 | 100.00% | Uses transaction date, not file month. |
| Date outside source month | 72 | 0.52% | Preserved as a warning; may reflect reporting timing. |
| Exact duplicate additional occurrences | 134 | 0.97% | Not deleted; requires source/business review. |
| Business duplicate candidate rows | 468 | 3.38% | Same entity + transaction number but non-identical content. |
| Cross-file business-candidate rows | 78 | 0.56% | Requires review for late reporting, correction, or repeated identifier use. |
| Missing transaction number | 123 | 0.89% | Confirms transaction number cannot be the raw primary key. |
| Non-positive amounts | 49 | 0.35% | Review as credits/adjustments; values remain valid numeric records. |
| Absolute amount below £25,000 | 38 | 0.27% | Review against publication rules; do not reject automatically. |
| Effectively missing contract number | 7,683 | 55.55% | Includes blanks and common sentinels; missingness is not evidence of maverick spend. |
| Quarantined rows | 0 | 0.00% | Excluded from a future spend fact until corrected. |

Actual transaction-date coverage is **2025-03-03 to 2026-02-27**. The configured analysis window is **2025-03-01 to 2026-02-28**.

Parsed amount distribution (GBP): minimum **£-467,177.21**, median **£83,928.07**, 99th percentile **£3,713,137.82**, and maximum **£200,000,000.00**. These are profile statistics, not acceptance thresholds.

The 134 additional exact occurrences are distributed as `{"Defra__25k_May_25.csv":127,"November_Over__25K_Transparency.csv":5,"Over__25K_Transparency_Jan_26.csv":2}`. No exact duplicate group crosses source files.

## File profile

| Source month | File | Rows | Columns | Transaction-date range | Outside file month | Quarantined |
|---|---|---:|---:|---|---:|---:|
| 2025-03 | `Over++_25K++Mar+2025-Rev.csv` | 2,467 | 15 | 2025-03-03 to 2025-03-31 | 0 | 0 |
| 2025-04 | `Over_25K_Transparency_report_April_25.csv` | 1,103 | 15 | 2025-03-05 to 2025-04-30 | 20 | 0 |
| 2025-05 | `Defra__25k_May_25.csv` | 1,057 | 15 | 2025-05-01 to 2025-05-30 | 0 | 0 |
| 2025-06 | `Defra_Over__25k_June_2025.csv` | 991 | 15 | 2025-05-13 to 2025-07-02 | 10 | 0 |
| 2025-07 | `Over__25K_Transparency_July.csv` | 1,063 | 15 | 2025-05-21 to 2025-07-31 | 4 | 0 |
| 2025-08 | `August_Over__25K_Transparency.csv` | 781 | 15 | 2025-07-10 to 2025-08-29 | 5 | 0 |
| 2025-09 | `September_Over__25K_Transparency.csv` | 1,169 | 15 | 2025-08-01 to 2025-09-30 | 31 | 0 |
| 2025-10 | `Defra_Over__25K_October_2025.csv` | 1,108 | 15 | 2025-10-01 to 2025-10-31 | 0 | 0 |
| 2025-11 | `November_Over__25K_Transparency.csv` | 953 | 15 | 2025-11-03 to 2025-12-03 | 1 | 0 |
| 2025-12 | `December_Over__25K.csv` | 1,118 | 16 | 2025-12-01 to 2025-12-31 | 0 | 0 |
| 2026-01 | `Over__25K_Transparency_Jan_26.csv` | 921 | 15 | 2026-01-02 to 2026-02-02 | 1 | 0 |
| 2026-02 | `Over__25K_Feb_26.csv` | 1,099 | 15 | 2026-02-02 to 2026-02-27 | 0 | 0 |

## Decisions

- Read source files as Windows-1252 and write generated CSV reports as UTF-8 with BOM.
- Map both `PO Category Description` and the source typo `PO Catergory Description` to one canonical field.
- Retain nullable `comments` for all months; months without the source column receive an empty value.
- Keep `source_month` and parsed `transaction_date` separately. A mismatch is a warning, not a rejection.
- Define an exact duplicate from all canonical source values. Report every occurrence and the additional-occurrence count; never auto-delete.
- Define a potential business duplicate as a repeated `(entity, transaction_number)` with non-identical source content. This is a review queue, not a duplicate verdict.
- Profile blanks separately from common sentinel values (`null`, `n/a`, `unknown`, `not set`, `none`). Preserve the source text while treating both as effectively missing for completeness measures.
- Quarantine only rows that cannot support the future fact grain because the transaction date or amount is missing/invalid. Missing descriptive identifiers remain warnings.
- Keep numeric non-positive amounts and values below £25,000 as review warnings. They may be credits, adjustments, or valid publication exceptions; no unverified range rule removes them.
- Treat all current rows as real public DEFRA GBP records. Future synthetic data must use a separate raw dataset and carry `record_origin`, `is_synthetic`, and its own source namespace.

## Analytical risks

- Summing raw rows without an explicit duplicate policy may overstate spend. The mart should include all source rows by default and expose duplicate flags for sensitivity analysis.
- Grouping by file month can shift activity into the wrong period. Calendar reporting should use `transaction_date`; operational ingestion monitoring can use `source_month`.
- `transaction_number` is a business identifier, not a proven globally unique primary key. Use the deterministic `source_record_id` for raw lineage and a surrogate key in marts.
- Repeated transaction numbers with differing fields may represent multi-line postings, corrections, or identifier reuse. They remain candidates until source/business evidence resolves them.
- Blank contract numbers do not establish maverick spend or non-compliance.

## Evidence files

- `source_inventory.csv`: source hashes, schema, row counts and date coverage.
- `duplicate_investigation.csv`: exact duplicate and business-candidate rows with lineage.
- `source_month_discrepancies.csv`: all source-month/date mismatches.
- `data_quality_summary.csv`: machine-readable check results.
- `column_profile.csv`: overall and per-file blank rates and cardinality.
- `data/quarantine/defra_rejected_rows.csv`: hard validation failures, if any.
