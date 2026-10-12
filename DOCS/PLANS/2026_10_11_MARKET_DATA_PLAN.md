# Plan for the FAOSTAT part of the market data

## Purpose

This plan makes step 1 of the specification `2026_10_11_MARKET_DATA_DESIGN.md` for FAOSTAT only. The result is a command that reads the 4 FAOSTAT archives and keeps the rows with their history. It builds the `clean` layer and the page tables, and it puts a new release live in one transaction.

The plan has 7 tasks. Each task has tests and gives a result that works. The other sources, the API and AMS each have a plan.

## Rules for the work

- Work in the directory `backend/` of the repository `~/stb/exchange-honey`. The repository has other work that is not complete. Add new files only. Do not change a file that is there.
- Write all code in Go. Use the standard code of Go first. Add no new dependency.
- Add the database change as a new numbered migration file. Do not change a migration that is in use.
- Test with the database that `internal/testdb` gives. Do not replace the database in a test.
- Use only the database on port 5433. The database on port 5432 is for "Adopt The Bees". Do not use it.
- Do not write a database URL in the output of the command.
- Before the work is complete, start `go test ./...`, `go vet ./...` and `gofmt -l .` in `backend/`. The tests and `go vet` must give no error. `gofmt -l .` must give no output.

Set `EH_TEST_DATABASE_URL` to start the tests:

```bash
# The password is in the file backend/compose.yaml of the Exchange Honey repository.
export EH_TEST_DATABASE_URL='postgres://eh:<password>@127.0.0.1:5433/postgres?sslmode=disable'
```

## Steps of each task

1. Write the tests. Name each test for the break that it catches. Write the correct values in the test. Do not get them from the code that you test.
2. Start the tests. Make sure that they give an error for the correct cause.
3. Write only the code that makes the tests give no error.
4. Start the tests again. Make sure that they give no error.
5. Start `gofmt -l .` and `go vet ./...`.

## Files

| Path in `backend/` | Content |
| --- | --- |
| `internal/db/migrations/0005_market_data.sql` | The schemas and the tables of task 1 |
| `internal/marketdata/schema_test.go` | Tests of the tables |
| `internal/marketdata/reader.go` | `Dataset`, `Observation`, `Reader` |
| `internal/marketdata/fetch.go` | `Fetcher`, `Download` |
| `internal/marketdata/store.go` | `Load`, `Changed`, `RecordFailure` |
| `internal/marketdata/clean.go` | `BuildClean` |
| `internal/marketdata/page.go` | `BuildPage` |
| `internal/marketdata/release.go` | `Build`, `Rollback`, `LiveRelease` |
| `internal/marketdata/update.go` | `Update` |
| `cmd/marketdata/main.go` | The command `marketdata update` |

Each `.go` file has a test file. Its name is the name of the file with `_test` before `.go`.

## Task 1: Migration

Make the file `0005_market_data.sql`. Its number must be the next number after the last file in the directory.

