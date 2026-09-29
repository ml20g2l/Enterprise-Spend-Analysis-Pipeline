# Proposed architecture

## Layer flow

```mermaid
flowchart LR
    A[DEFRA monthly CSVs\nreal public GBP] --> B[raw_defra_transactions]
    C[Synthetic expense files\nfictional organisation EUR/USD] --> D[raw_synthetic_expenses]
    E[Frankfurter API\nreal reference rates] --> F[raw_fx_rates]
    G[Synthetic contract master] --> H[raw_synthetic_contracts]
    I[Synthetic approval JSON] --> J[raw_synthetic_approval_events]

    B --> K[stg_defra_transactions]
    D --> L[stg_synthetic_expenses]
    F --> M[stg_fx_rates]
    H --> N[stg_synthetic_contracts]
    J --> O[stg_synthetic_approval_events]

    K --> P[int_defra_spend_review]
    L --> Q[int_synthetic_expenses_gbp]
    M --> Q
    N --> R[int_synthetic_contract_match]
    Q --> R
    O --> S[int_synthetic_approval_cycle]

    P --> T[fact_defra_spend\nREAL ONLY]
    Q --> U[fact_synthetic_spend\nSYNTHETIC ONLY]
    R --> U
    S --> V[fact_synthetic_approval\nSYNTHETIC ONLY]

    T --> W[DEFRA procurement marts]
    U --> X[Synthetic spend/compliance marts]
    V --> Y[Synthetic operations marts]
```

## Responsibilities

| Layer | Purpose | Mutability and controls |
|---|---|---|
| Raw | Lossless source representation plus file/API lineage. | Append/idempotent load; no source-value correction. Raw primary key is source-scoped. |
| Staging | Canonical names, typed dates/amounts, trimming policy, quality statuses. | One model per source; quarantined rows excluded from accepted staging but retained in a rejection table. |
| Intermediate | Duplicate review, GBP conversion, contract matching, and approval-cycle derivations. | Business logic remains source-specific. DEFRA blanks never inherit synthetic contracts. |
| Mart | Stable fact/dimension grains for analysis. | Separate real and synthetic facts. Shared dimensions use source-scoped natural keys. |

## Idempotency and lineage

1. Register a file by SHA-256 and controlled `source_month`.
2. Generate `source_record_id` deterministically from source file, row number, and source-value hash.
3. Load with a unique constraint on `source_record_id`; a repeated identical run becomes a no-op.
4. If a publisher replaces a file under the same name, its file hash changes. Store a new ingestion version and require an explicit supersession decision instead of silently overwriting history.
5. Carry `source_record_id` into every downstream fact so any metric can trace to file and row.

## Quarantine boundary

Hard failures are invalid/missing transaction date, invalid/missing numeric amount, missing lineage, or an unexpected schema that cannot be mapped unambiguously. Soft warnings include source-month discrepancies, exact repeats, repeated business identifiers, blank contract/project/transaction references, non-positive amounts, and values below the publication threshold. Warnings stay in the accepted population with flags.

