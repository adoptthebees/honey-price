# Data sources

## Purpose

This document is the specification of the data that the page shows. It gives the sources, the rules that select the data, and the fields of the data file.

## Source

All values come from FAOSTAT. FAOSTAT is the statistics database of the Food and Agriculture Organization of the United Nations (FAO). The item is "Natural honey" with the FAOSTAT item code 1182. The license is `CC BY 4.0`.

FAOSTAT does not count honey. It gets the values from the countries. The trade data come from UNSD and Eurostat. These organizations can put more limits on the use of the trade data.

## Series

| Series | Data set | Element code | Unit |
| --- | --- | --- | --- |
| Production | `QCL` | `5510` | tonne |
| Producer price | `PP` | `5532` | US dollar for each tonne |
| Export quantity | `TCL` | `5910` | tonne |
| Export value | `TCL` | `5922` | 1000 US dollars |
| Import quantity | `TCL` | `5610` | tonne |

The page shows production, producer price and export price. The script uses the import quantity only to compare it with the production and the exports.

## Files

The script gets 3 zip files from the FAOSTAT download server. The names are `Production_Crops_Livestock_E_All_Data_(Normalized).zip`, `Prices_E_All_Data_(Normalized).zip` and `Trade_CropsLivestock_E_All_Data_(Normalized).zip`.

The trade file has approximately 270 MB. The script keeps the files in a cache directory. It downloads a file again only when the `Last-Modified` value of the file changes.

## Selection rules

- The script uses only the rows with item code 1182 and the element codes in the table above.
- The script uses only annual values. The price file also has rows for each month.
- A country row has an area code of less than 5000. FAO uses the codes from 5000 for groups, such as the World.
- The script removes the group China (code 351). It is the sum of "China, mainland" and "China, Taiwan Province of". The script keeps the 2 parts.
- The script stops with an error when the group China has producer prices, because it can remove data.
- The script removes each area with the word "excluding" in its name. These areas are groups too.
- The script removes each area without a value in the series of the table above.
- The World row (code 5000) has the World totals: the World production and the World exports. FAOSTAT has no World producer price.

## Flags

Each value has one flag letter from FAO. A space in a flag string shows that the value is not in the data.

| Flag | Text of FAO | Word on the page |
| --- | --- | --- |
| A | "Official figure" or "Official value" | official |
| E | "Estimated value" | estimated |
| I | "Value imputed by a receiving agency" | imputed |
| X | "Figure from external organization" or "Value from external organization" | external |
| B | "Time series break" (producer price only) | series break |
| M | "Missing value; data cannot exist" | none |

A non-official value is a value with a flag other than A. The switch "Official values only" keeps only the values with the flag A.

## Export price

The script divides the export value by the export quantity and multiplies the result by 1000. The result is in US dollars for each tonne. It is a customs average. It has all grades of honey. It also has exports of honey that the country got from other countries.

To make an export price, the script must have an export quantity and an export value. Its flag is A only when the 2 flags are A. If not, the flag is the first of I, E and X that one of the 2 flags has.

A country has an export price only for a year with an export quantity of 100 tonnes or more. The World row has no such limit. An export price from a small export quantity has much noise. The script measures this noise and keeps the result in `meta.exportCheck`.

## Units

The data file keeps tonnes and US dollars for each tonne. The page changes the values to pounds and kilograms. It uses 1 lb = 0.45359237 kg.

## Data file

The file `data/honey_data.js` sets `window.HONEY_DATA`. The value is one JSON object with 4 keys.

| Key | Content |
| --- | --- |
| `meta` | The source, the license, the date of the update, the dates of the FAOSTAT files, the texts of the flags, the export limit, the numbers that the page shows in its text, and the rules of the score |
| `years` | The years |
| `world` | The World row. It has one array of values for each series. Each array has one value for each year. |
| `areas` | One entry for each country or area |

Each entry of `areas` has the keys `code` and `name`. It has the arrays `production`, `price`, `exportQty` and `exportValue`. Each of these arrays has one value for each year. The flag strings `productionFlags`, `priceFlags` and `exportFlags` have one letter for each year.

For each type, an entry has 3 arrays: the score, the half width and the penalties. The names for production are `productionConf`, `productionBand` and `productionWhy`. The names for producer price are `priceConf`, `priceBand` and `priceWhy`. The names for export price are `exportConf`, `exportBand` and `exportWhy`.

The score is a whole number from 5 to 90. The half width is in units of 0.001. A value that is not in the data has null in the 3 arrays.

A penalty array has one string for each year. The string has one part for each penalty of the value, with a space between the parts. A part is a letter and a whole number. For example, `a10 j3` shows the age penalty 10 and the jump penalty 3. A value that has no penalty has an empty string. The key `meta.uncertainty.rubric.codes` gives the name of each letter.

The World row has no price arrays and no penalty arrays. Its scores and ranges come from the countries. The file `CONFIDENCE_METHOD.md` gives the rules.

### The key `meta`

| Key | Content |
| --- | --- |
| `retrieved` | The date of the update, in UTC |
| `sources` | For each FAOSTAT file: the data set, the title, the element, the links, the file name and `lastModified` |
| `flags` | The flag letters that the data use, with the text of FAO for each letter |
| `minExportTonnes` | The export limit for the export price of a country |
| `exportCheck` | The test of the export limit. It has the share of country years with an export price of more than 6.00 or less than 0.40 US dollars for each lb. It also has the share of the tonnage above the limit in the last year. |
| `worldExportGaps` | The years in which the World export quantity is more than 1% different from the sum of the countries |
| `uncertainty` | The numbers that the script finds from the data, and the rules of the score and the range |

The page writes `exportCheck` and `worldExportGaps` in its text. Thus the text follows the data after each update.

## Status file

The file `data/honey_status.js` sets `window.HONEY_STATUS`. The value is `{"checked": "YYYY-MM-DD"}`. It has the status date. The status date is the date on which the script last examined the FAOSTAT files for newer data. The script writes it at the end of its work.

## Stops of the script

The script stops with an error in these conditions:

- A file has no honey row.
- A flag has more than one letter.
- The group China has producer prices.

The script gives a note when the World export quantity is more than 1% different from the sum of the countries.

## Limits of the data

FAOSTAT has no retail price and no wholesale price. All prices are in US dollars of the year of the price. They do not change for the increase of prices in time.

A country can have a value in the first years and no value in the last years. FAO includes it in the World total. The page shows the share of the World total that the country rows have.

The World total of the exports can be different from the sum of the countries. The data of 2026-10-10 show this for the year 2013.

The production file can have a date before the date of the price file. The page shows the date of each file.

## References

- `CONFIDENCE_METHOD.md` is the specification of the score and the range.
- `DATA_UPDATE.md` is the specification of the update of the data.
- `PAGE_BEHAVIOR.md` is the specification of the page.
