// Loads aggregates.json + metadata.json. The aggregates cells array is the
// canonical query surface — each row is [dim indices..., n, released,
// released_with_rearrest_info, rearrested, vf_rearrested, fta]. There are
// 10 dimensions (charge, sev, attempt, vfo, nvfo, misd, pending, age,
// gender, boro) and 6 counter columns.

const DATA = {
    aggregates: null,
    metadata: null,
    labels: null,      // shortcut to aggregates.labels
    dims: null,        // dimension order
    ready: false,
};

async function loadData() {
    const [aggRes, metaRes] = await Promise.all([
        fetch('data/aggregates.json'),
        fetch('data/metadata.json'),
    ]);
    DATA.aggregates = await aggRes.json();
    DATA.metadata = await metaRes.json();
    DATA.labels = DATA.aggregates.labels;
    DATA.dims = DATA.aggregates.dims;
    DATA.ready = true;
    return DATA;
}
