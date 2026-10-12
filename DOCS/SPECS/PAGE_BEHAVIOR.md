# The page

## Purpose

This document is the specification of the page. The page shows the FAOSTAT data about honey: production, producer price and export price. It does not use a server. Open `index.html` in a browser to use it.

## Files

The file `index.html` has the structure and the text of the page. The file `styles.css` has the style. The file `ui.js` has the functions that the other scripts share: the units, the formats of numbers, the charts and the address. The file `app.js` makes the FAOSTAT part of the page work. The file `us.js` makes the section "United States" work.

The files `data/honey_data.js`, `data/honey_status.js`, `data/us_supply.js` and `data/us_status.js` have the data. The file `DATA_SOURCES.md` is the specification of these files.

## Controls

The year control is a slider. It goes from the first year to the last year of the FAOSTAT data. A change of the year changes all the values of FAOSTAT on the page. The text below the slider gives the last year of FAOSTAT and the last year of the United States data. The text below the title gives the first year and the last year of each source.

The unit control has 3 values: pound, kilogram and tonne. The page shows production in units of 1,000,000 pounds, 1,000,000 kilograms or tonnes. It shows prices in US dollars for each pound, kilogram or tonne. A price in tonnes has no decimal part.

The page writes a production of zero as 0 and a share of zero as 0%. It writes a small production with more decimals. Thus a value that is not zero does not show as 0. It shows an export quantity of less than 1,000,000 pounds or 1,000,000 kilograms in pounds or kilograms.

The switch "Official values only" removes each country value that does not have the flag A. The World totals stay on the page, because the script makes them from the countries. The shares in the table use the full World total.

The field "Search" keeps the countries with a name that has the letters that you type. Large letters and small letters have the same result. Marks on letters do not change the result.

## Address

The page keeps the year, the unit and the other selections in the part of the address after the symbol #. The keys are:

| Key | Content |
| --- | --- |
| `y` | The year |
| `u` | The unit: `lb`, `kg` or `tonne` |
| `a` | The area code of the country in the country panel |
| `o` | The value 1 when the switch "Official values only" is on |
| `uy` | The year of the section "United States" |

For example, `#y=2023&u=lb&a=183&o=1` opens the page for the year 2023, in pounds, with Romania in the country panel, and with official values only. A key with an incorrect value does not change the selection.

## Top of the page

The listed production is the sum of the production of the countries in the table. The page has 4 areas at the top. The first 3 areas show the selected year. The area "World production" shows the World total, the share of the listed production that is official, the range and the score. The area "World export price" shows the export value divided by the export quantity, the range and the score.

The area "Producer price range" shows the lowest and the highest producer price of the countries, with the names of these countries. It also shows the number of countries that have a price.

The area "United States" shows the last year of the United States data, which FAOSTAT does not have. It shows the production, the average price and the date of the report. When the year has one report only, it tells that the value is a first estimate. A button in the area moves the page to the section "United States".

## Panel about the data of the year

This panel has the title "How reliable is the year?". It has a list of facts about the selected year. The list gives the share of each flag in the production. It gives the number of countries in each level of the score.

The list also gives the number of countries that have a producer price or an export price. It gives the share of the tonnage of each flag in the export price.

The panel also has a chart. Each bar of the chart is one year. The bar shows the share of the listed production that has each flag. The switch does not change this chart. A click on a bar selects the year.

## Charts

The page has 2 charts for the World: production and export price. The country panel has 3 charts for one country: production, producer price and export price. Each chart has a point for each year with a value. The x axis has all the years, with a label each 10 years and a mark each 5 years. The y axis starts at zero.

The shape of a point shows the flag. An official value has a solid circle. An estimated value has an open circle. An imputed value has a diamond. An external value has a solid square, and a series break has an open square. A point is lighter when its score is lower.

Each point has a bar for its range. A band connects the ranges of each sequence of years. A strip below the chart has one mark for each year, with the color of the level of the score. A click on a chart selects the year.

