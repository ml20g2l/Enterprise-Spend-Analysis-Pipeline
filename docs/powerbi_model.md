# Power BI semantic model and dashboard design

## Status and scope

The three-page report is complete and stored at
`powerbi/Enterprise_Spend_Analysis_Pipeline.pbix`. This document records the
implemented semantic model, measures, visual design, and interaction limits.

All five reporting marts describe a **synthetic fictional company**. They must not be presented as DEFRA activity. Every mart currently contains `record_origin = 'synthetic_fictional_company'` and `is_synthetic = 1`.

The specification was validated against the live MySQL `enterprise_spend`
database on 29 September 2026. The reproducible read-only query output is in
`reports/reporting_analysis_snapshot.json`; rendered and package QA is documented
in `reports/powerbi_qa_report.md`.

## Reporting tables and grain

| Table | Rows | Grain | Primary report use |
|---|---:|---|---|
| `mart_department_spend` | 12 | One department for the full period | Department lookup and full-period departmental summary |
| `mart_vendor_performance` | 125 | One vendor for the full period | Vendor spend, risk, compliance, and survey performance |
| `mart_contract_compliance` | 2,918 | Month + department + spend category + compliance status | Filterable spend and contract analysis |
| `mart_approval_performance` | 144 | Month + department | Approval speed and SLA analysis |
| `mart_monthly_currency_spend` | 36 | Month + original currency | Currency exposure and monthly converted spend |

Only these five marts should be loaded. Do not load raw, staging, intermediate, or actual DEFRA tables into this report.

## Recommended semantic model

The marts are aggregate facts at different grains. Do not connect them directly, and do not use bidirectional or many-to-many relationships.

Create a month dimension in Power BI:

```DAX
DimMonth =
VAR Months =
    DISTINCT (
        UNION (
            SELECTCOLUMNS (
                'mart_monthly_currency_spend',
                "MonthStart", DATEVALUE ( 'mart_monthly_currency_spend'[spend_month] )
            ),
            SELECTCOLUMNS (
                'mart_contract_compliance',
                "MonthStart", DATEVALUE ( 'mart_contract_compliance'[spend_month] )
            ),
            SELECTCOLUMNS (
                'mart_approval_performance',
                "MonthStart", DATEVALUE ( 'mart_approval_performance'[spend_month] )
            )
        )
    )
RETURN
    ADDCOLUMNS (
        Months,
        "Year", YEAR ( [MonthStart] ),
        "Month Number", MONTH ( [MonthStart] ),
        "Year Month", FORMAT ( [MonthStart], "yyyy-MM" ),
        "Year Month Sort", YEAR ( [MonthStart] ) * 100 + MONTH ( [MonthStart] )
    )
```

Set `DimMonth[MonthStart]` to Date, then sort `DimMonth[Year Month]` by `DimMonth[Year Month Sort]`.

Before creating relationships, change `spend_month` in the three monthly marts from Text to Date in Power Query. This is a type conversion, not business transformation.

Create these single-direction one-to-many relationships:

| One side | Many side | Cardinality/filter |
|---|---|---|
| `DimMonth[MonthStart]` | `mart_contract_compliance[spend_month]` | 1:*; single direction |
| `DimMonth[MonthStart]` | `mart_approval_performance[spend_month]` | 1:*; single direction |
| `DimMonth[MonthStart]` | `mart_monthly_currency_spend[spend_month]` | 1:*; single direction |
| `mart_department_spend[department_id]` | `mart_contract_compliance[department_id]` | 1:*; single direction |
| `mart_department_spend[department_id]` | `mart_approval_performance[department_id]` | 1:*; single direction |

Rename `mart_department_spend` to `DimDepartment` in the Power BI model if desired, but do not change its source table. Hide its aggregate columns from report view if they are not used.

Leave `mart_vendor_performance` standalone. No other selected mart contains `vendor_id`. Currency exists only in `mart_monthly_currency_spend`.

### Known interaction limits

- Month, department, and category can filter contract visuals.
- Month and department can filter approval visuals.
- Month can filter currency visuals.
- Vendor visuals are full-period only and do not respond to month or department.
- Currency visuals cannot be filtered by department or spend category.
- The full-period fields in `mart_department_spend` do not respond to month.

