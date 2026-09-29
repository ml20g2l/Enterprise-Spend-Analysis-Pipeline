# Real and synthetic source integration

## Source contract

| Dataset | Reality status | Organisation represented | Intended use |
|---|---|---|---|
| DEFRA monthly spending CSVs | Real public records | DEFRA group entities represented in each file | Ingestion, public procurement spend, supplier concentration, and source-quality analysis. |
| Frankfurter FX rates | Real reference data | Not an expense source | Convert only fictional EUR/USD expenses to GBP using transaction-date rules. |
| Synthetic EUR/USD expenses | Synthetic | A clearly named fictional organisation | Multi-currency processing and testing. |
| Synthetic contracts | Synthetic | Same fictional organisation | Contract coverage and compliance simulation. |
| Synthetic approval events | Synthetic | Same fictional organisation | Approval cycle and SLA simulation. |

## Non-negotiable controls

- Every table that can contain synthetic records includes `source_dataset`, `record_origin`, `is_synthetic`, and `scenario_id` where applicable.
- DEFRA GBP values are never reassigned to fictional currencies.
- Synthetic contract records never match DEFRA contract-number text.
- Blank DEFRA contract numbers are reported as missing references, not maverick spend.
- Default dashboards and marts keep real and synthetic facts separate. An optional comparison page must label each series and must not present their sum as organisational spend.
- Generated data documentation must state the generator version, seed, assumptions, and deliberately simulated behaviours.

## FX rule for the later phase

Preserve original amount and ISO currency; convert with `Decimal`; use the transaction-date rate when available and otherwise the most recent prior available rate; store provider, requested date, applied rate date, base/quote pair, raw rate, and retrieval timestamp. Fail or quarantine the conversion when no prior rate exists within an agreed lookback window rather than silently substituting a current rate.

