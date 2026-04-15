// Orchestration: populate selects, wire changes, render outputs.

const FIELD_TO_DIM = {
    'f-charge': 'charge',
    'f-sev': 'sev',
    'f-boro': 'boro',
    'f-age': 'age',
    'f-gender': 'gender',
    'f-vfo': 'vfo',
    'f-nvfo': 'nvfo',
    'f-misd': 'misd',
    'f-pending': 'pending',
};

// Human-readable labels for bucket keys where the raw label reads awkwardly
function formatOption(dim, label) {
    if (dim === 'vfo' || dim === 'nvfo') {
        return label + ' prior';
    }
    if (dim === 'misd') {
        return label + ' prior';
    }
    if (dim === 'pending') {
        return label === 'Yes' ? 'Yes, has pending case' : 'No pending case';
    }
    if (dim === 'age') {
        return 'Age ' + label;
    }
    return label;
}

// Dimensions that should offer an "All" option (everything except charge).
const ALLOW_ALL = new Set(['sev', 'boro', 'age', 'gender', 'vfo', 'nvfo', 'misd', 'pending']);

function populateSelects() {
    for (const [fieldId, dim] of Object.entries(FIELD_TO_DIM)) {
        const sel = document.getElementById(fieldId);
        const labels = DATA.labels[dim];
        sel.innerHTML = '';

        if (ALLOW_ALL.has(dim)) {
            const opt = document.createElement('option');
            opt.value = 'all';
            opt.textContent = 'All';
            sel.appendChild(opt);
        }

        labels.forEach((label, i) => {
            const opt = document.createElement('option');
            opt.value = String(i);
            opt.textContent = formatOption(dim, label);
            sel.appendChild(opt);
        });
    }

    // Default: pick a charge (Assault) and leave every other dimension on "All".
    const chargeIdx = DATA.labels.charge.indexOf('Assault');
    if (chargeIdx >= 0) document.getElementById('f-charge').value = String(chargeIdx);
    for (const dim of ALLOW_ALL) {
        const fieldId = Object.keys(FIELD_TO_DIM).find(k => FIELD_TO_DIM[k] === dim);
        document.getElementById(fieldId).value = 'all';
    }
}

function currentProfile() {
    const profile = {};
    for (const [fieldId, dim] of Object.entries(FIELD_TO_DIM)) {
        const raw = document.getElementById(fieldId).value;
        profile[dim] = raw === 'all' ? 'all' : parseInt(raw, 10);
    }
    return profile;
}

function renderResult(result) {
    const sampleEl = document.getElementById('sample-n');
    const sampleNoteEl = document.getElementById('sample-note');
    sampleEl.textContent = formatN(result.n);

    if (result.n === 0) {
        sampleNoteEl.textContent = 'No matching arraignments — try broadening the profile';
        sampleNoteEl.classList.add('low-n');
    } else if (result.n < 30) {
        sampleNoteEl.textContent = 'Small sample — interpret with caution';
        sampleNoteEl.classList.add('low-n');
    } else {
        sampleNoteEl.textContent = '';
        sampleNoteEl.classList.remove('low-n');
    }

    const cards = [
        { key: 'released', valEl: 'v-released', cmpEl: 'c-released' },
        { key: 'rearrested', valEl: 'v-rearrested', cmpEl: 'c-rearrested' },
        { key: 'vf', valEl: 'v-vf', cmpEl: 'c-vf' },
        { key: 'fta', valEl: 'v-fta', cmpEl: 'c-fta' },
    ];

    for (const c of cards) {
        const rate = result.rates[c.key];
        const delta = result.deltas[c.key];
        const flag = result.flags[c.key];

        const valEl = document.getElementById(c.valEl);
        const cmpEl = document.getElementById(c.cmpEl);

        valEl.classList.remove('flagged', 'muted');
        if (rate === null) {
            valEl.textContent = '—';
            valEl.classList.add('muted');
            cmpEl.innerHTML = '<span style="color:var(--text-subtle)">insufficient data</span>';
            continue;
        }

        valEl.textContent = formatPct(rate);
        if (flag) valEl.classList.add('flagged');

        if (delta === null) {
            cmpEl.textContent = '';
        } else {
            const pts = delta * 100;
            let cls = 'delta';
            if (Math.abs(pts) < 0.5) {
                cls += '';
                cmpEl.innerHTML = `<span class="${cls}">at NYC average</span>`;
            } else {
                cls += pts > 0 ? ' above' : ' below';
                cmpEl.innerHTML = `vs NYC avg: <span class="${cls}">${formatDelta(delta)}</span>`;
            }
        }
    }
}

function refresh() {
    const profile = currentProfile();
    const result = query(profile);
    renderResult(result);
}

function wireEvents() {
    for (const fieldId of Object.keys(FIELD_TO_DIM)) {
        document.getElementById(fieldId).addEventListener('change', refresh);
    }
}

async function init() {
    try {
        await loadData();
        populateSelects();
        wireEvents();
        refresh();
    } catch (e) {
        console.error('Failed to load data:', e);
        document.getElementById('sample-note').textContent = 'Error loading data';
    }
}

document.addEventListener('DOMContentLoaded', init);
