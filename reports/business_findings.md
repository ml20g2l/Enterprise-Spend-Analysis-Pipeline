# Business findings from the fictional scenario

## Executive summary

The five live dbt marts describe 5,000 **synthetic fictional-company** expenses from March 2025 through February 2026. Converted spend totals **£1,160,936,638.63**, or **£232,187.33 per expense**. These findings demonstrate the reporting layer; they are not findings about DEFRA or a real company.

The principal control issues in the scenario are contract compliance and approval performance. Only **73.20%** of expenses are compliant by count, while **£305.92m (26.35%)** of spend is non-compliant. The approval process has **1,919 SLA breaches (38.38%)**, with a weighted mean approval time of **60.99 hours**.

## Spend profile

### Monthly pattern

| Month | Expenses | Converted GBP spend |
|---|---:|---:|
| 2025-03 | 408 | £94,395,357.90 |
| 2025-04 | 386 | £85,834,974.03 |
| 2025-05 | 395 | £93,773,241.77 |
| 2025-06 | 414 | £91,845,279.36 |
| 2025-07 | 427 | £97,583,815.89 |
| 2025-08 | 445 | £103,161,628.81 |
| 2025-09 | 426 | £100,960,513.92 |
| 2025-10 | 474 | £115,546,744.15 |
| 2025-11 | 434 | £102,600,214.71 |
| 2025-12 | 414 | £94,205,570.15 |
| 2026-01 | 418 | £96,248,578.29 |
| 2026-02 | 359 | £84,780,719.65 |

October 2025 is the peak month at **£115.55m** and 474 expenses. February 2026 is the lowest at **£84.78m** and 359 expenses. Peak spend is **36.29%** higher than the trough. With only one synthetic year, this is a within-period pattern rather than evidence of seasonality.

### Currency exposure

| Original currency | Expenses | Converted GBP spend | Spend share |
|---|---:|---:|---:|
| GBP | 3,000 | £753,145,670.04 | 64.87% |
| EUR | 1,250 | £269,481,892.86 | 23.21% |
| USD | 750 | £138,309,075.73 | 11.91% |

GBP represents 60% of transactions but 64.87% of converted spend. EUR and USD together contribute **35.13%** of converted spend, so the dashboard should retain the original-currency view rather than displaying only the GBP total.

### Department and vendor concentration

Spend is deliberately balanced across departments. Sales is the largest at **£101.36m (8.73%)**, while Marketing is the smallest at **£92.24m (7.95%)**. No individual department dominates the scenario.

The five largest vendors account for **£134.69m**, only **11.60%** of total spend. The largest vendor, Fictional Vendor 021 - Cloud Services, accounts for **£29.94m**. This indicates low top-vendor concentration in the generated data; it does not by itself establish low supply-chain risk.

## Contract compliance

Of 5,000 expenses, **3,660 are compliant (73.20%)**. Non-compliant spend is **£305,916,170.54 (26.35%)**.

### Classification of spend

| Status | Expenses | Converted GBP spend | Interpretation |
|---|---:|---:|---|
| `compliant_submitted_contract` | 2,993 | £697,954,866.56 | Submitted contract is valid and aligned |
| `compliant_master_match` | 507 | £117,886,884.30 | Valid matching master contract found |
| `compliant_alternate_master_match` | 160 | £39,178,717.23 | Alternative valid master match found |
| `no_active_matching_contract` | 500 | £116,946,147.25 | No active matching contract |
| `non_compliant_category_mismatch` | 470 | £105,147,478.29 | Contract category mismatch |
| `non_compliant_outside_validity` | 370 | £83,822,545.00 | Spend outside contract dates |

The largest non-compliant driver is **no active matching contract (£116.95m)**, followed by category mismatch (£105.15m) and spend outside validity (£83.82m). This supports a control response focused on contract coverage first, then category governance and renewal/date controls.

Customer Success has the largest departmental non-compliant exposure at **£33.62m** and the highest department rate at **33.75%**. Sales has the lowest rate at **21.15%**. By category, Telecommunications has the largest non-compliant value (**£38.24m**), while Logistics has the highest non-compliance rate (**33.18%**). The dashboard should show both value and rate because either alone can give the wrong priority.

## Vendor performance and risk

| Risk tier | Vendors | Spend | Contract compliance | Weighted rating |
|---|---:|---:|---:|---:|
| Low | 87 | £867,370,167.16 | 74.27% | 3.54 |
| Medium | 31 | £249,213,901.63 | 73.07% | 3.41 |
| High | 7 | £44,352,569.84 | 53.37% | 4.10 |

High-risk vendors have materially lower contract compliance (**53.37%**) than low- and medium-risk vendors, despite representing only seven vendors and £44.35m. That combination makes them a useful watchlist.

The high-risk group also has the highest weighted survey rating, but this must not be interpreted as a contradiction or causal result. Ratings are synthetic, response coverage varies by vendor, and some vendors have no responses. Blank ratings must remain blank rather than being treated as zero.

## Approval operations

Across 5,000 approval requests, the weighted mean approval cycle is **60.99 hours**, the weighted request-to-payment time is **111.09 hours**, and **1,919 requests (38.38%)** breach the SLA.

The highest monthly breach rate occurs in May 2025 (**41.52%**); November 2025 is the lowest (**33.18%**). The spread is meaningful for the dashboard, but a single synthetic year is insufficient to call it a seasonal pattern.

Research has the highest department breach rate at **42.04%**. Procurement has the longest average approval cycle at **64.04 hours** and a **40.84%** breach rate. Facilities performs best on breach rate at **33.74%** and has the shortest average approval cycle at **58.26 hours**. The scatter plot should therefore surface Procurement and Research as different operational priorities: one leads on cycle duration, the other on breach frequency.

## Decision-oriented interpretation

1. Prioritise the **£116.95m with no active matching contract**, then investigate category mismatch and validity-date controls.
2. Focus departmental contract review on Customer Success, while using both absolute value and rate to avoid over-prioritising small exposures.
3. Review high-risk vendors as a portfolio because their compliance rate is 19.83 percentage points below the overall 73.20% rate.
4. Investigate Procurement's longer cycle and Research's higher breach frequency separately; the measures describe different failure modes.
5. Preserve the currency view because more than one-third of converted spend originates in EUR or USD.

These are interpretations of a deterministic synthetic scenario. They are suitable for demonstrating analytical reasoning and dashboard behaviour, not for operational action in a real organisation.

## Validation and limitations

- Live source: MySQL `enterprise_spend`, queried read-only on 29 September 2026.
- Origin controls: every selected mart reports `synthetic_fictional_company` and `is_synthetic = 1`.
- Reconciliation: department, vendor, contract, and currency marts each reconcile to **5,000 expenses and £1,160,936,638.63**.
- Approval reconciliation: **5,000 requests**, one per synthetic expense.
- Live Phase 6 snapshot checks: **10/10 passed** (origin controls, counts, spend, and approval completeness).
- Automated regression suite: **19/19 tests passed** in the project dbt virtual environment.
- Model constraint: the five marts are aggregate tables at different grains. Vendor analysis is full-period; department/category cannot filter currency; department spend cannot be trended from `mart_department_spend`.
- Evidence: `reports/reporting_analysis_snapshot.json` contains the schemas and query results used here; `src/analysis/phase6_powerbi_analysis.py` reproduces the snapshot.
