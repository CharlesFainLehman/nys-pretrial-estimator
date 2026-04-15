# NYC Pretrial Release Estimator

A static web tool that takes a defendant profile — top charge, priors, age, gender, borough — and returns empirical probabilities drawn from ~637,000 NYC adult arraignments (2020–2025, DCJS Supplemental Pretrial Release Data File):

1. **Released at arraignment**
2. **Rearrested** while the case was pending (conditional on release)
3. **Violent-felony rearrest** (conditional on being rearrested)
4. **Failure to appear** in court (conditional on release)

Each rate is shown alongside the NYC overall average so users can see how a given profile compares.

## How it works

The raw DCJS CSVs (~1 GB total) are too large for GitHub, so they're kept out of the repo (`.gitignore`). `scripts/build_aggregates.py` reads them, filters to NYC, buckets each row on nine dimensions, and writes a sparse JSON lookup table (~1 MB) that the browser loads at page load. Rate math happens entirely client-side — no server, no API keys, no database.

### Dimensions

| Dimension | Buckets |
|---|---|
| Arraign charge category | 18 (Assault, Burglary, Drug, Robbery, …) |
| Severity at arraignment | Felony / Misdemeanor |
| Prior violent felonies | 0 / 1 / 2+ |
| Prior non-violent felonies | 0 / 1 / 2+ |
| Prior misdemeanors | 0 / 1–2 / 3+ |
| Any pending case | Yes / No |
| Age at arrest | 18–20 / 21–24 / 25–34 / 35–49 / 50+ |
| Gender | Male / Female |
| Borough | Bronx / Brooklyn / Manhattan / Queens / Staten Island |

Rows missing any dimension (or where the release decision is "Disposed at arraign" or "Unknown") are excluded to keep the denominator clean. Race is intentionally not exposed as a predictor.

## Regenerating the data

You need the raw DCJS CSVs (download from [nycourts.gov](https://ww2.nycourts.gov/pretrial-release-data-33136)). Place them in a folder (the default assumes a sibling directory) and run:

```bash
python3 scripts/build_aggregates.py --csv-dir /path/to/csvs
```

This writes `data/aggregates.json` and `data/metadata.json`. Both are checked into the repo; the CSVs are not.

## Running locally

```bash
python3 -m http.server 8000
# then open http://localhost:8000
```

## Deploying to GitHub Pages

1. Create an empty GitHub repo (via `gh repo create` or the web UI).
2. `git remote add origin git@github.com:USER/nys-pretrial-estimator.git`
3. `git push -u origin main`
4. In the repo's **Settings → Pages**, pick **Deploy from a branch**, select `main` / `/ (root)`, and save. The site will be live at `https://USER.github.io/nys-pretrial-estimator/` within a minute.

## Caveats

- 2025 is partial-year data.
- Superior Court data pre-2022 may be incomplete.
- Pooling 2020–2025 mixes several generations of bail-reform rules. Rates should be read as an average across that window, not a prediction of current practice.
- Rearrest denominators exclude cases where the rearrest outcome was still pending (NULL) at the time of the DCJS extract.
- Cells with fewer than 30 matching arraignments are flagged visually — those numbers are noisy.

## Source

NYS Division of Criminal Justice Services, [Supplemental Pretrial Release Data File](https://ww2.nycourts.gov/pretrial-release-data-33136). Adults (18+) arrested on fingerprinted charges.