```sql
-- +goose Up
CREATE SCHEMA raw;
CREATE SCHEMA clean;
CREATE SCHEMA meta;

CREATE TABLE meta.manifest (
    id            bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source        text        NOT NULL,
    url           text        NOT NULL,
    retrieved_at  timestamptz NOT NULL DEFAULT now(),
    last_modified timestamptz,
    sha256        text        NOT NULL DEFAULT '',
    bytes         bigint      NOT NULL DEFAULT 0,
    rows_scanned  bigint      NOT NULL DEFAULT 0,
    rows_kept     bigint      NOT NULL DEFAULT 0,
    status        text        NOT NULL CHECK (status IN ('ok', 'error')),
    error         text        NOT NULL DEFAULT ''
);
CREATE INDEX manifest_source ON meta.manifest (source, id DESC);

CREATE TABLE meta.release (
    id          bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    status      text        NOT NULL CHECK (status IN ('building', 'live', 'failed', 'retired')),
    started_at  timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    checks      jsonb       NOT NULL DEFAULT '[]',
    manifests   bigint[]    NOT NULL DEFAULT '{}'
);
CREATE UNIQUE INDEX release_one_live ON meta.release ((true)) WHERE status = 'live';

CREATE TABLE raw.faostat_observation (
    id           bigint  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dataset      text    NOT NULL,
    area_code    text    NOT NULL,
    partner_code text    NOT NULL DEFAULT '',
    item_code    text    NOT NULL,
    element_code text    NOT NULL,
    year         integer NOT NULL,
    months_code  text    NOT NULL DEFAULT '',
    area         text    NOT NULL,
    partner      text    NOT NULL DEFAULT '',
    item         text    NOT NULL,
    element      text    NOT NULL,
    months       text    NOT NULL DEFAULT '',
    unit         text    NOT NULL,
    value        numeric,
    flag         text    NOT NULL DEFAULT '',
    note         text    NOT NULL DEFAULT '',
    source_row   bigint  NOT NULL,
    row_hash     text    NOT NULL,
    valid_from   bigint  NOT NULL REFERENCES meta.manifest (id),
    valid_to     bigint  REFERENCES meta.manifest (id)
);
CREATE UNIQUE INDEX faostat_observation_current ON raw.faostat_observation
    (dataset, area_code, partner_code, item_code, element_code, year, months_code)
    WHERE valid_to IS NULL;

CREATE TABLE clean.faostat_honey (
    dataset      text    NOT NULL,
    class        text    NOT NULL,
    area_code    text    NOT NULL,
    area         text    NOT NULL,
    partner_code text    NOT NULL DEFAULT '',
    partner      text    NOT NULL DEFAULT '',
    year         integer NOT NULL,
    months_code  text    NOT NULL DEFAULT '',
    element_code text    NOT NULL,
    direction    text    NOT NULL DEFAULT '',
    measure      text    NOT NULL,
    value        numeric NOT NULL,
    unit         text    NOT NULL,
    flag         text    NOT NULL DEFAULT '',
    is_group     boolean NOT NULL,
    is_zero      boolean NOT NULL
);
```

| Test | Break that it catches |
| --- | --- |
| `TestSchema_oneOpenRowForEachKey` | No unique index. Two open rows with one key make the page build add the value 2 times. |
| `TestSchema_aClosedRowAndAnOpenRowCanShareAKey` | An index with no condition on `valid_to`. The system cannot keep the history of a value. |
| `TestSchema_oneLiveReleaseAtATime` | No index on `meta.release`. Two releases can be live. |

## Task 2: Reader

The reader opens the file in the zip of an archive and compares the header with the correct header. It keeps only the rows of the items 1181, 1182 and 1183. It gives each row with its line number in the file. The header is line 1. This number is the same as the number in database v5.

```go
type Dataset struct {
	Code    string   // QCL, PP, TCL or TM
	Archive string   // file name at FAO
	Member  string   // CSV file in the zip
	Header  []string // the exact header that the reader accepts
}

var Datasets map[string]Dataset // keys: QCL, PP, TCL, TM

type Observation struct {
	Dataset, AreaCode, Area, PartnerCode, Partner string
	ItemCode, Item, ElementCode, Element          string
	Year                                          int
	MonthsCode, Months, Unit                      string
	Value                                         string // empty when the source has no value
	Flag, Note                                    string
	SourceRow                                     int64
}

var ErrFormat error // the file has a new format

func OpenArchive(ra io.ReaderAt, size int64, ds Dataset) (*Reader, error)
func (r *Reader) Next() bool
func (r *Reader) Observation() Observation
func (r *Reader) Scanned() int64 // the data rows that the reader looked at
func (r *Reader) Err() error
func (r *Reader) Close() error
```

For `TM`, the field `AreaCode` is the reporter and `PartnerCode` is the partner. For `PP`, the fields `MonthsCode` and `Months` have the month. The other datasets have them empty.

