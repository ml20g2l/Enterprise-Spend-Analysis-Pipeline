-- Independent SQL contract-match audit for synthetic expenses.
-- Missing submitted_contract_id is not treated as non-compliance by itself.

WITH active_matches AS (
    SELECT
        e.expense_id,
        c.contract_id,
        ROW_NUMBER() OVER (PARTITION BY e.expense_id ORDER BY c.contract_id) AS match_rank
    FROM raw_synthetic_expense e
    JOIN raw_synthetic_contract c
      ON c.vendor_id = e.vendor_id
     AND c.approved_category = e.spend_category
     AND e.transaction_date BETWEEN c.contract_start_date AND c.contract_end_date
),
expected AS (
    SELECT
        e.expense_id,
        CASE
            WHEN submitted.contract_id IS NOT NULL
             AND submitted.vendor_id = e.vendor_id
             AND submitted.approved_category = e.spend_category
             AND e.transaction_date BETWEEN submitted.contract_start_date AND submitted.contract_end_date
                THEN submitted.contract_id
            ELSE active.contract_id
        END AS expected_matched_contract_id
    FROM raw_synthetic_expense e
    LEFT JOIN raw_synthetic_contract submitted
      ON submitted.contract_id = e.submitted_contract_id
    LEFT JOIN active_matches active
      ON active.expense_id = e.expense_id
     AND active.match_rank = 1
)
SELECT
    COUNT(*) AS mismatched_fact_rows
FROM fact_synthetic_spend f
JOIN expected e USING (expense_id)
WHERE NOT (f.matched_contract_id <=> e.expected_matched_contract_id);

