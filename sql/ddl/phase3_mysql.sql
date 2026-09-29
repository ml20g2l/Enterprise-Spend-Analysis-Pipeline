-- Phase 3 MySQL 8.0 schema.
-- Synthetic tables are physically separate from raw_defra_transactions and fact_defra_spend.

CREATE TABLE IF NOT EXISTS pipeline_load_run (
    generation_run_id CHAR(64) PRIMARY KEY,
    scenario_id VARCHAR(100) NOT NULL,
    generation_version VARCHAR(30) NOT NULL,
    random_seed BIGINT NOT NULL,
    manifest_json JSON NOT NULL,
    loaded_at_utc TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
);

CREATE TABLE IF NOT EXISTS raw_synthetic_department (
    source_record_id CHAR(64) PRIMARY KEY,
    department_id VARCHAR(20) NOT NULL UNIQUE,
    department_name VARCHAR(100) NOT NULL,
    cost_centre VARCHAR(30) NOT NULL,
    scenario_id VARCHAR(100) NOT NULL,
    record_origin VARCHAR(100) NOT NULL,
    is_synthetic BOOLEAN NOT NULL,
    CHECK (is_synthetic = TRUE)
);

CREATE TABLE IF NOT EXISTS raw_synthetic_vendor (
    source_record_id CHAR(64) PRIMARY KEY,
    vendor_id VARCHAR(20) NOT NULL UNIQUE,
    vendor_name VARCHAR(255) NOT NULL,
    country VARCHAR(100) NOT NULL,
    default_currency CHAR(3) NOT NULL,
    primary_category VARCHAR(100) NOT NULL,
    risk_tier VARCHAR(20) NOT NULL,
    scenario_id VARCHAR(100) NOT NULL,
    record_origin VARCHAR(100) NOT NULL,
    is_synthetic BOOLEAN NOT NULL,
    CHECK (default_currency IN ('GBP', 'EUR', 'USD')),
    CHECK (is_synthetic = TRUE)
);

CREATE TABLE IF NOT EXISTS raw_synthetic_contract (
    source_record_id CHAR(64) PRIMARY KEY,
    contract_id VARCHAR(20) NOT NULL UNIQUE,
    vendor_id VARCHAR(20) NOT NULL,
    contract_start_date DATE NOT NULL,
    contract_end_date DATE NOT NULL,
    contract_value_gbp DECIMAL(20,2) NOT NULL,
    approved_category VARCHAR(100) NOT NULL,
    contract_status VARCHAR(30) NOT NULL,
    scenario_id VARCHAR(100) NOT NULL,
    record_origin VARCHAR(100) NOT NULL,
    is_synthetic BOOLEAN NOT NULL,
    CONSTRAINT fk_contract_vendor FOREIGN KEY (vendor_id) REFERENCES raw_synthetic_vendor(vendor_id),
    CHECK (contract_end_date >= contract_start_date),
    CHECK (contract_value_gbp > 0),
    CHECK (is_synthetic = TRUE)
);

CREATE TABLE IF NOT EXISTS raw_synthetic_expense (
    source_record_id CHAR(64) PRIMARY KEY,
    expense_id VARCHAR(20) NOT NULL UNIQUE,
    transaction_date DATE NOT NULL,
    department_id VARCHAR(20) NOT NULL,
    vendor_id VARCHAR(20) NOT NULL,
    spend_category VARCHAR(100) NOT NULL,
    description VARCHAR(500) NOT NULL,
    submitted_contract_id VARCHAR(20),
    original_amount DECIMAL(20,2) NOT NULL,
    original_currency CHAR(3) NOT NULL,
    payment_method VARCHAR(50) NOT NULL,
    scenario_id VARCHAR(100) NOT NULL,
    generation_seed BIGINT NOT NULL,
    record_origin VARCHAR(100) NOT NULL,
    is_synthetic BOOLEAN NOT NULL,
    CONSTRAINT fk_expense_department FOREIGN KEY (department_id) REFERENCES raw_synthetic_department(department_id),
    CONSTRAINT fk_expense_vendor FOREIGN KEY (vendor_id) REFERENCES raw_synthetic_vendor(vendor_id),
    CONSTRAINT fk_expense_submitted_contract FOREIGN KEY (submitted_contract_id) REFERENCES raw_synthetic_contract(contract_id),
    CHECK (original_amount > 0),
    CHECK (original_currency IN ('GBP', 'EUR', 'USD')),
    CHECK (is_synthetic = TRUE)
);

CREATE TABLE IF NOT EXISTS raw_fx_rate (
    fx_rate_id CHAR(64) PRIMARY KEY,
    rate_date DATE NOT NULL,
    base_currency CHAR(3) NOT NULL,
    quote_currency CHAR(3) NOT NULL,
    rate DECIMAL(20,10) NOT NULL,
    fx_source VARCHAR(255) NOT NULL,
    cache_file VARCHAR(255) NOT NULL,
    UNIQUE KEY uq_fx_observation (rate_date, base_currency, quote_currency, fx_source),
    CHECK (rate > 0)
);

