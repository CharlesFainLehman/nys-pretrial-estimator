// Query DATA for a profile; return rates + sample size and comparison deltas.

const LOW_N_THRESHOLD = 30;

// Counter positions within the slice stored in DATA.cellMap values
const C = {
    n: 0,
    released: 1,
    released_with_info: 2,  // released AND rearrest outcome known
    rearrested: 3,
    vf_rearrested: 4,
    fta: 5,
};

function query(profile) {
    // profile is { charge, sev, vfo, nvfo, misd, pending, age, gender, boro } -> indices
    const dims = DATA.dims;
    const key = dims.map(d => profile[d]).join(',');
    const counts = DATA.cellMap.get(key);

    const out = {
        n: 0,
        released_count: 0,
        rates: {
            released: null,
            rearrested: null,
            vf: null,
            fta: null,
        },
        deltas: {
            released: null,
            rearrested: null,
            vf: null,
            fta: null,
        },
        flags: {
            released: false,
            rearrested: false,
            vf: false,
            fta: false,
            overall: false,
        },
    };

    if (!counts) {
        out.flags.overall = true;
        return out;
    }

    const n = counts[C.n];
    const released = counts[C.released];
    const releasedWithInfo = counts[C.released_with_info];
    const rearrested = counts[C.rearrested];
    const vf = counts[C.vf_rearrested];
    const fta = counts[C.fta];

    out.n = n;
    out.released_count = released;

    // released rate: released / n
    if (n > 0) {
        out.rates.released = released / n;
        out.flags.released = n < LOW_N_THRESHOLD;
    }
    // rearrest rate: conditional on released with known outcome
    if (releasedWithInfo > 0) {
        out.rates.rearrested = rearrested / releasedWithInfo;
        out.flags.rearrested = releasedWithInfo < LOW_N_THRESHOLD;
    }
    // vf rate: vf / rearrested
    if (rearrested > 0) {
        out.rates.vf = vf / rearrested;
        out.flags.vf = rearrested < LOW_N_THRESHOLD;
    }
    // fta rate: conditional on released (all release events have FTA info)
    if (released > 0) {
        out.rates.fta = fta / released;
        out.flags.fta = released < LOW_N_THRESHOLD;
    }

    // Comparison deltas
    const avg = DATA.metadata.overall_rates;
    const avgMap = {
        released: avg.released_of_n,
        rearrested: avg.rearrested_of_released,
        vf: avg.vf_of_rearrested,
        fta: avg.fta_of_released,
    };
    for (const k of ['released', 'rearrested', 'vf', 'fta']) {
        if (out.rates[k] !== null && avgMap[k] !== null) {
            out.deltas[k] = out.rates[k] - avgMap[k];
        }
    }

    out.flags.overall = n < LOW_N_THRESHOLD;
    return out;
}

function formatPct(x) {
    if (x === null || x === undefined || isNaN(x)) return '—';
    return (x * 100).toFixed(0) + '%';
}

function formatDelta(d) {
    if (d === null || d === undefined || isNaN(d)) return '';
    const pts = d * 100;
    const sign = pts > 0 ? '+' : '';
    return `${sign}${pts.toFixed(0)} pts`;
}

function formatN(n) {
    return n.toLocaleString('en-US');
}
