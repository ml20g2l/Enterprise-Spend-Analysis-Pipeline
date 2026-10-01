# Source provenance and reuse

The local files are attributed to the Department for Environment, Food & Rural Affairs (DEFRA). The official [DEFRA departmental spending collection](https://www.gov.uk/government/collections/defra-departmental-spending-over-25000) lists all 12 source months used here and describes the publications as monthly departmental spending over £25,000.

`reports/source_inventory.csv` records the controlled source month, official publication landing URL, local path, byte size, SHA-256, encoding, row count, schema, and observed date coverage for every file. The test suite verifies the preserved files under `data/raw/defra/` against these recorded hashes. This proves repository source preservation, but it does **not** prove byte identity with the current remote GOV.UK download; that status is explicitly `not_checked`.

GOV.UK states that most content is published under the [Open Government Licence](https://www.gov.uk/help/terms-conditions), subject to its conditions and exceptions. The inventory links to [OGL v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/). Before publicly redistributing the raw CSVs, check each publication for a contrary notice and include the required attribution. A lower-risk repository option is to publish hashes, landing-page URLs, and download instructions while excluding raw files.
