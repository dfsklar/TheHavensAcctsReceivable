# REVAMP2026 marketplace stats

Each month, export three CSVs into `downloads_from_marketplaces/` and run the wrapper. It runs the Airbnb and VRBO scripts, prints each TSV separately, then totals **payroll per employee** and **prepay per employee** across both marketplaces.

## Monthly files

1. Airbnb transaction-history CSV  
2. VRBO LodgingTaxReport CSV  
3. VRBO PayoutSummaryReport CSV

## How to run

From this `REVAMP2026` folder:

```
python compute_monthly_stats.py AIRBNB.csv LODGING_TAX.csv PAYOUT_SUMMARY.csv
```

Example for August 2026:

```
python compute_monthly_stats.py downloads_from_marketplaces/airbnb_08_2026-08_2026.csv downloads_from_marketplaces/LodgingTaxReport_2026-08-01_2026-08-31.csv.csv downloads_from_marketplaces/PayoutSummaryReport_2026-08-01_2026-08-31.csv.csv
```

Keep the three arguments in that order. Swap in the new month’s files each time.

## Output

1. **Airbnb** TSV (taxable income, host fees, occupancy, GST/Alberta pass-through, payroll/prepay)  
2. **VRBO** TSV (same occupancy rows, plus VRBO taxable income, fees, payouts, payroll/prepay)  
3. **Combined** TSV:

```
payroll per employee	<sum>	CAD
prepay per employee	<sum>	CAD
```

Copy the tab-separated rows into Google Sheets.

USD amounts are converted to CAD with Bank of Canada `FXUSDCAD` rates for each row date. The scripts abort immediately if that FX data is missing or looks erroneous.