The chart shows the last 3 years with a different color and a line at their start. The word "provisional" is above them, because FAO and the countries can change these years. When you move the mouse above a chart, the page shows a message. The message has the year, the value, the source, the range and the score. It also has a note when the year is "provisional". Below these, the message gives the score at the start and each penalty of the score.

## Table

The table has one row for each country or area that has a value in the selected year. The columns are the number, the country or area, the production, the share of the World total, the producer price and the export price. The number is the position of the row by production.

A click on a heading sorts the table. A click on the same heading again changes the direction. A value has a small letter when its flag is not A. It also has a circle with its score. When you move the mouse above the circle, the page shows the same message as for a chart. A click on a row selects the country and opens the country panel.

The note below the table gives the number of rows and the number of countries that have a price. It gives the share of the World total that the rows have. It also gives the text for each letter.

When the page has a width of 600 pixels or less, the table does not show the number and the share. The circle with the score stays.

## Country panel

The country panel shows one country. It gives the production, the share of the World total, the producer price, the export price and the export quantity for the selected year. Each value has its score and its range. The panel has the 3 charts of the country. The button "Clear" closes the panel.

A country with an export quantity of less than 100 tonnes has no export price. The panel shows the export quantity and gives the cause. The switch "Official values only" can remove the export values of the year. Then the panel shows no export quantity and gives this cause.

## Section "United States"

The section "United States" is below the table of the countries. It shows the data of NASS for the United States: the production, the price, the colonies, the yield, the stocks and the value. The file `DATA_SOURCES.md` gives the source. The text below the title tells that the data come from NASS and are newer than the FAOSTAT data. The section also shows the date on which the script last examined ESMIS.

The page gets the file `data/us_supply.js` with the page. When the file does not come, the section and the area at the top show a message with the name of the file. The other parts of the page work.

### Year of the section

The section has a list of years. It is not the slider of the page, because the slider stops at the last year of FAOSTAT. The list has each year that has a value for the United States. The page selects the last of them. The address key `uy` keeps the year. A year that is not in the list does not change the selection.

### Facts

A line gives the values of the United States for the selected year. These are the production, the colonies, the yield, the average price, the value, the stocks on 15 December and the date of the report. When the first estimate of the year is different from the last value, the line also gives the first estimate. It gives the date of its report. The unit control of the page changes the units of the section.

### Charts

The section has 2 charts: the production and the average price of the United States for each year. The last value of a year has a solid circle. When the first estimate of the year is different, it has an open circle, and a line connects the 2 circles. A line connects the last values. The selected year has a mark.

The message of a chart gives the year, the value, the date of the report and the first estimate. A click on a chart selects the year.

### Table

The table shows the states for the selected year. The columns are the state, the colonies, the yield, the production, the stocks, the price and the value. The row "Other States" is the last row. The last line of the table has the values of the United States. A click on a heading sorts the table, as in the table of the countries. A value that NASS does not give shows the symbol "—".

The line below the table gives the source and the date of the report. It also tells that the values come from the newest report that has the year. When the selected year has no value for the United States, the section shows the text "No data for this year". It gives the first year and the last year of the data.

When the page has a width of 600 pixels or less, the table does not show the stocks and the value.

## Text that follows the data

The page writes some numbers in its text from the data file. These numbers come from the data:

- The first year and the last year of each series.
- The dates of the files.
- K, K1 and the class multipliers.
- The numbers of the tests of the range.
- The numbers of the score.
- The export limit and the results of its test.
- The years in which the World total of the exports is different from the sum of the countries.

Thus the text follows the data after an update of the data. The text below the title shows the update date and the status date. The file `DATA_UPDATE.md` gives more information.

## References

- `DATA_SOURCES.md` is the specification of the data.
- `CONFIDENCE_METHOD.md` is the specification of the range and the score.
- `DATA_UPDATE.md` is the specification of the update of the data.
