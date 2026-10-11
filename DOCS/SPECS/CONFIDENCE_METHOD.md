# Confidence method

## Purpose

This document is the specification of the confidence score and the range that the page shows for each value. FAOSTAT gives no error for its values. The script makes the score and the range from the data.

The score and the range are estimates of the tool. They are not FAO values. They are not confidence intervals.

The script `scripts/build_data.py` uses `scripts/uncertainty.py` for each type of series. It keeps the score and the range in the data file. The page reads them and shows them in the charts and in the table.

## Terms

A series is the values of one type for one country. A series has one value for each year. There are 3 types: production in tonnes, producer price in US dollars for each tonne, and export price in US dollars for each tonne. The script divides the export value by the export quantity to make the export price.

Each value has a flag from FAO. The flag A shows an official value. The flag E shows an estimated value and the flag I shows an imputed value. The flag X shows an external value. The flag B shows a series break. A non-official value is a value with a flag other than A.

A neighbor of a value is the value of the year before or the year after, in the same series. The miss of a value is the difference between its logarithm and the mean of the logarithms of its 2 neighbors. The script uses the natural logarithm. A value must be more than zero to have a miss.

The series scale is the spread of the misses of the official values of a series. The script measures the spread as the median of the distances from the median, multiplied by 1.4826. A series with a small number of misses uses a pooled scale.

K is one number for each type. The class multiplier is one number for each flag. The estimate multiplier is one number for each type. The script uses these numbers to make the estimate error of a non-official value.

K1 is one number for each type. It is the same as K, but for a value that has one neighbor only. A penalty is a number that the script subtracts from the score for one measured problem.

The area code is the number that FAO gives to a country.

## Range

Each value has a range. The low end of the range is the value divided by a number. The high end is the value multiplied by the same number. The number is the exponential of the half width.

The half width is on a logarithm scale. It is the square root of the sum of the squares of 4 parts:

1. The report error. This is one number for each type.
2. The revision. This is one number for the last year, the year before and the year before that.
3. The rounding. The script makes this part from the last digit of the value.
4. The estimate error. This part is only for a non-official value.

The script limits the half width to the natural logarithm of 3. Thus the high end is not more than 3 times the value. The low end is not less than 1/3 of the value.

The script keeps the half width in units of 0.001. The half width is a share of the value. Thus a value of zero has the half width zero.

### Numbers of the parts

The report error, the revision and the estimate multiplier are assumptions. The tests in this document agree with them for production only.

| Part | Production | Producer price | Export price |
| --- | --- | --- | --- |
| Report error | 0.03 | 0.04 | 0.03 |
| Revision, last year | 0.05 | 0.11 | 0.05 |
| Revision, 1 year before | 0.03 | 0.06 | 0.03 |
| Revision, 2 years before | 0.015 | 0.03 | 0.015 |
| Estimate multiplier | 2.5 | 1.0 | 1.0 |

The constants `REPORT_ERROR`, `REVISION` and `ESTIMATE_SCALE` in `scripts/uncertainty.py` keep these numbers.

### Rounding

A whole number that ends in zeros can have a rounding error. For example, 24,000 can be a number from 23,500 to 24,500. The script divides 500 by 24,000 to make the rounding part for 24,000. The result is 0.021.

A whole number that does not end in zero has the rounding part 0.5 divided by the value. A value with a decimal part has the rounding part zero.

### Estimate error

The script multiplies K by the series scale, the class multiplier and the estimate multiplier. The result is the estimate error. The script limits it to the natural logarithm of 3 before it adds it to the sum of squares.

K is the 90th percentile of the misses of the official values of all countries, each divided by its scale. The script finds the scale of each miss without that miss. Thus a value does not help to make the scale that tests it.

A normal curve gives K = 1.645. The data give a larger K for each type, because the misses have long tails.

### Scale

A series must have 6 or more official values with 2 official neighbors to have a series scale. The scale of the series is then a mixture of the series scale and the pooled scale. The pooled scale has the weight of 6 values.

A series with a smaller number of such values uses the pooled scale only. The score has the thin penalty for this.

The script divides the countries into 3 groups that have the same number of countries, by the median value of the series. The pooled scale of a group is the median of the series scales in the group. A group with less than 3 series scales uses the median of all series scales.

### Class multiplier

The class multiplier is 1 or more. It makes the range larger for a flag when the values of that flag have a larger miss than official values. The script divides each miss by the series scale. It then divides the spread of these numbers for the flag by the spread for the official values.

The script makes the multiplier only when 20 values or more of the flag have a miss with 2 official neighbors. If not, the multiplier is 1.

## Totals

FAO gives a World total for production and a World total for exports. The page does not use the flag that FAO gives to a total. The notes of FAO on the data show that its totals include estimated values. Thus the script makes the range and the score of a total from the countries that make the total.

