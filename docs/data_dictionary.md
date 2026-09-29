# Data dictionary

## Profiled DEFRA transaction

Grain: one physical data row in one monthly DEFRA CSV. Repeated rows remain separate records.

| Field | Type | Nullable | Meaning / rule |
|---|---|---:|---|
| `source_record_id` | char(64) | No | Deterministic SHA-256 of source file, 1-based source data-row number, and exact record hash. Raw primary key. |
| `source_file` | text | No | Original CSV filename. |
| `source_month` | char(7) | No | Reporting month derived from the controlled file manifest, `YYYY-MM`. |
| `source_row_number` | integer | No | 1-based row number after the header. Combined with the file for direct lineage. |
| `ingestion_timestamp` | timestamp with offset | No | Profiling run time. It is operational metadata, not part of record identity. |
| `record_origin` | text | No | `real_public_defra` for all current rows. |
| `is_synthetic` | boolean | No | `false` for all current rows. |
| `comments` | text | Yes | December source field; blank for months without this source column. |
| `department` | text | Yes | Source department label, preserved without business remapping. |
| `entity` | text | Yes | Source entity label. |
| `transaction_date_raw` | text | No in current data | Original date text. |
| `transaction_date` | date | Required for staging | Safely parsed ISO date. Supported source forms include `DD/MM/YYYY` and `DD-Mon-YY`. |
| `expense_type` | text | Yes | Source expense-type description. |
| `expense_area` | text | Yes | Source organisational or expense-area description. |
| `supplier` | text | Required with warning | Source supplier label. Missing values do not cause a hard rejection by themselves. |
| `transaction_number` | text | Yes | Original transaction identifier. Retained as text; not a primary key. |
| `amount_raw` | text | No in current data | Original amount representation, including symbols and separators. |
| `amount_gbp` | decimal(20,2) | Required for staging | Parsed numeric amount. Negative and zero values remain valid numeric records but are review warnings. |
| `currency_code` | char(3) | No | `GBP` for current DEFRA rows. |
| `po_category_description` | text | Yes | Canonical mapping of both `PO Category Description` and misspelled `PO Catergory Description`. |
| `supplier_postcode` | text | Yes | Source supplier postcode. |
| `supplier_type` | text | Yes | Source supplier-type label. |
| `contract_number` | text | Yes | Source contract reference. Blank does not mean non-compliant or maverick spend. |
| `project_code` | text | Yes | Source project code. |
| `expenditure_type` | text | Yes | Source expenditure classification. |
| `vat_registration_number` | text | Yes | Source VAT identifier, preserved as text. |
| `exact_record_hash` | char(64) | No | SHA-256 across all canonical source values, before typed derivations. Used only to group exact repeats. |
| `business_key` | char(64) | Yes | Hash of normalised `(entity, transaction_number)` when both exist. A duplicate-review key, not a uniqueness guarantee. |
| `date_parse_status` | enum | No | `valid`, `missing`, or `invalid`. |
| `amount_parse_status` | enum | No | `valid`, `missing`, or `invalid`. |
| `source_month_match` | enum | No | `true`, `false`, or `unknown`. A false value is a warning. |
| `quality_status` | enum | No | `valid`, `warning`, or `quarantine`. |
| `quality_issues` | text | Yes | Pipe-delimited machine-readable warning/rejection codes. |

## Duplicate classifications

| Classification | Definition | Automated action |
|---|---|---|
| Exact row duplicate | Two or more rows share every canonical source value, including comments. | Preserve every row; assign an investigation group. |
| Business duplicate candidate | Same normalised entity and transaction number but at least one canonical source value differs. | Preserve and review differing fields, source months, and source files. |
| Confirmed duplicate transaction | Requires external business/source evidence that one economic transaction was loaded more than once. | Not assigned in this phase. |

