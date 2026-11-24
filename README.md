# Electricity milestones: one-household historical case study

This reproducible analysis describes historical minute-average electricity
measurements for **one household in Sceaux, France**. It does not represent the
user's home or households generally, and daily/hour-of-day aggregates cannot
identify appliance use, household behavior, or savings.

## Source and method

The source is the [UCI Individual household electric power consumption
dataset](https://archive.ics.uci.edu/dataset/235/individual+household+electric+power+consumption)
(DOI: [10.24432/C58K54](https://doi.org/10.24432/C58K54), CC BY 4.0). The dataset
was donated on 2012-08-29; its observations span 2006-12-16 through 2010-11-26.
The checked-in ZIP is the input. The workflow validates that it contains only
the expected `household_power_consumption.txt` member, then streams rows from
the ZIP; it never writes the roughly 133 MB member to disk.

`Global_active_power` is a minute-average in kW. For each date, the analysis
sums valid minute values and divides by 60 to produce kWh. The source uses `?`
for missing active power; these minutes are excluded, never imputed. The CSV
reports expected, observed, and valid minutes and both observed and valid
coverage. Expected slots are clipped to the first and last timestamps, so
partial boundary dates are not treated as full days. A day is complete only if
it is a full 1,440-minute calendar day with all 1,440 active-power values.
Timestamps are kept timezone-naive because the source does not specify a
timezone.

The e03 milestone also groups valid minute-average active power by the source
clock hour (00:00 through 23:00) across the full observation period. The hourly
mean is the arithmetic mean of valid minute readings in kW; its CSV row also
reports expected, observed, and valid minute counts and valid coverage. An
hour-of-day group is complete only when at least 90% of all expected minute
slots for that source clock hour have valid readings. Expected slots cover the
inclusive first-to-last timestamp span, including gaps; incomplete groups stay
in the CSV with a `false` status and no mean, and are visibly marked in the
chart. The 90% threshold is applied across the multi-year group, not
independently to each date. No timezone or daylight-saving adjustment is
inferred. The `e03` / `2024-08-07` coverage label is a topic label, not the
execution date.

Exact energy-conversion code from `analysis/household_power.py`:

```python
energy = record.active_power_sum_kw / Decimal(60)
```

## Findings

The stream contained **2,075,259 minute rows** over **1,442 dates**, from
2006-12-16 17:24 through 2010-11-26 21:02. There were no duplicate, out-of-order,
or skipped timestamp slots. **25,979 active-power values (1.251844%)** were
marked missing; **1,358 days** have complete coverage, and **84** are partial or
incomplete. The first and last dates contain 396 and 1,263 expected minutes,
respectively.

The April 29, 2007 row has a numerical energy value of `0.000000 kWh` because
all 1,440 active-power values are missing. Its valid coverage is 0%, and it is
explicitly marked incomplete: this is missing data, not evidence of zero use.

| Date | Daily energy (kWh) | Expected minutes | Valid power minutes | Complete |
|---|---:|---:|---:|:---:|
| 2006-12-16 | 20.152933 | 396 | 396 | no |
| 2006-12-17 | 56.507667 | 1,440 | 1,440 | yes |
| 2007-04-29 | 0.000000 | 1,440 | 0 | no |
| 2010-11-26 | 24.801733 | 1,263 | 1,263 | no |

The e03 output adds one row for each of the 24 source clock hours. Hourly means
describe aggregate recorded readings only; they do not imply appliance use,
household behavior, or savings. In this run, all 24 groups meet the 90%
coverage rule; valid coverage ranges from 98.598% to 98.959%. Means range from
0.443847 kW at 04:00 to 1.899064 kW at 20:00 in the source clock.

## Reproduce

Requires Python 3 and only its standard library; there are no third-party
runtime dependencies.

```sh
python3 analysis/household_power.py
python3 -m unittest discover -s tests -v
```

The workflow writes these exports under `outputs/`:

- `daily_consumption.svg` — accessible daily-energy series; blue marks complete
  days, orange marks partial or lower-coverage days. Each plotted point also
  carries its CSV date, energy, and coverage values.
- `daily_consumption.csv` — dated kWh and observation-coverage aggregates.
- `hourly_active_power.svg` — accessible source-clock-hour mean-power chart;
  tooltips report valid/expected readings and coverage, and incomplete means
  are omitted.
- `hourly_active_power.csv` — 24 hour-of-day aggregates with mean kW,
  expected/observed/valid readings, coverage, the 90% threshold, and status.
- `quality_summary.json` — row, missingness, timestamp, and coverage summary.
- `export_metadata.json` — question, source vintage and URLs, observation
  boundaries, input commit/blob/SHA-256, analysis revision, actual
  timezone-bearing execution timestamp, daily and hourly methods, limitations,
  and outputs.
  `publication_date` is null; no publication is implied.

The input commit, blob ID, and local SHA-256 are provenance for the ZIP, not
claims about when the historical observations were collected. The execution
timestamp and code revision in the metadata record this run, not the data
vintage or a publication date. There is no tariff estimate, forecasting,
causal inference, or inference about appliance use, household behavior, or
savings.
