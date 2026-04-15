#!/usr/bin/env python3
"""
Build a sparse aggregate lookup table for the NYC Pretrial Release Estimator.

Reads the raw DCJS Supplemental Pretrial Release CSVs (2019-2025), filters to
NYC boroughs, buckets defendant attributes, and produces:

  data/aggregates.json  -- sparse cell counts keyed by the 10-tuple
                           (charge, severity, attempt, prior_vfo, prior_nvfo,
                            prior_misd, any_pending, age, gender, borough)
  data/metadata.json    -- label tables, overall NYC rates, sample size, caveats

Usage:
    python scripts/build_aggregates.py --csv-dir "../NYS Pre-Trial Release Dashboard"
"""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

NYC_COUNTIES = {'Bronx', 'Kings', 'New York', 'Queens', 'Richmond'}
BOROUGHS = {
    'Bronx': 'Bronx',
    'Kings': 'Brooklyn',
    'New York': 'Manhattan',
    'Queens': 'Queens',
    'Richmond': 'Staten Island',
}
BOROUGH_ORDER = ['Bronx', 'Brooklyn', 'Manhattan', 'Queens', 'Staten Island']
COUNTY_TO_BORO_IDX = {c: BOROUGH_ORDER.index(BOROUGHS[c]) for c in NYC_COUNTIES}

CSV_FILES = [
    'NYS for Web 2019.csv',
    'NYS for Web 2020.csv',
    'NYS for Web 2021.csv',
    'NYS for Web 2022.csv',
    'NYS for Web 2023.csv',
    'NYS for Web 2024.csv',
    'NYS for Web 2025.csv',
]

SEV_ORDER = ['Felony', 'Misdemeanor']  # Violation too rare to bucket separately here
ATTEMPT_ORDER = ['Completed', 'Attempted']
PRIOR_VFO_BUCKETS = ['0', '1', '2+']
PRIOR_NVFO_BUCKETS = ['0', '1', '2+']
PRIOR_MISD_BUCKETS = ['0', '1-2', '3+']
PENDING_BUCKETS = ['No', 'Yes']
AGE_BUCKETS = ['18-20', '21-24', '25-34', '35-49', '50+']
GENDER_ORDER = ['Male', 'Female']


def bucket_prior(val, breakpoints):
    """breakpoints like [(1, '0'), (2, '1'), (float('inf'), '2+')] — return bucket."""
    try:
        n = int(val)
    except (ValueError, TypeError):
        return None
    for cap, label in breakpoints:
        if n < cap:
            return label
    return breakpoints[-1][1]


VFO_BREAKS = [(1, '0'), (2, '1'), (float('inf'), '2+')]
NVFO_BREAKS = [(1, '0'), (2, '1'), (float('inf'), '2+')]
MISD_BREAKS = [(1, '0'), (3, '1-2'), (float('inf'), '3+')]


def bucket_age(val):
    try:
        a = int(val)
    except (ValueError, TypeError):
        return None
    if a < 18:
        return None
    if a < 21:
        return '18-20'
    if a < 25:
        return '21-24'
    if a < 35:
        return '25-34'
    if a < 50:
        return '35-49'
    return '50+'


def any_pending(row):
    """Return 'Yes' if any pend_* is '1', 'No' if all are '0' or NULL."""
    vals = [row.get('pend_vfo', ''), row.get('pend_nonvfo', ''), row.get('pend_misd', '')]
    if any(v == '1' for v in vals):
        return 'Yes'
    return 'No'


