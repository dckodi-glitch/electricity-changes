# First electricity milestone: one-household historical case study

This reproducible analysis describes historical minute-average electricity
measurements for **one household in Sceaux, France**. It does not represent the
user's home or households generally, and daily aggregates cannot identify
appliance-level use or savings.

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
- `quality_summary.json` — row, missingness, timestamp, and coverage summary.
- `export_metadata.json` — question, source vintage and URLs, observation
  boundaries, input commit/blob/SHA-256, analysis revision, actual
  timezone-bearing execution timestamp, methods, limitations, and outputs.
  `publication_date` is null; no publication is implied.

The input commit, blob ID, and local SHA-256 are provenance for the ZIP, not
claims about when the historical observations were collected. The execution
timestamp records this run, not the data vintage or a publication date. There
is no tariff estimate, forecasting, causal inference, or inference about
appliance savings.
