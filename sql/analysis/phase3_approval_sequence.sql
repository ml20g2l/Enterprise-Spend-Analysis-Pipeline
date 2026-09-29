-- Returns invalid approval workflows; expected result is zero rows.

WITH sequenced AS (
    SELECT
        expense_id,
        COUNT(*) AS event_count,
        MIN(CASE WHEN event_sequence = 1 THEN event_timestamp_utc END) AS request_ts,
        MIN(CASE WHEN event_sequence = 2 THEN event_timestamp_utc END) AS manager_ts,
        MIN(CASE WHEN event_sequence = 3 THEN event_timestamp_utc END) AS finance_ts,
        MIN(CASE WHEN event_sequence = 4 THEN event_timestamp_utc END) AS payment_ts
    FROM raw_synthetic_approval_event
    GROUP BY expense_id
)
SELECT *
FROM sequenced
WHERE event_count <> 4
   OR NOT (request_ts < manager_ts AND manager_ts < finance_ts AND finance_ts < payment_ts);