Use **Edit interactions** to disable misleading cross-filtering and add the subtitle “Full period” to vendor visuals. These limits are a consequence of the existing aggregate mart grains, not a Power BI defect. A future dbt enhancement could add a conformed month–department–vendor–currency fact, but that is outside Phase 6.

## Measures

Create a dedicated empty measures table and add the following measures. Format GBP measures as `£#,0.00` (cards may use display units), counts as whole numbers, ratings as `0.00`, hours as `0.00`, and percentages as `0.00%`.

### Spend and currency

```DAX
Total Spend GBP =
SUM ( 'mart_contract_compliance'[amount_gbp] )

Expense Count =
SUM ( 'mart_contract_compliance'[expense_count] )

Average Expense GBP =
DIVIDE ( [Total Spend GBP], [Expense Count] )

Department Count =
DISTINCTCOUNT ( 'mart_contract_compliance'[department_id] )

Previous Month Spend GBP =
VAR CurrentMonth = MAX ( 'DimMonth'[MonthStart] )
RETURN
    CALCULATE (
        [Total Spend GBP],
        FILTER (
            ALL ( 'DimMonth' ),
            'DimMonth'[MonthStart] = EDATE ( CurrentMonth, -1 )
        )
    )

MoM Spend % =
VAR PreviousSpend = [Previous Month Spend GBP]
RETURN
    IF (
        NOT ISBLANK ( PreviousSpend ),
        DIVIDE ( [Total Spend GBP] - PreviousSpend, PreviousSpend )
    )

Currency Spend GBP =
SUM ( 'mart_monthly_currency_spend'[amount_gbp] )

Currency Expense Count =
SUM ( 'mart_monthly_currency_spend'[expense_count] )

Currency Spend Share % =
DIVIDE (
    [Currency Spend GBP],
    CALCULATE (
        [Currency Spend GBP],
        REMOVEFILTERS ( 'mart_monthly_currency_spend'[original_currency] )
    )
)
```

### Contract and vendor

```DAX
Contract Expense Count =
SUM ( 'mart_contract_compliance'[expense_count] )

Compliant Expense Count =
CALCULATE (
    [Contract Expense Count],
    KEEPFILTERS ( 'mart_contract_compliance'[is_contract_compliant] = 1 )
)

Contract Compliance % =
DIVIDE ( [Compliant Expense Count], [Contract Expense Count] )

Non-Compliant Spend GBP =
CALCULATE (
    [Total Spend GBP],
    KEEPFILTERS ( 'mart_contract_compliance'[is_contract_compliant] = 0 )
)

Non-Compliant Spend % =
DIVIDE ( [Non-Compliant Spend GBP], [Total Spend GBP] )

Vendor Spend GBP =
SUM ( 'mart_vendor_performance'[amount_gbp] )

Vendor Expense Count =
SUM ( 'mart_vendor_performance'[expense_count] )

Vendor Count =
DISTINCTCOUNT ( 'mart_vendor_performance'[vendor_id] )

Vendor Contract Compliance % =
DIVIDE (
    SUM ( 'mart_vendor_performance'[compliant_expense_count] ),
    [Vendor Expense Count]
)

Survey Response Count =
SUM ( 'mart_vendor_performance'[response_count] )

Weighted Overall Rating =
DIVIDE (
    SUMX (
        'mart_vendor_performance',
        'mart_vendor_performance'[avg_overall_rating]
            * 'mart_vendor_performance'[response_count]
    ),
    [Survey Response Count]
)

High-Risk Spend GBP =
CALCULATE (
    [Vendor Spend GBP],
    KEEPFILTERS ( 'mart_vendor_performance'[risk_tier] = "high" )
)

High-Risk Spend % =
DIVIDE ( [High-Risk Spend GBP], [Vendor Spend GBP] )
```

The weighted rating correctly handles vendors with different response counts. Filter out blank ratings in charts that compare survey results; a blank means no response, not a zero rating.

### Approval