| Test | Break that it catches |
| --- | --- |
| `TestReader_keepsOnlyTheThreeItems` | An incorrect filter. A row of a different item goes into the database. |
| `TestReader_numbersRowsByLine` | A count from 0, or a count of records. The source of a row is then incorrect. |
| `TestReader_keepsAnEmptyValueAsNoValue` | A change of an empty value to 0. |
| `TestReader_readsAQuotedFieldWithAComma` | A cut at each `,`. A name such as "Korea, Republic of" breaks. |
| `TestReader_readsPricesAndTheTradeMatrix` | An incorrect column for the month, the partner or the note. |
| `TestReader_aChangedHeaderStopsWithErrFormat` | A read with no error of a file with a new format. |
| `TestReader_aMissingMemberStopsWithErrFormat` | A zip that does not have the correct file. |
| `TestReader_aBadYearStopsWithErrFormat` | A year that is not a number. |

## Task 3: Download

The code in `fetch.go` sends a HEAD request to get the `Last-Modified` value. It downloads an archive to a temporary file and finds the SHA-256 hash when it writes. The code that uses it removes the file.

```go
type Fetcher struct{ Client *http.Client }

func FAOURL(base string, ds Dataset) string // the base address plus the archive name

type Download struct {
	Path         string
	Size         int64
	SHA256       string    // hexadecimal
	LastModified time.Time // the zero time when the server sends none
}

func (f *Fetcher) Head(ctx context.Context, url string) (time.Time, error)
func (f *Fetcher) Download(ctx context.Context, url, dir string) (Download, error)
```

| Test | Break that it catches |
| --- | --- |
| `TestHead_readsLastModified` | An incorrect date format. The test for a change always gives "new". |
| `TestHead_noHeaderGivesTheZeroTime` | An error when the server sends no header. |
| `TestDownload_hashesTheBytesThatItWrites` | A hash of incorrect bytes. The test uses the known hash of `abc`. |
| `TestDownload_aServerErrorStopsAndLeavesNoFile` | A part of a file that stays after an error. |

## Task 4: Store

`Load` reads an archive and writes its rows to `raw.faostat_observation` in one transaction. The key of a row is the dataset, the area, the partner, the item, the element, the year and the months code. The function `Changed` tells if the source has a new file. The function `RecordFailure` writes a manifest row with the status "error".

```go
type Archive struct {
	URL          string
	ReaderAt     io.ReaderAt
	Size         int64
	SHA256       string
	LastModified time.Time
}

type LoadResult struct {
	Manifest                               int64
	Scanned, Kept, New, Changed, Withdrawn int64
}

func Load(ctx context.Context, pool *pgxpool.Pool, ds Dataset, a Archive) (LoadResult, error)
func Changed(ctx context.Context, q db.Querier, ds Dataset, lastModified time.Time, sha256 string) (bool, error)
func RecordFailure(ctx context.Context, q db.Querier, ds Dataset, url string, cause error) error
```

The function `Load` follows these rules:

1. Set `statement_timeout` to 0 in the transaction. The `Load` function is longer than 15000 ms.
2. Copy the rows to a temporary table as text. Then change them with SQL.
3. A row with the same key and the same `row_hash` stays as it is.
4. A row with the same key and a different `row_hash` gets `valid_to` set to the manifest. A new row with the new values gets `valid_from` set to the manifest.
5. An open row of the same dataset that has no key in the archive gets `valid_to` set to the manifest.
6. The `row_hash` is the MD5 hash of the value, the flag, the unit, the note and the names.

| Test | Break that it catches |
| --- | --- |
| `TestLoad_storesEachKeptRow` | A row that the code does not store. A value such as 1234.5 must go into the database as a number. |
| `TestLoad_theSameArchiveAgainChangesNothing` | A new version for a row that is the same. |
| `TestLoad_aChangedValueKeepsThePreviousRow` | A change of the previous row. The system does not keep the history. |
| `TestLoad_aRowThatLeavesTheArchiveIsClosed` | A row that stays open after FAO removes it. |
| `TestLoad_aFormatErrorChangesNothing` | A read that stops in the middle and keeps some rows. |
| `TestLoad_pricesKeepOneRowForEachMonth` | A key with no months code. The prices of the months replace each other. |
| `TestLoad_aDatasetDoesNotCloseTheRowsOfAnother` | A close of rows with no filter on the dataset. |
| `TestChanged_comparesLastModifiedAndHash` | An incorrect result for: no manifest, same date, new date, no date with the same hash. |
| `TestRecordFailure_writesAnErrorManifest` | A failure that has no record. |

