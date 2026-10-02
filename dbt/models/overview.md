{% docs __overview__ %}

# Enterprise Spend Analytics

This dbt project transforms a deterministic fictional company scenario into
five governed reporting marts. It does not contain DEFRA transactions.

## Data boundary

The repository has two separate data paths:

- Real DEFRA public data supports profiling and descriptive analysis outside
  this dbt project.
- Fictional corporate data supports contract, approval, vendor, currency, and
  management-reporting demonstrations in this dbt project.

All scenario models retain source labels. Corporate results are not claims
about DEFRA or a real company.

## Model layers

1. **Staging:** seven views standardise names, types, null meaning, and source
   labels from the MySQL raw tables.
2. **Intermediate:** five views apply reusable FX, contract, approval, and
   vendor-satisfaction logic.
3. **Marts:** five tables provide controlled reporting outputs at declared
   business grains.

## Reporting marts

| Mart | Grain | Main use |
|---|---|---|
| `mart_department_spend` | One department for the full period | Department spend and compliance |
| `mart_vendor_performance` | One vendor for the full period | Vendor spend, risk, compliance, and satisfaction |
| `mart_contract_compliance` | Month × department × category × compliance status | Contract control analysis |
| `mart_approval_performance` | Month × department | Approval time and SLA analysis |
| `mart_monthly_currency_spend` | Month × original currency | Currency exposure and GBP reporting |

## Control principles

- Python owns API access, cache persistence, deterministic generation, and raw
  loading.
- dbt owns relational transformation, business rules, tests, lineage, and
  reporting marts.
- Applied FX rates use the latest available observation on or before each
  transaction date.
- Contract compliance uses vendor, category, and validity-date relationships.
- Reconciliation tests compare dbt results with independent Python audit facts.
- Power BI consumes the marts and does not rebuild the main transformation
  rules.

## Verified baseline

The verified project contains 17 models and 73 data tests. The reporting grain
contains 5,000 fictional expenses and reconciles to £1,160,936,638.63.

{% enddocs %}
