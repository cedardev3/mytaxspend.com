# mytaxspend.com

Interactive visualization of U.S. federal outlays by budget function and subfunction.

## Data

Figures come from:

- [OMB Historical Table 3.2](https://www.whitehouse.gov/omb/information-resources/budget/historical-tables/) (function and subfunction actuals)
- [Treasury Monthly Treasury Statement](https://fiscaldata.treasury.gov/datasets/monthly-treasury-statement/) (latest fiscal-year-to-date function totals)

Refresh the local dataset:

```bash
npm run refresh-budget
```

## Develop

```bash
npm install
npm run dev
```

## Build

Static export for Cloudflare Pages:

```bash
npm run build
```

Output is written to `out/`.
