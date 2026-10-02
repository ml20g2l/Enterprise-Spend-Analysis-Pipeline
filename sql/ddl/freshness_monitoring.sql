-- Additive audit tables for data-freshness monitoring.
-- This migration does not alter or recreate existing Phase 3 tables.

CREATE TABLE IF NOT EXISTS pipeline_freshness_run (
    monitor_run_id VARCHAR(180) PRIMARY KEY,
    airflow_run_id VARCHAR(250) NOT NULL,
    checked_at_utc DATETIME(6) NOT NULL,
    policy_version VARCHAR(30) NOT NULL,
    overall_status VARCHAR(10) NOT NULL,
    checks_passed SMALLINT UNSIGNED NOT NULL,
    checks_failed SMALLINT UNSIGNED NOT NULL,
    report_json JSON NOT NULL,
    recorded_at_utc TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CHECK (overall_status IN ('PASS', 'FAIL'))
);

CREATE TABLE IF NOT EXISTS pipeline_freshness_result (
    monitor_run_id VARCHAR(180) NOT NULL,
    rule_id VARCHAR(100) NOT NULL,
    rule_status VARCHAR(10) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    observed_value VARCHAR(255),
    expected_value VARCHAR(255) NOT NULL,
    message VARCHAR(1000) NOT NULL,
    PRIMARY KEY (monitor_run_id, rule_id),
    CONSTRAINT fk_freshness_result_run
        FOREIGN KEY (monitor_run_id)
        REFERENCES pipeline_freshness_run(monitor_run_id)
        ON DELETE CASCADE,
    CHECK (rule_status IN ('PASS', 'FAIL')),
    CHECK (severity IN ('critical', 'high', 'medium', 'low'))
);
