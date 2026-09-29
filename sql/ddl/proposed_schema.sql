-- DESIGN ARTIFACT ONLY. Not executed in this phase.
-- MySQL-compatible outline; detailed types/indexes will be reviewed before deployment.

CREATE TABLE raw_ingestion_run (
    ingestion_run_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    source_system VARCHAR(100) NOT NULL,
    source_file VARCHAR(255),
    source_month CHAR(7),
    file_sha256 CHAR(64),
    ingestion_timestamp TIMESTAMP(6) NOT NULL,
    row_count INT,
    run_status VARCHAR(30) NOT NULL,
    UNIQUE KEY uq_raw_file_version (source_system, source_file, file_sha256)
);

CREATE TABLE raw_defra_transactions (
    source_record_id CHAR(64) PRIMARY KEY,
    ingestion_run_id BIGINT NOT NULL,
    source_file VARCHAR(255) NOT NULL,
    source_month CHAR(7) NOT NULL,
    source_row_number INT NOT NULL,
    exact_record_hash CHAR(64) NOT NULL,
    source_payload JSON NOT NULL,
    FOREIGN KEY (ingestion_run_id) REFERENCES raw_ingestion_run (ingestion_run_id),
    UNIQUE KEY uq_defra_file_row (ingestion_run_id, source_row_number)
);

CREATE TABLE stg_defra_transactions (
    source_record_id CHAR(64) PRIMARY KEY,
    transaction_date DATE NOT NULL,
    entity VARCHAR(255),
    supplier VARCHAR(500),
    transaction_number VARCHAR(255),
    amount_gbp DECIMAL(20,2) NOT NULL,
    contract_number VARCHAR(255),
    exact_duplicate_group_id CHAR(64),
    business_duplicate_group_id CHAR(64),
    quality_status VARCHAR(30) NOT NULL,
    FOREIGN KEY (source_record_id) REFERENCES raw_defra_transactions (source_record_id)
);

-- Real and synthetic facts remain separate. Shared dimensions must namespace
-- natural keys by source_dataset; synthetic contract keys never join to DEFRA.
CREATE TABLE fact_defra_spend (
    defra_spend_key BIGINT AUTO_INCREMENT PRIMARY KEY,
    source_record_id CHAR(64) NOT NULL,
    transaction_date_key INT NOT NULL,
    supplier_key BIGINT,
    department_key BIGINT,
    category_key BIGINT,
    amount_gbp DECIMAL(20,2) NOT NULL,
    transaction_number VARCHAR(255),
    duplicate_review_status VARCHAR(30) NOT NULL,
    UNIQUE KEY uq_fact_defra_source_record (source_record_id)
);

CREATE TABLE fact_synthetic_spend (
    synthetic_spend_key BIGINT AUTO_INCREMENT PRIMARY KEY,
    scenario_id VARCHAR(100) NOT NULL,
    synthetic_expense_id VARCHAR(255) NOT NULL,
    transaction_date_key INT NOT NULL,
    original_currency_code CHAR(3) NOT NULL,
    original_amount DECIMAL(20,2) NOT NULL,
    applied_fx_rate DECIMAL(20,10) NOT NULL,
    applied_fx_rate_date DATE NOT NULL,
    amount_gbp DECIMAL(20,2) NOT NULL,
    contract_key BIGINT,
    UNIQUE KEY uq_synthetic_expense (scenario_id, synthetic_expense_id)
);

