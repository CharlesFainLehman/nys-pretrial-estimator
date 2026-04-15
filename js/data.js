// Loads aggregates.json + metadata.json and exposes a keyed Map for O(1) cell
// lookup. The packed key is the 9 dimension indices joined with commas.

const DATA = {
    aggregates: null,
    metadata: null,
    cellMap: null,     // Map<string, number[]>  key -> [n, released, r_w_info, rearr, vf, fta]
    labels: null,      // shortcut to aggregates.labels
    dims: null,        // dimension order
    ready: false,
};

function packKey(indices) {
    return indices.join(',');
}

async function loadData() {
    const [aggRes, metaRes] = await Promise.all([
        fetch('data/aggregates.json'),
        fetch('data/metadata.json'),
    ]);
    DATA.aggregates = await aggRes.json();
    DATA.metadata = await metaRes.json();
    DATA.labels = DATA.aggregates.labels;
    DATA.dims = DATA.aggregates.dims;

    // Build the lookup map. Each cell row is:
    //   [charge_i, sev_i, vfo_i, nvfo_i, misd_i, pend_i, age_i, gen_i, boro_i,
    //    n, released, r_w_info, rearrested, vf_rearrested, fta]
    const map = new Map();
    const DIM_COUNT = DATA.dims.length; // 9
    for (const row of DATA.aggregates.cells) {
        const key = row.slice(0, DIM_COUNT).join(',');
        map.set(key, row.slice(DIM_COUNT));
    }
    DATA.cellMap = map;
    DATA.ready = true;
    return DATA;
}
