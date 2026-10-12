# Data update

## Purpose

This document is the specification of the update of the data file. A GitHub workflow makes the data file again when FAOSTAT has newer files. No person must do the work.

## Parts

- The script `scripts/build_data.py` makes the data file `data/honey_data.js` and the status file `data/honey_status.js`.
- The workflow `.github/workflows/update-data.yml` starts the script each week and saves the result in the repository.
- The workflow `.github/workflows/checks.yml` does the tests and examines the documents on each push to the branch `main` and on each pull request.

The page reads the 2 data files.

## Dates on the page

The page shows 2 dates. The word "Updated" is before the update date, which comes from `meta.retrieved` in the data file. The words "FAOSTAT last checked" are before the status date. The status date is the date on which the script last examined the FAOSTAT files for newer data. It comes from the status file.

The 2 dates are different when FAOSTAT has no newer file. Then the status date changes and the update date does not change.

## Newer files

Each FAOSTAT file has a `Last-Modified` value. The data file keeps this value for each of the 3 files that made it. The option `--if-changed` sends a HEAD request to FAOSTAT and gets the 3 values. It does not download the files.

When the 3 values are the same as in the data file, the script writes only the status file and stops. The script makes the data again in these conditions:

- A value is different.
- FAOSTAT sends no value.
- There is no data file, or the data file is not complete. The data file is complete when it has the years, the World row and the areas.

A change of a script does not change the 3 values. After a change of a script, make the data again without the option `--if-changed`.

## Workflow

The workflow "Update data" starts each Monday at 05:17 UTC. A person can also start it. The input `force` makes the script make the data again when FAOSTAT has no newer file.

The workflow has these steps:

1. Get the repository.
2. Do the tests. The workflow does not save a change when a test gives an error.
3. Start the script `python3 scripts/build_data.py`. Use the option `--if-changed`, or no option when `force` is set.
4. Add the directory `data`. When no file is different, stop.
5. Save the change in the repository with the message "Update honey data from FAOSTAT". When only the status file is different, use the message "Record the FAOSTAT check".
6. Send the change to the branch of the repository.
7. Send a request to GitHub for an update of the site.

The workflow has 2 permissions: `contents: write` and `pages: write`. The workflow sets the 2 permissions, because the repository gives read access only.

## Update of the site

The site uses the Pages option "Deploy from a branch". GitHub does not start an update of the site for a change that a workflow sends with the `GITHUB_TOKEN`. Thus step 7 sends a request to the endpoint `POST /repos/{owner}/{repo}/pages/builds`. The permission `pages: write` lets the workflow send this request.

## Schedule

GitHub stops a schedule in a repository that is open to all after 60 days without a change in the repository. FAOSTAT can stay the same for more than 60 days.

Thus each start of the workflow saves the status file. The new date is a change in the repository. It keeps the schedule on. The status date on the page also shows that the workflow works.

## Start the workflow

To start the workflow on GitHub:

1. Open the tab "Actions".
2. Select "Update data".
3. Select "Run workflow".
4. Set `force` when you want new data.

To start the script on your computer, use `python3 scripts/build_data.py --if-changed`. Add `--refresh` to download the FAOSTAT files again.

## Failure

The workflow stops with an error in these conditions:

- The script gives an error.
- A test gives an error.
- A file does not download in full.

The workflow then saves no change. GitHub sends a message about the failure. The page keeps the last good data.

When the workflow stops with an error, the status date on the page does not change. A status date that is more than 1 week before the date on which you look at the page shows a problem.

## Numbers that the update does not change

The update makes the data again, and the numbers that come from the data. It does not change `EVIDENCE` and `ESTIMATE_SCALE` in `scripts/uncertainty.py`. These numbers come from a test against previous versions of the production file. The file `REVISION_TEST.md` gives the test. But `scripts/build_data.py` reads the revisions of the USDA from `data/us_supply.js` when the file is there.

## United States data

The script `scripts/build_us_data.py` makes the files `data/us_supply.js` and `data/us_status.js` from the reports of NASS. The file `DATA_SOURCES.md` gives the source and the fields. The workflow `.github/workflows/update-us-data.yml` starts the script each Monday at 06:17 UTC. A person can also start it, with the input `force`.

The option `--if-changed` gets the list of the reports from ESMIS. When each report with a zip file is in the data file, the script writes only the status file and stops. If not, the script downloads the reports that are not in its cache and makes the data file again. A downloaded file that is not complete, or is not a zip file, stops the script.

ESMIS does not always give a correct response to a runner of GitHub. Some of its servers send an empty list, and the address of ESMIS is not always known to the runner. Thus the script tries each request 4 times, with 5 seconds between 2 tries. It reads the number of pages of the list from the first page. A page that does not come stops the script. The script also stops when ESMIS lists less reports than the data file has.

The workflow has the same steps and the same permissions as the workflow "Update data". The message of the change is "Update US honey data from NASS" when the data file is different. It is "Record the US data status" when only the status file is different.

NASS gives one report each year, in March. Thus the data file changes one time each year, and the status file changes each week.

## Limits

- A rule on the branch that does not let the workflow send a change stops the update.
- The schedule and the request for the update of the site work only on GitHub. The tests do not start them.
- FAO can change the format of its files. The script then stops with an error.
- The status date changes each week. Thus the repository gets one new change each week.

## References

- `DATA_SOURCES.md` is the specification of the data and the files.
- `REVISION_TEST.md` is the specification of the test of the range.