## Task 5: Clean layer and page tables

`BuildClean` empties `clean.faostat_honey` and fills it from the open rows of item 1182 that have a value. It sets `is_group` for the area codes from 5000 and for the code 351. It sets `is_zero` for the value 0. The class is `production` for `QCL`, `producer_price` for `PP` and `trade_flow` for `TCL` and `TM`.

`BuildPage` makes the schema `page_next` with these tables and indexes:

| Table | Columns | Indexes |
| --- | --- | --- |
| `production_country_year` | `area_code`, `country`, `year`, `tonnes`, `flag` | `(year)`, `(area_code, year)` |
| `trade_country_year` | `area_code`, `country`, `year`, `direction`, `tonnes`, `value_usd_thousand`, `unit_value_usd_tonne` | `(year, direction)`, `(area_code, year)` |
| `trade_lane_year` | `reporter_code`, `reporter`, `partner_code`, `partner`, `year`, `direction`, `tonnes`, `value_usd_thousand`, `unit_value_usd_tonne` | `(reporter_code, year, direction)`, `(partner_code, year, direction)` |
| `release_info` | `release_id`, `built_at` | none |

```go
func BuildClean(ctx context.Context, q db.Querier) error
func BuildPage(ctx context.Context, q db.Querier, releaseID int64) error
```

The unit value is the value in 1000 US dollars, times 1000, divided by the tonnes. It is null when the tonnes are 0 or when one of the two numbers is not there.

`BuildPage` keeps a row that has a quantity and no value. It keeps a row that has a value and no quantity. Each number that is not there is null.

| Test | Break that it catches |
| --- | --- |
| `TestBuildClean_dropsNullValuesAndMarksZeroAndGroupRows` | A null value in `clean`. A group row that counts as a country. |
| `TestBuildClean_keepsOnlyHoney` | A row of item 1181 or 1183 in the honey table. |
| `TestBuildClean_aSecondBuildReplacesTheFirst` | A table that has more rows after each build. |
| `TestBuildClean_readsOnlyOpenRows` | A closed version or a removed row in `clean`. |
| `TestBuildPage_productionHasCountryRowsOnly` | A World row that adds to the countries. |
| `TestBuildPage_tradePairsQuantityAndValue` | An incorrect pair. 10 tonnes and a value of 25 in 1000 US dollars must give 2500 US dollars for each tonne. |
| `TestBuildPage_zeroQuantityGivesNoUnitValue` | An error from 0 tonnes or from a value that is not there. |
| `TestBuildPage_partnerRowsHaveNoGroupsAndKeepEachSideApart` | A group row in the table of partners. A reporter and its partner that become one row. |
| `TestBuildPage_recordsTheReleaseNumber` | A page that cannot tell which release it came from. |
| `TestBuildPage_aSecondBuildReplacesTheFirst` | A `page_next` that stays from the first build. |
| `TestBuildPage_hasTheIndexesOfThePage` | No index for a filter of the page. |

## Task 6: Release build and rollback

`Build` makes a release. It gets a lock in the database. Thus 2 builds do not work at the same time. When a different build has the lock, `Build` gives the error `ErrBusy`. When it has the lock, `Build` adds a `meta.release` row with the status "building".

Then `Build` does the work in one transaction. The transaction starts `BuildClean` and `BuildPage`, and then it does the release tests. When a test gives an error, the transaction ends with no commit. Thus `page_next` is not there and `clean` is as it was. `Build` sets the status "failed" and gives the error `ErrCheckFailed`. The live release does not change.

When all tests give no error, the same transaction changes the live release. It removes `page_prev`. It changes the name of `page` to `page_prev` and the name of `page_next` to `page`. It also sets the statuses of the releases. The commit makes the new release live.

