# Phase 4 dbt live verification

Status: **PASS**  
Generated: `2026-10-01T13:58:21.996863+00:00`

## Runtime

- Python: `3.13.5`
- dbt Core: `1.7.19`
- dbt MySQL adapter: `1.7.0`
- MySQL Server: `8.0.46`

## Commands

| Command | Exit code | Log |
|---|---:|---|
| `dbt debug` | 0 | Pass |
| `dbt build` | 0 | 90/90 nodes passed |
| `dbt test` | 0 | 73/73 tests passed |
| `dbt docs generate` | 0 | Catalog generated |

## Built relation counts

| Relation | Rows |
|---|---:|
| `int_synthetic_spend` | 5,000 |
| `int_approval_cycles` | 5,000 |
| `mart_department_spend` | 12 |
| `mart_vendor_performance` | 125 |
| `mart_contract_compliance` | 2,918 |
| `mart_approval_performance` | 144 |
| `mart_monthly_currency_spend` | 36 |

## Currency reconciliation

| Currency | Rows | Original amount | GBP amount |
|---|---:|---:|---:|
| EUR | 1,250 | 312591016.58 | 269481892.86 |
| GBP | 3,000 | 753145670.04 | 753145670.04 |
| USD | 750 | 184759495.49 | 138309075.73 |

dbt total GBP: **1160936638.63**  
Phase 3 baseline GBP: **1160936638.63**  
Spend row mismatches: **0**  
Approval row mismatches: **0**

All data in these dbt models is labelled synthetic. No DEFRA table was loaded or modelled in Phase 4 because no DEFRA MySQL source table exists.
