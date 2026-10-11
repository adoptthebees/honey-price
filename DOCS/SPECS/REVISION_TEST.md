# Revision test

## Purpose

This document is the specification of the test behind the numbers in `EVIDENCE` and `ESTIMATE_SCALE` in `scripts/uncertainty.py`. The test compares previous versions of the FAOSTAT production file with the new version. The script `scripts/revision_check.py` does the test.

FAO gives its values again 2 times each year and changes some of them. The test shows how far a range of the tool is from the change that FAO makes in a new version. A good range holds the new value approximately 9 times in 10.

## Versions

The test uses 3 previous versions of the production file and 1 new version. The label of a version is the date of the CSV file in the zip file. The new version has the label 2025-12. Its CSV file has the date 2025-12-23.

### Version 2022-09

The label is 2022-09. The date of the CSV file is 2022-09-16. The source is a copy on GitHub. FAO did not make the copy. The Git commit of the copy has the date 2022-10-01.

URL: `https://github.com/rasmuse/bnf-faostat/raw/a812e57851d63e06f6d70399dc114b0af4755b7c/indata/Production_Crops_Livestock_E_All_Data_(Normalized).zip`

### Version 2023-12

The label is 2023-12. The date of the CSV file is 2023-12-19. The source is a copy on GitHub. FAO did not make the copy. The Git commit of the copy has the date 2024-10-01.

URL: `https://github.com/rasmuse/bnf-faostat/raw/7dda9128c58e26941d1cba718c3605c7b6a17d9e/indata/Production_Crops_Livestock_E_All_Data_(Normalized).zip`

### Version 2025-02

The label is 2025-02. The date of the CSV file is 2025-02-27. The source is a copy that the Internet Archive made on 2025-03-05.

URL: `https://web.archive.org/web/20250305184413id_/https://bulks-faostat.fao.org/production/Production_Crops_Livestock_E_All_Data_(Normalized).zip`

The file has the same MD5 and the same number of bytes as the record of OWID for the data set `faostat_qcl`. The MD5 is `3f0c438597573432e3c01dbdda5aec6c`. OWID gives 2025-02-27 as the date of the version.

## How to do the test again

Download the 3 previous versions from the links above. Use this command in the top directory of the repository:

```text
python3 scripts/revision_check.py VERSION_2022_09.zip VERSION_2023_12.zip VERSION_2025_02.zip
```

The script uses the cache of `scripts/build_data.py` for the new version. This is the file `Production_Crops_Livestock_E_All_Data_(Normalized).zip` in the directory `honey_price_cache` of the temporary directory. Use the option `--current` to give a different file.

## Method

The script makes the ranges with the countries of one previous version only. It then compares each range with the value of the same country and year in the new version. The script divides the new value by the previous value. The miss is the logarithm of the result.

The range holds the new value when the miss is not more than the half width above or below zero. The age of a value is the number of years between its year and the last year of the previous version. The script gives the results for the age 0, 1 and 2, and for an age of 3 or more.

The script makes 3 groups of values:

1. Official values. The 2 versions have an official value.
2. Estimates. The previous version has an estimated value, an imputed value or an external value. The new version has an official value.
3. World totals. The script makes the World total from the countries of the previous version. It compares the range of this total with the World total that FAO gives in the new version.

## Results

The date of the test is 2026-10-11. The script gives the numbers below.

### Official values

The table gives the share of new values that the range held.

| Age | Held share | Values |
| --- | --- | --- |
| 0 | 91.9% | 136 |
| 1 | 94.8% | 193 |
| 2 | 98.1% | 212 |
| 3 or more | 100.0% | 11,619 |

For the age 0, the share is 84.8% of 46 values for the version 2022-09. It is 93.8% of 48 values for the version 2023-12 and 97.6% of 42 values for the version 2025-02.

### Estimates

There are 110 values that are estimates in a previous version and official values in the new version. The range held 90.0% of them with the estimate multiplier 2.5. It held 70.9% of them without the multiplier.

| Age | Held share | Values |
| --- | --- | --- |
| 0 | 89.6% | 48 |
| 1 | 85.7% | 28 |
| 2 | 80.0% | 10 |
| 3 or more | 100.0% | 24 |

| Version | Held share | Values |
| --- | --- | --- |
| 2022-09 | 95.5% | 44 |
| 2023-12 | 91.9% | 37 |
| 2025-02 | 79.3% | 29 |

For a held share of 90%, the multiplier must be 2.47 for all 110 values. It must be 4.07 for the 25 estimated values (flag E) and 2.47 for the 83 imputed values (flag I). The new value is above the estimate for 46 of the 110 values. The miss is more than 3 times for 6 of the 110 values.

### World totals

The test has 185 years of World totals in the 3 previous versions. The range held all of them. Only 3 years have the age 0, one for each previous version. In these 3 years, the new World total is more than the previous World total by 8.7%, 6.1% and 3.5%. The ranges are 13.1%, 13.5% and 20.1% above and below the previous World total.

## Limits

Producer price and export price have no test, because the data have no previous version of their files. The producer price file from the Internet Archive of 2025-03-05 is the same as the new file. It does not test anything. No previous version of the trade file is in the data that the test uses.

The test uses production only, and 110 estimates. A country that replaced an estimate with an official value can be different from a country that did not.

The first 2 versions come from a copy on GitHub that FAO did not make. The new official value is not the correct value. It is only the nearest value that the data give.

## References

- `CONFIDENCE_METHOD.md` is the specification of the range and the score.
- `DATA_SOURCES.md` is the specification of the data.