CREATE TABLE IF NOT EXISTS raw_synthetic_approval_event (
    source_record_id CHAR(64) PRIMARY KEY,
    event_id VARCHAR(40) NOT NULL UNIQUE,
    expense_id VARCHAR(20) NOT NULL,
    event_sequence TINYINT NOT NULL,
    event_type VARCHAR(40) NOT NULL,
    event_timestamp_utc DATETIME(6) NOT NULL,
    actor_role VARCHAR(50) NOT NULL,
    scenario_id VARCHAR(100) NOT NULL,
    record_origin VARCHAR(100) NOT NULL,
    is_synthetic BOOLEAN NOT NULL,
    CONSTRAINT fk_event_expense FOREIGN KEY (expense_id) REFERENCES raw_synthetic_expense(expense_id),
    UNIQUE KEY uq_expense_event_sequence (expense_id, event_sequence),
    CHECK (event_sequence BETWEEN 1 AND 4),
    CHECK (is_synthetic = TRUE)
);

CREATE TABLE IF NOT EXISTS raw_synthetic_vendor_satisfaction (
    source_record_id CHAR(64) PRIMARY KEY,
    response_id VARCHAR(20) NOT NULL UNIQUE,
    vendor_id VARCHAR(20) NOT NULL,
    response_date DATE NOT NULL,
    overall_rating TINYINT NOT NULL,
    delivery_rating TINYINT NOT NULL,
    quality_rating TINYINT NOT NULL,
    support_rating TINYINT NOT NULL,
    response_channel VARCHAR(50) NOT NULL,
    scenario_id VARCHAR(100) NOT NULL,
    record_origin VARCHAR(100) NOT NULL,
    is_synthetic BOOLEAN NOT NULL,
    CONSTRAINT fk_survey_vendor FOREIGN KEY (vendor_id) REFERENCES raw_synthetic_vendor(vendor_id),
    CHECK (overall_rating BETWEEN 1 AND 5),
    CHECK (delivery_rating BETWEEN 1 AND 5),
    CHECK (quality_rating BETWEEN 1 AND 5),
    CHECK (support_rating BETWEEN 1 AND 5),
    CHECK (is_synthetic = TRUE)
);

CREATE TABLE IF NOT EXISTS fact_synthetic_spend (
    source_record_id CHAR(64) PRIMARY KEY,
    expense_id VARCHAR(20) NOT NULL UNIQUE,
    transaction_date DATE NOT NULL,
    department_id VARCHAR(20) NOT NULL,
    vendor_id VARCHAR(20) NOT NULL,
    spend_category VARCHAR(100) NOT NULL,
    submitted_contract_id VARCHAR(20),
    matched_contract_id VARCHAR(20),
    contract_compliance_status VARCHAR(60) NOT NULL,
    is_contract_compliant BOOLEAN NOT NULL,
    original_amount DECIMAL(20,2) NOT NULL,
    original_currency CHAR(3) NOT NULL,
    fx_rate_to_gbp DECIMAL(20,10) NOT NULL,
    fx_rate_date DATE NOT NULL,
    amount_gbp DECIMAL(20,2) NOT NULL,
    fx_source VARCHAR(255) NOT NULL,
    fx_cache_file VARCHAR(255) NOT NULL,
    scenario_id VARCHAR(100) NOT NULL,
    generation_seed BIGINT NOT NULL,
    record_origin VARCHAR(100) NOT NULL,
    is_synthetic BOOLEAN NOT NULL,
    CONSTRAINT fk_fact_synthetic_expense FOREIGN KEY (expense_id) REFERENCES raw_synthetic_expense(expense_id),
    CONSTRAINT fk_fact_synthetic_matched_contract FOREIGN KEY (matched_contract_id) REFERENCES raw_synthetic_contract(contract_id),
    CHECK (is_synthetic = TRUE)
);

CREATE TABLE IF NOT EXISTS fact_synthetic_approval (
    source_record_id CHAR(64) PRIMARY KEY,
    expense_id VARCHAR(20) NOT NULL UNIQUE,
    request_timestamp_utc DATETIME(6) NOT NULL,
    manager_approval_timestamp_utc DATETIME(6) NOT NULL,
    finance_approval_timestamp_utc DATETIME(6) NOT NULL,
    payment_timestamp_utc DATETIME(6) NOT NULL,
    approval_cycle_hours DECIMAL(12,2) NOT NULL,
    request_to_payment_hours DECIMAL(12,2) NOT NULL,
    approval_sla_hours DECIMAL(12,2) NOT NULL,
    approval_sla_breached BOOLEAN NOT NULL,
    scenario_id VARCHAR(100) NOT NULL,
    record_origin VARCHAR(100) NOT NULL,
    is_synthetic BOOLEAN NOT NULL,
    CONSTRAINT fk_fact_approval_expense FOREIGN KEY (expense_id) REFERENCES raw_synthetic_expense(expense_id),
    CHECK (request_timestamp_utc < manager_approval_timestamp_utc),
    CHECK (manager_approval_timestamp_utc < finance_approval_timestamp_utc),
    CHECK (finance_approval_timestamp_utc < payment_timestamp_utc),
    CHECK (is_synthetic = TRUE)
);