def classify_row(row):
    """Return tuple of dimension labels, or None if row should be excluded.

    Also returns (released_flag, rearrested_flag, vf_rearrested_flag, fta_flag,
    has_rearrest_info) for counters.
    """
    county = (row.get('County_Name') or '').strip()
    if county not in NYC_COUNTIES:
        return None

    category = (row.get('Arraign Charge Category') or '').strip()
    if not category:
        return None

    sev = (row.get('Top_Severity_at_Arraign') or '').strip()
    if sev not in SEV_ORDER:
        return None

    attempt_raw = (row.get('Top_Arraign_Attempt_Indicator') or '').strip()
    attempt = 'Attempted' if attempt_raw == 'Attempt' else 'Completed'

    gender = (row.get('Gender') or '').strip()
    if gender not in GENDER_ORDER:
        return None

    age_bucket = bucket_age(row.get('Age_at_Arrest'))
    if age_bucket is None:
        return None

    vfo = bucket_prior(row.get('prior_vfo_cnt'), VFO_BREAKS)
    nvfo = bucket_prior(row.get('prior_nonvfo_cnt'), NVFO_BREAKS)
    misd = bucket_prior(row.get('prior_misd_cnt'), MISD_BREAKS)
    if vfo is None or nvfo is None or misd is None:
        return None

    pend = any_pending(row)

    release = (row.get('Release Decision at Arraign') or '').strip()
    # Exclude rows without a clear release/detention decision
    if release not in ('ROR', 'Nonmonetary release', 'Bail-set', 'Remanded'):
        return None

    # Released = ROR, NMR, or Bail-set with bail actually posted
    bail_made = (row.get('Bail_Made_Indicator') or '').strip()
    if release == 'ROR' or release == 'Nonmonetary release':
        released = 1
    elif release == 'Bail-set' and bail_made:
        released = 1
    else:
        released = 0

    # Rearrest (only meaningful if released; NULL = case still pending)
    rearrest = (row.get('rearrest') or '').strip()
    has_rearrest_info = rearrest in ('No Arrest', 'Misdemeanor', 'Non-Violent Felony', 'Violent Felony')
    rearrested = 1 if rearrest in ('Misdemeanor', 'Non-Violent Felony', 'Violent Felony') else 0
    vf_rearrested = 1 if rearrest == 'Violent Felony' else 0

    fta_raw = (row.get('Warrant_Ordered_btw_Arraign_and_Dispo') or '').strip()
    fta = 1 if fta_raw == 'Y' else 0

    dims = (category, sev, attempt, vfo, nvfo, misd, pend, age_bucket, gender, COUNTY_TO_BORO_IDX[county])
    counters = {
        'released': released,
        'rearrested': released * rearrested * (1 if has_rearrest_info else 0),
        'vf_rearrested': released * vf_rearrested * (1 if has_rearrest_info else 0),
        'fta': released * fta,
        'has_rearrest_info': has_rearrest_info,
    }
    return dims, counters


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv-dir', required=True, help='Directory containing NYS for Web *.csv')
    ap.add_argument('--out-dir', default=str(Path(__file__).parent.parent / 'data'))
    args = ap.parse_args()

    csv_dir = Path(args.csv_dir).expanduser()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Discover all unique charge categories by pre-scanning (stable ordering)
    categories = set()

    # Aggregate: key -> [n, released, released_with_rearrest_info,
    #                    rearrested, vf_rearrested, fta]
    agg = defaultdict(lambda: [0, 0, 0, 0, 0, 0])

    overall = {
        'n': 0,
        'released': 0,
        'released_with_rearrest_info': 0,
        'rearrested': 0,
        'vf_rearrested': 0,
        'fta': 0,
    }

    total_rows = 0
    kept_rows = 0
    per_year = defaultdict(int)

    for fname in CSV_FILES:
        path = csv_dir / fname
        if not path.exists():
            print(f'  skip (missing): {path}')
            continue
        year = int(fname.split()[-1].split('.')[0])
        print(f'Reading {fname} ...', flush=True)
        with open(path, 'r', encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                total_rows += 1
                result = classify_row(row)
                if result is None:
                    continue
                dims, c = result
                kept_rows += 1
                per_year[year] += 1
                categories.add(dims[0])

                arr = agg[dims]
                arr[0] += 1  # n
                arr[1] += c['released']
                arr[2] += c['released'] * (1 if c['has_rearrest_info'] else 0)
                arr[3] += c['rearrested']
                arr[4] += c['vf_rearrested']
                arr[5] += c['fta']

                overall['n'] += 1
                overall['released'] += c['released']
                overall['released_with_rearrest_info'] += c['released'] * (1 if c['has_rearrest_info'] else 0)
                overall['rearrested'] += c['rearrested']
                overall['vf_rearrested'] += c['vf_rearrested']
                overall['fta'] += c['fta']

    print(f'\nTotal raw rows read: {total_rows:,}')
    print(f'Rows kept (NYC, valid dims, release decision): {kept_rows:,}')
    print(f'Unique cells: {len(agg):,}')
    print(f'By year: {dict(sorted(per_year.items()))}')

    # Build label tables
    charge_labels = sorted(categories)
    charge_idx = {c: i for i, c in enumerate(charge_labels)}
    sev_idx = {s: i for i, s in enumerate(SEV_ORDER)}
    attempt_idx = {a: i for i, a in enumerate(ATTEMPT_ORDER)}
    vfo_idx = {v: i for i, v in enumerate(PRIOR_VFO_BUCKETS)}
    nvfo_idx = {v: i for i, v in enumerate(PRIOR_NVFO_BUCKETS)}
    misd_idx = {v: i for i, v in enumerate(PRIOR_MISD_BUCKETS)}
    pend_idx = {v: i for i, v in enumerate(PENDING_BUCKETS)}
    age_idx = {v: i for i, v in enumerate(AGE_BUCKETS)}
    gender_idx = {v: i for i, v in enumerate(GENDER_ORDER)}

    cells = []
    for key, counts in agg.items():
        cat, sev, attempt, vfo, nvfo, misd, pend, age, gen, boro = key
        row = [
            charge_idx[cat], sev_idx[sev], attempt_idx[attempt],
            vfo_idx[vfo], nvfo_idx[nvfo], misd_idx[misd], pend_idx[pend],
            age_idx[age], gender_idx[gen], boro,
        ] + counts
        cells.append(row)
    cells.sort()

    aggregates = {
        'dims': ['charge', 'sev', 'attempt', 'vfo', 'nvfo', 'misd', 'pending', 'age', 'gender', 'boro'],
        'labels': {
            'charge': charge_labels,
            'sev': SEV_ORDER,
            'attempt': ATTEMPT_ORDER,
            'vfo': PRIOR_VFO_BUCKETS,
            'nvfo': PRIOR_NVFO_BUCKETS,
            'misd': PRIOR_MISD_BUCKETS,
            'pending': PENDING_BUCKETS,
            'age': AGE_BUCKETS,
            'gender': GENDER_ORDER,
            'boro': BOROUGH_ORDER,
        },
        'counters': ['n', 'released', 'released_with_rearrest_info',
                     'rearrested', 'vf_rearrested', 'fta'],
        'cells': cells,
    }

    # Overall rates for comparison
    def safe_div(a, b):
        return (a / b) if b else None

    overall_rates = {
        'released_of_n': safe_div(overall['released'], overall['n']),
        'rearrested_of_released': safe_div(overall['rearrested'], overall['released_with_rearrest_info']),
        'vf_of_rearrested': safe_div(overall['vf_rearrested'], overall['rearrested']),
        'fta_of_released': safe_div(overall['fta'], overall['released']),
    }

    metadata = {
        'source': 'https://ww2.nycourts.gov/pretrial-release-data-33136',
        'source_name': 'NYS Division of Criminal Justice Services (DCJS)',
        'description': 'Supplemental Pretrial Release Data File, NYC boroughs only, 2019-2025 pooled',
        'scope': {
            'geography': 'New York City (Bronx, Brooklyn, Manhattan, Queens, Staten Island)',
            'years': sorted(per_year.keys()),
            'total_arraignments': kept_rows,
            'per_year': dict(sorted(per_year.items())),
        },
        'overall_rates': overall_rates,
        'overall_counts': overall,
        'caveats': [
            '2019 is pre-bail-reform; pooling across years mixes regimes.',
            '2025 contains only partial-year data.',
            'Superior Court data pre-2022 may be incomplete.',
            'Rows with missing severity, age, gender, priors, or a clear release decision are excluded.',
            'NULL rearrest values (case still pending at disposition) are excluded from rearrest denominator.',
        ],
    }

    agg_path = out_dir / 'aggregates.json'
    meta_path = out_dir / 'metadata.json'
    with open(agg_path, 'w') as f:
        json.dump(aggregates, f, separators=(',', ':'))
    with open(meta_path, 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f'\nWrote {agg_path} ({agg_path.stat().st_size/1024:.0f} KB)')
    print(f'Wrote {meta_path}')

    # Spot-check sums (dim count + counter offset n = 10 after adding attempt)
    dim_count = len(aggregates['dims'])
    sum_n = sum(c[dim_count] for c in cells)
    print(f'\nSpot check: sum(n) over cells = {sum_n:,}  kept_rows = {kept_rows:,}  '
          f'{"MATCH" if sum_n == kept_rows else "MISMATCH"}')
    print(f'Overall rates:')
    for k, v in overall_rates.items():
        print(f'  {k}: {v:.3f}' if v is not None else f'  {k}: n/a')


if __name__ == '__main__':
    main()
