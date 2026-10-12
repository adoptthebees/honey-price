# Plan for the sources and the API of the market data

This plan has the work after the FAOSTAT part. The specification is `DOCS/SPECS/2026_10_11_MARKET_DATA_DESIGN.md`. The plan for the FAOSTAT part is `2026_10_11_MARKET_DATA_PLAN.md`.

## Purpose

Read each source into the database. Keep the history of each row. Show the data to a visitor from the page layer only. Each request of a visitor must get its response in 100 ms or less.

## Rules for all tasks

- Write all code in Go in the directory `backend/` of the Exchange Honey repository. Do not add a dependency.
- Use PostgreSQL in each test. Use the port 5433 only. Do not replace PostgreSQL with other software in a test.
- Write each test before the code. Break the code on purpose in one line. Make sure that a test gives a failure.
- Do not change a migration that a server uses. A migration that no server uses can change.
- Do not put a key in the repository. Do not write a key in a message of the server.

## Tasks

| Task | Result | Test |
| --- | --- | --- |
| 1. Role of the visitor and the read of the page layer | The role `eh_visitor`, the package `market` and the lock for the change of a release | `TestRead_*`, `TestVisitorRole_*` |
| 2. Framework for sources | The interface `Source`, the loader `LoadHistory`, `Update` for many sources and the page table `source_note` | `TestLoadHistory_*`, `TestUpdate_*`, `TestDefaultSources_*` |
| 3. Parsers | One package for each file format: `ers`, `nass`, `census`, `hts`, `schedb`, `remedy` and `ams` | The tests of each package |
| 4. Adapters | One `Source` for each of the 7 sources, with its migration, its `clean` rows and its page tables | `TestERS_*`, `TestNASS_*`, `TestCensus_*`, `TestTariff_*`, `TestRemedies_*`, `TestAMS_*` |
| 5. Seed from database v5 | The command `marketdata seed` and the seed of the AMS and Census sources | `TestV5Query_*`, `TestAMS_seed*`, `TestCensus_Seed*` |
| 6. Routes of the API | 25 routes in `/api/v1/market` | `TestMarket*`, `TestPrices*`, `TestUSSupply*`, `TestUSPorts*`, `TestTariff*`, `TestOverview*` |

## Task 2: Framework for sources

A source has the methods `Name`, `Codes`, `Update`, `BuildClean` and `PageTables`. `Update` reads the files that changed into the `raw` layer. `BuildClean` makes the `clean` rows from the open rows. `PageTables` gives the tables for the schema `page_next`.

`LoadHistory` is the only code that writes to a `raw` table. It keeps the previous row when a value changes. It closes a row that the file does not have. It stops with `ErrFormat` and changes nothing when a file has two rows with one key.

The hash of a row is the `md5` of the text of a record. Thus NULL, an empty text and a separator in a text give different hashes. The hash does not have the line number of the file.

`Update` reads all the sources. A source that has a failure does not stop the other sources. The command builds a release from the last good download of each source. It ends with the code 1 and the errors.

The date of a file is only the first test for a change. After the download, the hash of the file gives the result of the test. A new date on the same bytes adds no manifest and no release. The CDN of Census sends such dates for 5 to 12 of the 48 files in each test.

## Task 4: Adapters

| Source | Name and codes | Manifest names | Page tables |
| --- | --- | --- | --- |
| FAOSTAT | `faostat`: `QCL`, `PP`, `TCL`, `TM` | `faostat.<code>` | `production_country_year`, `production_world_year`, `trade_country_year`, `trade_world_year`, `trade_lane_year` |
| ERS | `ers`: `ERS` | `ers.ERS` | `us_series_year` |
| NASS | `nass`: `NASS` | `nass.<report date>` for the publications `Honey` and `Honey - Final Estimates` | `us_supply_year` |
| Census | `census`: `PORTHS6MM`, `PORTHS6XM` | `census.<code>.<YYMM>`, `census.country`, `census.port` | `us_port_month` |
| Tariff | `tariff`: `HTS`, `SCHEDB` | `tariff.HTS`, `tariff.SCHEDB` | `tariff_line` |
| Remedies | `remedy`: `REMEDY` | `remedy.REMEDY`, `remedy.FR.<case>` | `remedy_rate` |
| AMS | `ams`: `AMS` | `ams`, `ams.v5` | `quote_month`, `quote_index_month`, `us_import_month`, `regional_condition` |

The release build makes `release_info` and `source_note` for all sources. It gives the role `eh_visitor` the right to read each table.

## Task 5: Seed from database v5

The command `marketdata seed --v5 <file>` reads database v5 with the program `sqlite3`. The server does not use the program. The seed has all the AMS issues and all the Census months of database v5. The update then reads the last AMS issue and the last 24 months of Census from the sources. The seed makes no release. Start `marketdata update` after the seed.

The seed does not copy two defects of database v5: the 12 `Grand Total` import rows and the 112 export rows with no month. It corrects the "floral source" of one Brazil quote row. In the first format, the column `month_cif_value_usd` has the CIF value, and the seed puts the freight and insurance in the column for them. The seed does not remove the rows that have the same content as a different row. The specification lists the defects in the section "Defects of the AMS rows of database v5".

## Task 6: Routes of the API

| Area | Routes |
| --- | --- |
| FAOSTAT | `release`, `production/countries`, `production/countries/{areaCode}`, `production/world`, `trade/countries`, `trade/countries/{areaCode}`, `trade/world`, `trade/lanes` |
| Summary | `overview`, `sources` |
| US supply | `us/supply`, `us/supply/states`, `us/series`, `us/series/attributes` |
| US ports | `us/ports`, `us/ports/partners`, `us/ports/series` |
| Tariff and remedies | `tariff`, `remedies` |
| Prices | `prices/quotes`, `prices/filters`, `prices/index`, `prices/us/imports`, `prices/us/imports/months`, `prices/conditions` |

The test `TestMarket_eachDocumentedRouteIsMountedAndNoOtherOne` reads the router that the server uses. The test gives a failure when a route has an incorrect path.

## Not in this plan

- The Census HS10 API. A key is necessary, and the key is not in this repository.
- The sources IBGE and Eurostat.
- The approval of a trade remedy rate. A person must agree to each rate.
- The pages of the frontend.
- The directory for the AMS PDF files in production. Set `EH_PDF_DIR`.