```DAX
Approval Requests =
SUM ( 'mart_approval_performance'[approval_request_count] )

Average Approval Cycle Hours =
DIVIDE (
    SUMX (
        'mart_approval_performance',
        'mart_approval_performance'[avg_approval_cycle_hours]
            * 'mart_approval_performance'[approval_request_count]
    ),
    [Approval Requests]
)

Average Request to Payment Hours =
DIVIDE (
    SUMX (
        'mart_approval_performance',
        'mart_approval_performance'[avg_request_to_payment_hours]
            * 'mart_approval_performance'[approval_request_count]
    ),
    [Approval Requests]
)

SLA Breach Count =
SUM ( 'mart_approval_performance'[sla_breach_count] )

SLA Breach % =
DIVIDE ( [SLA Breach Count], [Approval Requests] )
```

Do not average the pre-aggregated percentage or average columns directly. The measures above weight them by request/expense count.

## Page 1 — Executive Spend Overview

### Questions

- How much was spent, across how many synthetic expenses?
- How did converted GBP spend change by month?
- Which departments account for the most spend?
- What is the original-currency mix after GBP conversion?
- Which vendors account for the most full-period spend?

### Visuals

| Visual | Fields/measures | Purpose |
|---|---|---|
| KPI cards | `[Total Spend GBP]`, `[Expense Count]`, `[Average Expense GBP]`, `[Contract Compliance %]` | Scale and headline control indicator |
| Line chart | Axis `DimMonth[Year Month]`; value `[Total Spend GBP]`; tooltip `[Expense Count]`, `[MoM Spend %]` | Monthly trend |
| Horizontal bar | Axis `mart_department_spend[department_name]`; value `[Total Spend GBP]` | Department comparison using the contract fact |
| Donut or 100% stacked bar | Legend `mart_monthly_currency_spend[original_currency]`; value `[Currency Spend GBP]`; tooltip `[Currency Spend Share %]`, `[Currency Expense Count]` | Currency exposure |
| Top-10 horizontal bar | Axis `mart_vendor_performance[vendor_name]`; value `[Vendor Spend GBP]`; tooltip risk, category, compliance, rating | Full-period vendor concentration |

Slicers: `DimMonth[Year Month]`, `mart_department_spend[department_name]`, and `mart_contract_compliance[spend_category]`.

Interactions: month filters the trend, cards, department, and currency visuals. Department/category filters affect only visuals sourced from contract compliance. Disable their interaction with currency and vendor visuals. Label the vendor chart “Top vendors — full period”.

Interpretation: management can distinguish timing, departmental allocation, currency exposure, and supplier concentration without implying that all visuals share a transaction-level grain.

## Page 2 — Contract & Vendor Performance

### Questions

- What share of expenses is contract compliant?
- How much spend is non-compliant and what explains it?
- Which departments and categories should be prioritised?
- Do high-risk vendors combine material spend with weak compliance?
- Which vendors have survey evidence, and how strong is it?

### Visuals

| Visual | Fields/measures | Purpose |
|---|---|---|
| KPI cards | `[Contract Compliance %]`, `[Non-Compliant Spend GBP]`, `[Non-Compliant Spend %]`, `[High-Risk Spend GBP]`, `[Weighted Overall Rating]` | Headline contract/vendor risk |
| Stacked horizontal bar | Axis `contract_compliance_status`; value `[Total Spend GBP]`; legend `is_contract_compliant` | Explain compliance classification |
| Department bar | Axis `department_name`; value `[Non-Compliant Spend GBP]`; tooltip `[Non-Compliant Spend %]`, `[Contract Expense Count]` | Department priorities |
| Category combo/bar | Axis `spend_category`; columns `[Non-Compliant Spend GBP]`; line `[Non-Compliant Spend %]` | Separate absolute exposure from rate |
| Vendor scatter | X `contract_compliance_pct`; Y `avg_overall_rating`; size `amount_gbp`; details `vendor_name`; legend `risk_tier` | Vendor risk/performance portfolio |
| Vendor table | vendor name, category, risk tier, `[Vendor Spend GBP]`, `contract_compliance_pct`, `avg_overall_rating`, `response_count` | Inspectable watchlist |