The change of the live release locks `page.release_info`. A reader that reads this table first holds a lock on it until its request ends. Thus the change waits for the request, and the request reads one release. The server finds the name `page` again for each statement. A reader that does not read `release_info` first can see tables of two releases. The tests of the change show this.

```go
type Check struct {
	Name   string `json:"name"`
	OK     bool   `json:"ok"`
	Detail string `json:"detail"`
}

var (
	ErrBusy              error // another Build or Rollback holds the lock
	ErrCheckFailed       error // a release test gave an error
	ErrNothingToRollBack error // there is no page_prev
)

func Build(ctx context.Context, pool *pgxpool.Pool) (releaseID int64, checks []Check, err error)
func Rollback(ctx context.Context, pool *pgxpool.Pool) error
func LiveRelease(ctx context.Context, q db.Querier) (id int64, ok bool, err error)
```

These are the release tests. Each one has a name such as `has_rows:trade_lane_year`.

1. Each page table of task 5 has 1 row or more.
2. No page table has a value below 0.
3. When a live release is there, each page table has 90 percent or more of the rows of the live release.

| Test | Break that it catches |
| --- | --- |
| `TestBuild_theFirstReleaseGoesLiveWithNoPreviousSchema` | A change of the name of a schema that is not there. An end time that is the start time of the transaction. |
| `TestBuild_theSecondReleaseKeepsThePreviousSchema` | No schema to go back to. |
| `TestBuild_aFailedTestKeepsTheLiveReleaseAsItIs` | A bad release that goes live. |
| `TestBuild_aSmallArchiveIsRefused` | A cut archive that removes most rows from the page. |
| `TestBuild_aBuildThatIsRunningRefusesASecondOne` | No lock. |
| `TestRollback_putsThePreviousReleaseBack` | An incorrect status or an incorrect schema after the rollback. |
| `TestRollback_withNoPreviousReleaseIsAnError` | A change of the name of a schema that is not there. |
| `TestSwap_aReaderNeverSeesTwoReleasesDuringBuilds` | A change of release that a reader sees in the middle of its request. |
| `TestSwap_aReaderNeverSeesTwoReleasesDuringRollbacks` | The same break, with 200 changes of release. |
| `TestSwap_aConnectionThatReadBeforeTheSwapReadsTheNewRelease` | A saved plan that reads the tables of the release before the change. |

The 2 tests of the change use readers that follow the rule. One reader reads 2 tables in 2 statements, and the transaction waits between them. One reader reads 2 tables in one statement that the server reads again each time. Each test gives an error when the lock on `release_info` is weaker.

## Task 7: Command

`Update` does the work of the command. For each dataset it gets the `Last-Modified` value. When `Changed` gives no, it goes to the next dataset. When `Changed` gives yes, it downloads the archive. When the hash of the archive is the hash of the last download, it removes the temporary file and goes to the next dataset. For each other archive, it reads the archive into the database and removes the temporary file.

Then `Update` starts `Build` when no release is live. It starts `Build` also when a source has a download that the live release does not use. Thus the next start makes the release after a build stops. The command does not download a file again.

A failure in one dataset writes an error manifest and stops the work with an error. The data that `Update` read before the failure stay in the database. The command reads `EH_DATABASE_URL` and applies the migrations. The option `--file QCL=/path` reads a local archive and does not download. The option `--force` reads each archive again. The command `marketdata rollback` starts `Rollback`.

```go
type Config struct {
	Fetcher *Fetcher
	BaseURL string            // the address of the FAO bulk directory
	Files   map[string]string // dataset code to a local archive; skips the network
	TempDir string
	Force   bool // load again when the files did not change
}

type Result struct {
	Loaded    map[string]LoadResult // the datasets that Update read
	Unchanged []string              // the datasets that Update did not read
	Release   int64                 // the release that Update built; 0 when none
	Checks    []Check               // the tests of that release
}

func Update(ctx context.Context, pool *pgxpool.Pool, cfg Config) (Result, error)
```

