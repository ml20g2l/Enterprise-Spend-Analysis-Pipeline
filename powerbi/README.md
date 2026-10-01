# Power BI report

`Enterprise_Spend_Analysis_Pipeline.pbix` is the final three-page reporting
layer. It consumes the reviewed dbt marts in MySQL rather than rebuilding
business logic in Power Query.

Pages:

1. Executive Spend Overview
2. Contract & Vendor Performance
3. Approval & Operational Performance

The report represents the explicitly labelled fictional corporate scenario;
it does not present the DEFRA public records as company transactions. Local
MySQL credentials are not committed. See `docs/phase6_powerbi_design.md` for
the semantic model and `reports/powerbi_qa_report.md` for QA evidence.

The earlier HTML prototype is deliberately ignored and is not part of the
portfolio deliverable.
