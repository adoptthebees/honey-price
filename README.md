# Honey price and production

This tool shows data about honey. It shows the production, the producer price and the export price of honey for each country. These data come from FAOSTAT, the statistics database of the Food and Agriculture Organization of the United Nations (FAO). The tool also shows the production, the price, the colonies and the stocks of the United States for each state. These data come from the reports of NASS, a part of the USDA. They are newer than the FAOSTAT data.

## Use

Open `index.html` in a browser. The page does not use a server. Select a year and a unit. Select a country in the table to see its values for all years.

Each value has a confidence score and a range. The page has text that tells how the tool makes them. The page also shows the date of the last update. It also shows the date on which the script last examined the FAOSTAT files for newer data.

## Update the data

A GitHub workflow looks for newer FAOSTAT files each week. When it finds them, it makes the data file again and saves it in the repository. It also saves the status date. To make the data file on your computer, use `python3 scripts/build_data.py`. A second workflow does the same for the reports of NASS with `python3 scripts/build_us_data.py`. The file `DOCS/SPECS/DATA_UPDATE.md` gives more information.

## Tests

To do the tests, use `python3 -m unittest discover -s scripts`. After a change of `styles.css`, `ui.js`, `app.js` or `us.js`, use `python3 scripts/stamp_page.py`. It writes the version of each file into `index.html`. Thus a browser gets the new file.

To examine the documents, use `python3 scripts/check_docs.py`. Add the option `--vocabulary` to examine each word against the dictionary of the ASD-STE100 specification. The file `AGENTS.md` gives the rules for the documents.

## Documents

- `AGENTS.md` has the instructions for AI tools and the rules for the documents.
- `DOCS/SPECS/DATA_SOURCES.md` is the specification of the data.
- `DOCS/SPECS/DATA_UPDATE.md` is the specification of the update of the data.
- `DOCS/SPECS/CONFIDENCE_METHOD.md` is the specification of the confidence score and the range.
- `DOCS/SPECS/REVISION_TEST.md` is the specification of the test of the range against previous versions of the data.
- `DOCS/SPECS/PAGE_BEHAVIOR.md` is the specification of the page.
- `DOCS/SPECS/2026_10_11_MARKET_DATA_DESIGN.md` is the specification of the market data of Exchange Honey: the sources, the database and the pages.
- `DOCS/SPECS/2026_10_12_US_PANELS_DESIGN.md` is the specification of the United States panels on the page: the content, the data files and the workflow of each week.
- `DOCS/PLANS/2026_10_11_MARKET_DATA_PLAN.md` is the plan for the FAOSTAT part of the market data.
- `DOCS/PLANS/2026_10_12_MARKET_SOURCES_AND_API_PLAN.md` is the plan for the other sources and the API of the market data.

## License

The data are from FAOSTAT and have the license `CC BY 4.0`. FAO shows that the trade data can have more limits from UNSD and Eurostat. The data of NASS are in the public domain.
