# GitHub portfolio contents

The repository is intentionally curated for reviewers who want to understand the architecture, reproduce the controls, and inspect the final deliverables.

## Included

- application code, SQL, dbt models/tests, Airflow DAGs, and configuration
- preserved DEFRA open-data files in one canonical location
- cached public FX responses required for deterministic offline generation
- schemas, architecture, data dictionaries, business rules, and lineage notes
- concise machine-readable and Markdown validation evidence
- clone-safe regression tests
- the final Power BI report and three rendered dashboard images
- licence/source attribution and credential-free setup examples

## Excluded

- duplicate source files at repository root
- reproducible synthetic and processed row-level data
- quarantine outputs, command logs, dbt build artefacts, Airflow logs and runs
- local passwords, `.env` files, virtual environments, and user profiles
- the temporary HTML dashboard prototype and Power BI PDF exports
- editor, cache, lock, and operating-system files

These exclusions reduce repository noise and avoid presenting generated data as hand-authored evidence. The tracked config, FX cache, code, and manifest are sufficient to recreate the synthetic scenario and validate its hashes.