For the World production, the script uses each country that has a value in the year. Each country gives its value, its score, its half width and its flag. Some part of the World total can have no country row. This part is the World total minus the sum of the countries.

The script uses this part as an estimated value. Its half width is the mean half width of the non-official country values, with the value as weight. Its score is 60 minus the age penalty.

The script multiplies the value of each part by the exponential of its half width, minus 1. It finds the square root of the sum of the squares of these numbers. The half width of the total is the logarithm of 1 plus this root divided by the total. The score of the total is the mean of the scores of the parts. Each part has a weight that is equal to its value.

For the World export price, the script uses the countries that have an export price. The weight of each country is its export value. The script then uses the same square root and the same mean.

These rules are correct only when the errors of the countries have no relation to each other. If the errors have a relation to each other, the range of a total is too small.

## Score

The confidence score is a whole number from 5 to 90. It is a set of rules. It does not give a probability. The tool does not measure the weights.

The page shows 4 levels. The level is "high" for 80 or more, "medium" for 60 to 79, "low" for 40 to 59 and "very low" for less than 40.

The script starts from a score for the flag. Then it subtracts the age penalty and 6 other penalties. Each penalty is a whole number.

| Flag | Score at the start |
| --- | --- |
| A | 90 |
| X | 75 |
| B | 75 |
| E | 60 |
| I | 40 |
| Other | 40 |

### Age penalty

For the last year, the year before and the year before that, the script subtracts 10, 6 and 3. This is for production and export price. For producer price it subtracts 20, 10 and 5, because FAO changes prices more.

### Penalties in proportion

The 6 other penalties are in proportion to the measure of a problem. A measure is zero when the value has no problem. The script multiplies the most penalty by the measure and divides the result by the full measure. It makes this a whole number. The penalty is not more than the most penalty.

A penalty is not zero for a small problem. Thus a small problem has a small penalty, and different values have different scores.

| Penalty | Letter | Most | Full measure | Types |
| --- | --- | --- | --- | --- |
| Jump | j | 20 | 1.5 | All 3 types |
| History | h | 15 | 1.0 | All 3 types |
| Thin | t | 10 | 1.0 | All 3 types |
| Rounding | r | 20 | 0.5 | All 3 types |
| Price gap | g | 15 | 1.5 | Producer price and export price |
| Supply | s | 20 | 0.25 | Production and export price |

The age penalty has the letter a. The constants `AGE_PENALTY` and `CHECKS` in `scripts/uncertainty.py` keep these numbers.

### Jump

The jump measure shows how far a value is from its neighbors. A value that has a neighbor on each side has its miss, divided by the scale of the series and by K. The neighbors can have each flag.

A value that has one neighbor only has the step from that neighbor, divided by the scale of the series and by K1. A value has one neighbor only in the first year, in the last year, and next to a year without a value. A step is the distance between the logarithms of 2 values.

K1 is the 90th percentile of the steps of the official values, each divided by the scale of its series. Only a step between 2 official values counts.

### History

The history measure of a value is the share of values that are not official in the 11 years around it. These years are the year of the value, the 5 years before and the 5 years after. In the first 5 years and in the last 5 years, the script moves the 11 years to stay in the data. A year without a value does not count.

### Thin

A series must have 6 or more official values with 2 official neighbors to have a series scale. The thin measure is 6 minus the number of such values, divided by 6. It is zero for a series that has 6 or more such values. A series that has none has the measure 1. All the values of a series have the same thin measure.

### Rounding

The rounding measure is the rounding part of the range. For a value of 1,000 it is 0.5. For a value of 31,541 it is almost zero.

### Price gap

The ratio of a country in a year is its producer price divided by its export price. The usual ratio of the country is the median of the natural logarithms of its ratios. The price gap measure of a year is the distance between the logarithm of its ratio and the usual ratio.

The script makes the usual ratio only for a country that has 5 years or more with the 2 prices. A year without the 2 prices has the measure zero. The 2 prices of the year have the same measure.

### Supply

The supply of a country is its production plus its import quantity. The supply measure of a year is its export quantity divided by its supply, minus 1. It is zero when the exports are not more than the supply.

The measure is also zero for an export quantity of less than 100 tonnes. It is zero when the production has no value.

### Result

The script subtracts the age penalty and the 6 other penalties from the score at the start. It makes the result a whole number and keeps it from 5 to 90. The data file keeps the penalties of each value. The page shows them.

The most penalties and the full measures are assumptions. The revision test cannot measure them. K and K1 come from the data.

## Use on the page

The page shows the score in a small circle next to each value. The color of the circle shows the level. When you move the mouse above the circle, the page shows the score at the start and each penalty that is more than zero. A message of a chart has the same text. The text of a World total shows that its score is the mean of the scores of the countries.

