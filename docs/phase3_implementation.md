# Phase 3 implementation notes

## Pre-implementation discrepancy

The Phase 3 prompt described MySQL ingestion as complete. Repository inspection showed otherwise:

- `README.md` explicitly stated that MySQL loading had not been implemented.
- `sql/ddl/proposed_schema.sql` was labelled as a design artifact and defined only an outline.
- No MySQL ingestion module, connection configuration, or load report existed.
- This host has neither a `mysql` command-line client nor Docker, and no MySQL connection variables are configured.

Phase 3 implemented the missing MySQL 8.0 DDL and idempotent loader. Live ingestion was subsequently verified against MySQL Server 8.0.46.

## Implemented flow

1. `src.synthetic.generate_phase3` reads the versioned scenario config and fixed seed.
2. It reuses cached Frankfurter responses, or fetches them with retry and an identifying User-Agent when the cache is absent.
3. It generates separate department, vendor, contract, expense, approval-event, and survey sources.
4. It converts amounts and evaluates contract relationships without joining to DEFRA records.
5. `src.validation.validate_phase3` independently recomputes foreign keys, contract matches, FX conversions, event order, currency counts, lineage labels, and quarantine counts.
6. `src.ingestion.load_mysql` applies deterministic upserts. With `--verify-idempotency`, it loads twice and fails if table row counts change.

## FX source

Frankfurter's official project describes the public endpoint at [api.frankfurter.dev](https://api.frankfurter.dev) and its v2 API as daily blended reference rates. The implementation requests explicit date ranges using `/v2/rates?base=...&quotes=GBP&from=...&to=...`. Cached observations cover 2025-02-19 through 2026-02-28, providing a ten-day lookback before the expense period.

Rates are direct original-currency-to-GBP quotes. The generator does not invert a GBP-based quote, reducing conversion ambiguity.

## Reproducibility

- Configuration and random seed are versioned in `config/phase3_synthetic.json`.
- Identifiers are deterministic hashes or deterministic sequence IDs.
- Historical API responses are immutable inputs for ordinary reruns.
- The automated test regenerates all synthetic files in a temporary directory using offline caches and compares SHA-256 hashes.
- The generation manifest records row counts and hashes for every delivered source and processed file.

## Live MySQL result

The database `enterprise_spend` contained the 10 Phase 3 tables and all were empty before the verified load. The loader did not execute DDL.

| Table | First load | Second load |
|---|---:|---:|
| `raw_synthetic_department` | 12 | 12 |
| `raw_synthetic_vendor` | 125 | 125 |
| `raw_synthetic_contract` | 200 | 200 |
| `raw_synthetic_expense` | 5,000 | 5,000 |
| `raw_synthetic_approval_event` | 20,000 | 20,000 |
| `raw_synthetic_vendor_satisfaction` | 300 | 300 |
| `raw_fx_rate` | 750 | 750 |
| `fact_synthetic_spend` | 5,000 | 5,000 |
| `fact_synthetic_approval` | 5,000 | 5,000 |
| `pipeline_load_run` | 1 | 1 |

Source and database totals matched exactly. The total converted spend was £1,160,936,638.63 on both loads. FX arithmetic, latest-rate date rules, raw-to-fact completeness, fact-to-raw integrity, approval sequences, and approval-fact completeness all returned zero exceptions. The second run did not change counts or totals.

## Failure and fix

The first live attempt failed with MySQL error 1048 because `fx_cache_file` was `NULL` for GBP rows. GBP uses an identity rate and had no external cache filename; the generic loader converted the empty string to `NULL`, conflicting with the `NOT NULL` column.

The fix stores `GBP_IDENTITY` as explicit lineage. Validation now rejects a blank FX cache reference and checks that every GBP row uses `GBP_IDENTITY`. The deprecated connector server-version call was also replaced with the supported property. The successful retry's pre-load counts were all zero, confirming the failed transaction had not partially committed.

## Secure verification command

```powershell
$env:PYTHONPATH="$env:APPDATA\Python\Python313\site-packages"
python -m src.ingestion.verify_mysql_phase3
Remove-Item Env:PYTHONPATH
```

The command prompts for the password without echoing or persisting it. Credentials remain outside version control.