Slicers: month, department, spend category for contract visuals; risk tier and vendor primary category for vendor visuals. Keep the two slicer groups visually separated.

Interactions: contract slicers must not filter vendor visuals because the vendor mart is full-period and standalone. Risk/category vendor slicers must not filter contract visuals. Filter the vendor scatter to non-blank `avg_overall_rating` and show `response_count` in the tooltip.

Interpretation: prioritise by both non-compliant value and non-compliance rate. Treat vendor ratings as supporting evidence only; response counts are limited and the scenario is synthetic.

## Page 3 — Approval & Operational Performance

### Questions

- How long do approvals and end-to-end payment take?
- What share of requests breaches the SLA?
- Are delays concentrated by month or department?
- Which departments combine high cycle time with a high breach rate?

### Visuals

| Visual | Fields/measures | Purpose |
|---|---|---|
| KPI cards | `[Approval Requests]`, `[Average Approval Cycle Hours]`, `[Average Request to Payment Hours]`, `[SLA Breach Count]`, `[SLA Breach %]` | Operational headline |
| Line and clustered column | Axis `DimMonth[Year Month]`; columns `[SLA Breach %]`; line `[Average Approval Cycle Hours]` | Monthly trend and co-movement |
| Department bar | Axis `department_name`; value `[SLA Breach %]`; tooltip cycle hours, payment hours, requests | Department comparison |
| Scatter | X `[Average Approval Cycle Hours]`; Y `[SLA Breach %]`; size `[Approval Requests]`; details `department_name` | Operational priority matrix |
| Matrix | Rows department; columns `DimMonth[Year Month]`; values `[SLA Breach %]` | Heat-map with conditional formatting |

Slicers: `DimMonth[Year Month]` and `mart_department_spend[department_name]`. Every visual on this page responds to both.

Interpretation: identify sustained process issues rather than reacting to one month, and distinguish long average cycle time from high SLA breach frequency.

## Power BI Desktop connection steps

1. Install the 64-bit Oracle MySQL Connector/NET provider if it is not already installed, matching the 64-bit Power BI Desktop installation. Restart Power BI Desktop after installation. Microsoft documents Connector/NET as the required MySQL provider and supports MySQL tables/views.
2. Open Power BI Desktop and select **Home → Get data → More → Database → MySQL database**.
3. Enter server `127.0.0.1:3306` and database `enterprise_spend`.
4. Select **Import**. The five marts total only 3,235 rows, so Import is simpler and faster for this local portfolio report.
5. When prompted, choose **Database** authentication, username `spend_app`, and the existing MySQL application password. Do not save the password in the repository.
6. If Power BI warns that the connection is unencrypted, accept it only for this local machine setup. A shared or production deployment should use TLS.
7. In Navigator, select only the five `mart_*` tables listed above, then choose **Transform Data**.
8. Confirm money columns are Fixed decimal number, counts are Whole number, ratings/hours are Decimal number, and the three `spend_month` fields are Date.
9. Apply changes, create `DimMonth`, add the five relationships, and then create the measures.
10. Build the pages and use **Edit interactions** exactly as described above.
11. Validate the finished report against the control totals below before saving.

Official setup references: [Microsoft MySQL database connector](https://learn.microsoft.com/en-us/power-query/connectors/mysql-database) and [Power BI data-source prerequisites](https://learn.microsoft.com/en-us/power-bi/desktop-data-source-prerequisites).

## Acceptance checks

With no filters applied, the report must show:

| Check | Expected value |
|---|---:|
| Total spend | £1,160,936,638.63 |
| Expense / approval request count | 5,000 |
| Average expense | £232,187.33 |
| Contract-compliant expenses | 3,660 |
| Contract compliance | 73.20% |
| Non-compliant spend | £305,916,170.54 |
| SLA breaches | 1,919 |
| SLA breach rate | 38.38% |
| Weighted average approval cycle | 60.99 hours |
| Weighted request-to-payment time | 111.09 hours |

Also confirm that totals from the contract, currency, department, and vendor marts reconcile to the same £1,160,936,638.63 and 5,000 expenses. Minor display rounding is acceptable; model values must reconcile to the penny.