A country has an export price only for a year with an export quantity of 100 tonnes or more. The World total has no such limit.

The switch "Official values only" removes each country value that does not have the flag A. It does not remove the World totals, because the script makes them from the countries.

## Tests

3 tests measure the ranges. The neighbor test measures the estimate error with official values. The revision test uses previous versions of the data. The World total test uses the World total.

### Neighbor test

The neighbor range of a value is the mean of the logarithms of its 2 neighbors, plus and minus K times the scale. The range holds the value when the miss is not more than K times the scale.

For each official value that has 2 official neighbors, the script finds the scale without the miss of this value. It then divides the miss by the scale. The script divides the countries into 2 groups by the parity of the area code. It finds K with one group and tests K with the other group. It does the test 2 times, and each group is the test group 1 time.

The data of 2026-10-10 give these results. The table gives the share of the official values that the neighbor range held.

| Type | K | Held share | Values |
| --- | --- | --- | --- |
| Production | 2.457 | 90.2% | 3,686 |
| Producer price | 2.048 | 90.0% | 1,534 |
| Export price | 1.995 | 90.3% | 2,323 |

This test measures the estimate error with official values only. It does not show how far an FAO estimate is from the correct value.

### Class multipliers

The data of 2026-10-10 give these class multipliers. Only a value with 2 official neighbors can set a multiplier. Only 42 of the 3,199 non-official production values (1.3%) have 2 official neighbors.

| Type | Flag | Multiplier | Values that set it |
| --- | --- | --- | --- |
| Production | E | 1.22 | 23 of 2,127 |
| Production | I | 1.00 | 10 of 890 |
| Production | X | 1.00 | 8 of 182 |
| Producer price | E, I, X, B | 1.00 | 1 or less |
| Export price | I | 1.00 | 13 of 147 |
| Export price | X | 1.80 | 27 of 187 |

### Revision test

The test uses 3 previous versions of the production file. It makes the ranges with the data of each previous version only. Then it compares each range with the value of the same country and year in the version of 2025-12. The file `REVISION_TEST.md` gives the method.

The test uses the official values that are in the 2 versions. In the last year of the previous version, the range held 91.9% of 136 new values. For the year before, the rate is 94.8% of 193 values. For 2 years before, it is 98.1% of 212 values. For the years before that, it is 100% of 11,619 values.

Some estimated values and imputed values are official values in the new version. There are 110 such values. The neighbor range without the multiplier held 70.9% of them. The range with the estimate multiplier 2.5 held 90.0% of them. This is the cause of the multiplier.

### World total test

The test makes the range of the World total from the countries of each previous version. It compares the range with the World total in the version of 2025-12. The range held all 185 values.

Only 3 of the values are for the last year of a previous version. For these 3 values, the World total in the new version is 8.7%, 6.1% and 3.5% more than in the previous versions.

### Score test

The test counts the different scores of the official values of the last year. The previous rules gave 3, 2 and 3 different scores to these values. One score was on 94%, 93% and 85% of them. The data of 2026-10-11 give these results with the new rules.

| Type | Values | Different scores | Largest share with the same score |
| --- | --- | --- | --- |
| Production | 50 | 17 | 14% |
| Producer price | 44 | 12 | 20% |
| Export price | 55 | 19 | 22% |

The test also counts the values that have a range of more than 20% on each side and a score of 80 or more. The previous rules gave 117 of the 12,523 values this score and this range. The new rules give them to 1 value. The rounding penalty causes this change.

## Limits

The ranges of producer price and export price have no test against previous versions. The data that the test uses have no previous version of these files.

The report error and the revision are assumptions. For production, the revision test agrees with them. For the other types, only the revisions of the USDA for US honey agree with them. In the years 2017 to 2024, the USDA changed its first estimate of the US production by 1.1% or less. It changed the price by 11% or less.

The range has the same distance above and below the value on a logarithm scale. In the tests, the World total was more in the new version, and the USDA did not decrease the US production. Thus the range can be too low for the last year.

The class multipliers use a small number of values. The score puts an estimated value above an imputed value. In the revision test, the estimated values had a larger miss than the imputed values. The 25 estimated values had a median miss of 22%. The 83 imputed values had a median miss of 13%. A set of 25 values is too small to change the score.

The revision test uses the new official value as the correct value. This value can have an error too. The tool does not measure a confidence interval.

The age penalty and the jump penalty lower the score of the last year. In the data of 2026-10-11, only 3 of the 50 official production values of 2024 have a score of 80 or more. Thus a small number of values of the last 3 years have the level "high".

## References

- `DATA_SOURCES.md` is the specification of the data.
- `REVISION_TEST.md` is the specification of the revision test.
- `PAGE_BEHAVIOR.md` is the specification of the page.