| Test | Break that it catches |
| --- | --- |
| `TestUpdate_firstRunLoadsAndGoesLive` | A broken link between the steps. A file that stays in the temporary directory. |
| `TestUpdate_secondRunDownloadsNothingAndAddsNoRelease` | A new download of 740 MB when the files are the same. The test counts the GET requests of the test server. |
| `TestUpdate_aChangedFileMakesANewRelease` | A change that does not show on the page. A download of the files that did not change. |
| `TestUpdate_aBadFileKeepsTheLiveReleaseAsItIs` | A format error that changes the page. The manifest has an error row. |
| `TestUpdate_aReleaseThatStoppedIsBuiltByTheNextRun` | A build that stops after the data are in `raw` and that the next start does not make again. |
| `TestUpdate_aLocalFileNeedsNoRequest` | A request to FAO for a local file. A local file with the same hash that is read again. |
| `TestRun_aFileForAnUnknownDatasetIsRefusedBeforeTheDatabaseIsUsed` | An incorrect option that starts work on the database. |
| `TestRun_updateGoesLiveThenSaysNothingIsDue` | A command that does not apply the migrations. An output that does not show the datasets that changed. |

## Test with the files of the sources

After the 7 tasks, do these steps with the FAO files of the sources. Use a new database on port 5433. Remove it at the end.

1. Start `marketdata update` with the files `QCL`, `PP` and `TCL` from the cache `/tmp/honey_price_cache` and the file `TM` from FAO. Write down the time of each step.
2. Start a script that is not part of the repository. It compares each open row of `raw.faostat_observation` with the tables `faostat_*` of database v5. The result must be 0 differences in the value and the flag for the keys that database v5 has.
3. Send each query of the page layer 200 times. Write down the 95th percentile. The limit is 100 ms or less.
4. Start `marketdata update` again. It must download nothing and add no release.

## Result of the test with the files of the sources

The test is of 2026-10-11 and uses the FAO files of 2026-10-09. The file `TM` is a download from before the test. All results are in the limits.

| Step | Result |
| --- | --- |
| 1. First start with 4 files | 32 s in all. The use of memory is 39 MB or less. Release 1 went live and the 6 tests gave no error. |
| 1. Time for each part | `QCL` 1.6 s, `PP` 0.8 s, `TCL` 8.3 s, `TM` 20.5 s and the build of the release 0.8 s. |
| 1. Rows read and kept | `QCL` 4,209,110 and 24,274. `PP` 1,319,583 and 13,763. `TCL` 17,143,873 and 102,753. `TM` 52,410,630 and 333,832. |
| 2. Compare with database v5 | 449,540 rows of database v5. The new database has all of them. 0 flag differences and 0 differences in the row number. |
| 2. The one value that is not the same | Database v5 has 10060574838.7 and FAOSTAT has 10060574838.700001. Database v5 rounded the number. |
| 2. Rows that database v5 does not have | 25,082 rows of item 1181 (bees). `TCL` has 12,350 and `TM` has 12,732. |
| 2. Page tables from database v5 with a different script | The 3 tables have 7,570, 18,659 and 118,596 rows. All the rows are the same. |
| 3. Page queries, 1 reader | The 95th percentile is from 0.09 ms to 1.7 ms. The slowest query reads 699 rows. |
| 3. Page queries, 8 readers at one time | The 95th percentile is from 0.16 ms to 2.9 ms. The limit is 100 ms. |
| 4. Start with `PP` from FAO | FAO sent 11.7 MB. 0 new rows, 0 changed rows and 0 removed rows. Release 2 went live. |
| 4. Start again | 0 downloads and 0.4 s. No new release. |
| Rollback | 2 rollbacks in 20 ms and 10 ms. Release 1 and then release 2 were live. |
| An archive that is cut | The exit code is 1. The manifest has an error row. The live release did not change. |

## Not in this plan

- The API, the header `ETag`, the visitor role and the time limit of 2000 ms.
- The sources ERS, NASS, Census, HTS, trade remedies, AMS and IBGE.
- The World total rows on the page. The first plan keeps them out of the country tables.
- A page table for the producer prices of `PP`. The system reads them into `clean`, but no page table uses them.
- A request from a visitor. The tests use readers that follow the rule of the specification for `release_info`.
