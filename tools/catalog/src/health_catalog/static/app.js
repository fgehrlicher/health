const $ = (selector) => document.querySelector(selector);
const filterIds = ['group', 'source-name', 'kind', 'preparation-state', 'min-protein', 'min-protein-density', 'min-fiber', 'max-energy'];
const queryNames = { 'source-name': 'source_name', 'preparation-state': 'preparation_state', 'min-protein': 'min_protein', 'min-protein-density': 'min_protein_density', 'min-fiber': 'min_fiber', 'max-energy': 'max_energy' };
const sortFields = { name: 'name', group_code: 'group', source_name: 'source', energy_kcal: 'energy', protein_g: 'protein', protein_per_100_kcal: 'protein_density', fat_g: 'fat', carbs_g: 'carbs', fiber_g: 'fiber' };
let table;
let searchTimer;
let groupNames = {};

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]);
}

function number(value, digits = 1) {
  return value == null ? '—' : new Intl.NumberFormat(undefined, { maximumFractionDigits: digits }).format(Number(value));
}

function basis(source) {
  return source ? `per ${number(source.reference_quantity)} ${source.reference_unit}` : 'No source';
}

function setStatus(online) {
  $('#connection-status').classList.toggle('offline', !online);
  $('#connection-status').textContent = online ? 'Local database connected' : 'Database unavailable';
}

async function getJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  return response.json();
}

function readUrl() {
  const params = new URLSearchParams(location.search);
  $('#search').value = params.get('q') || '';
  for (const id of filterIds) $('#' + id).value = params.get(queryNames[id] || id) || '';
}

function filterParams() {
  const params = new URLSearchParams();
  const q = $('#search').value.trim();
  if (q) params.set('q', q);
  for (const id of filterIds) {
    const value = $('#' + id).value;
    if (value) params.set(queryNames[id] || id, value);
  }
  return params;
}

function reload() {
  const params = filterParams();
  history.replaceState(null, '', params.size ? `?${params}` : location.pathname);
  table.setData('/api/foods');
}

function addOptions(id, values, label = (value) => value) {
  const select = $('#' + id);
  const selected = select.value;
  for (const value of values) {
    const option = document.createElement('option');
    option.value = typeof value === 'string' ? value : value.code;
    option.textContent = label(value);
    select.append(option);
  }
  select.value = selected;
}

async function loadFacets() {
  try {
    const facets = await getJson('/api/foods/facets');
    $('#catalog-count').textContent = `${number(facets.foods, 0)} foods · ${number(facets.sources, 0)} nutrition sources`;
    groupNames = Object.fromEntries(facets.groups.map((group) => [group.code, group.name]));
    addOptions('group', facets.groups, (group) => `${group.name} (${number(group.count, 0)})`);
    addOptions('source-name', facets.source_names);
    addOptions('kind', facets.kinds);
    addOptions('preparation-state', facets.preparation_states);
    readUrl();
    setStatus(true);
  } catch (_) { setStatus(false); }
}

function sortParam(sorters) {
  const sorter = sorters?.[0];
  if (!sorter) return 'relevance';
  const field = sortFields[sorter.field];
  if (!field) return 'relevance';
  if (field === 'name') return sorter.dir === 'desc' ? 'name_desc' : 'name';
  return `${field}_${sorter.dir === 'desc' ? 'desc' : 'asc'}`;
}

function tableRow(food) {
  const source = food.source;
  return {
    slug: food.slug,
    name: food.name,
    secondary: food.brand || food.aliases.find((alias) => alias !== food.name) || '',
    group_code: source?.group_code || null,
    source_name: source?.source_name || null,
    energy_kcal: source?.energy_kcal == null ? null : Number(source.energy_kcal),
    protein_g: source?.protein_g == null ? null : Number(source.protein_g),
    protein_per_100_kcal: source?.protein_per_100_kcal == null ? null : Number(source.protein_per_100_kcal),
    fat_g: source?.fat_g == null ? null : Number(source.fat_g),
    carbs_g: source?.carbs_g == null ? null : Number(source.carbs_g),
    fiber_g: source?.fiber_g == null ? null : Number(source.fiber_g),
  };
}

async function requestPage(_url, _config, params) {
  const page = Number(params.page) || 1;
  const size = Number(params.size) || 50;
  const query = filterParams();
  query.set('sort', sortParam(params.sort));
  query.set('limit', String(size));
  query.set('offset', String((page - 1) * size));
  const payload = await getJson(`/api/foods?${query}`);
  $('#result-count').textContent = `${number(payload.total, 0)} ${payload.total === 1 ? 'food' : 'foods'}`;
  setStatus(true);
  return { last_page: Math.max(1, Math.ceil(payload.total / size)), last_row: payload.total, data: payload.items.map(tableRow) };
}

function nameCell(cell) {
  const row = cell.getRow().getData();
  return `<span class="food-name">${escapeHtml(row.name)}</span><span class="food-secondary">${escapeHtml(row.secondary)}</span>`;
}

function groupCell(cell) {
  const code = cell.getValue();
  return escapeHtml(code ? `${groupNames[code] || code} (${code})` : '—');
}

function numericCell(cell) {
  return number(cell.getValue());
}

function initTable() {
  table = new Tabulator('#food-table', {
    index: 'slug',
    ajaxURL: '/api/foods',
    ajaxRequestFunc: requestPage,
    pagination: true,
    paginationMode: 'remote',
    paginationSize: 50,
    paginationSizeSelector: [25, 50, 100],
    paginationCounter: 'rows',
    sortMode: 'remote',
    headerSortMulti: false,
    layout: 'fitColumns',
    responsiveLayout: 'collapse',
    responsiveLayoutCollapseStartOpen: false,
    movableColumns: true,
    placeholder: 'No matching foods',
    rowFormatter: (row) => {
      const element = row.getElement();
      element.tabIndex = 0;
      element.onkeydown = (event) => {
        if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); openFood(row.getData().slug); }
      };
    },
    rowHeader: { formatter: 'responsiveCollapse', width: 40, minWidth: 40, hozAlign: 'center', headerSort: false, resizable: false },
    columns: [
      { title: 'Food', field: 'name', minWidth: 220, widthGrow: 3, responsive: 0, formatter: nameCell, variableHeight: true },
      { title: 'Group', field: 'group_code', minWidth: 160, widthGrow: 1.4, responsive: 2, formatter: groupCell },
      { title: 'kcal', field: 'energy_kcal', width: 85, minWidth: 70, hozAlign: 'right', responsive: 0, formatter: numericCell },
      { title: 'Protein', field: 'protein_g', width: 104, minWidth: 90, hozAlign: 'right', responsive: 1, formatter: numericCell },
      { title: 'Protein / 100 kcal', field: 'protein_per_100_kcal', width: 180, minWidth: 155, hozAlign: 'right', responsive: 1, formatter: numericCell },
      { title: 'Fat', field: 'fat_g', width: 82, minWidth: 68, hozAlign: 'right', responsive: 3, formatter: numericCell },
      { title: 'Carbs', field: 'carbs_g', width: 88, minWidth: 70, hozAlign: 'right', responsive: 3, formatter: numericCell },
      { title: 'Fiber', field: 'fiber_g', width: 82, minWidth: 68, hozAlign: 'right', responsive: 3, formatter: numericCell },
      { title: 'Source', field: 'source_name', width: 105, minWidth: 85, responsive: 5 },
    ],
  });
  table.on('rowClick', (_event, row) => openFood(row.getData().slug));
  table.on('dataLoadError', () => {
    $('#result-count').textContent = 'Could not load foods';
    setStatus(false);
  });
}

function sourceMarkup(source) {
  // [label, column, sub-row of the row above]; optional rows only when known.
  const nutrition = [
    ['Fat', 'fat_g'], ['saturated', 'saturated_fat_g', true],
    ['Carbs', 'carbs_g'], ['sugars', 'sugars_g', true], ['polyols', 'polyols_g', true, true],
    ['Fiber', 'fiber_g'], ['Protein', 'protein_g'], ['Salt', 'salt_g'], ['Alcohol', 'alcohol_g', false, true],
  ].filter(([, field, , optional]) => !optional || Number(source[field]) > 0);
  const gramsBasis = source.reference_unit === 'g' && Number(source.reference_quantity) === 100;
  const amount = (field) => `${source.upper_bounds.includes(field) ? '< ' : ''}${number(source[field])} g`;
  const row = ([label, field, sub]) => {
    const value = source[field];
    const bar = gramsBasis && value != null && !sub
      ? `<span class="bar-track" aria-hidden="true"><span class="bar-fill" style="width:${Math.max(0, Math.min(100, Number(value)))}%"></span></span>`
      : '<span></span>';
    return `<div class="nutrient-row nutrient-${field}${sub ? ' sub' : ''}"><span>${sub ? 'of which ' : ''}${label}</span><strong>${amount(field)}</strong>${bar}</div>`;
  };
  return `<section class="detail-source"><div class="detail-source-head"><strong>${escapeHtml(source.source_name)}</strong><span>${escapeHtml(basis(source))}</span></div>
    <p>${escapeHtml(source.food_name)}${source.external_id ? ` · ${escapeHtml(source.external_id)}` : ''}${source.group_code ? ` · ${escapeHtml(groupNames[source.group_code] || source.group_code)}` : ''}</p>
    <div class="energy-line">${number(source.energy_kcal, 0)} kcal <span>${number(source.energy_kj, 0)} kJ</span></div>
    <p class="protein-density">${number(source.protein_per_100_kcal)} g protein / 100 kcal</p>
    ${nutrition.map(row).join('')}
    ${gramsBasis ? '<p>Bars show grams in 100 g of food.</p>' : ''}</section>`;
}

function portionsMarkup(portions) {
  if (!portions.length) return '';
  const items = portions.map((portion) => `<li>${escapeHtml(portion.name)}: ${number(portion.quantity)} ${escapeHtml(portion.unit)}</li>`);
  return `<section class="detail-portions"><strong>Portions</strong><ul>${items.join('')}</ul></section>`;
}

async function openFood(slug) {
  const dialog = $('#food-dialog');
  $('#detail-content').textContent = 'Loading…';
  if (!dialog.open) dialog.showModal();
  try {
    const food = await getJson(`/api/foods/${encodeURIComponent(slug)}`);
    $('#detail-content').innerHTML = `<h2 id="detail-title">${escapeHtml(food.name)}</h2>
      <p class="detail-meta">${escapeHtml([food.kind, food.brand, food.preparation_state, ...food.aliases].filter(Boolean).join(' · '))}</p>
      ${food.sources.length ? food.sources.map(sourceMarkup).join('') : '<p>No nutrition source yet.</p>'}
      ${portionsMarkup(food.portions)}
      <p class="detail-note">A dash means the value is unknown, not zero. Each source has its own reference quantity.</p>`;
  } catch (_) { $('#detail-content').textContent = 'Could not load this food.'; }
}

readUrl();
loadFacets().then(initTable);
$('#search-form').addEventListener('submit', (event) => { event.preventDefault(); clearTimeout(searchTimer); if (table) reload(); });
$('#search').addEventListener('input', () => { clearTimeout(searchTimer); searchTimer = setTimeout(() => { if (table) reload(); }, 250); });
for (const id of filterIds) $('#' + id).addEventListener('change', () => { if (table) reload(); });
$('#clear-filters').addEventListener('click', () => { $('#search').value = ''; for (const id of filterIds) $('#' + id).value = ''; if (table) reload(); });
$('#close-dialog').addEventListener('click', () => $('#food-dialog').close());
$('#food-dialog').addEventListener('click', (event) => { if (event.target === $('#food-dialog')) $('#food-dialog').close(); });
window.addEventListener('popstate', () => { readUrl(); if (table) table.setData('/api/foods'); });
document.addEventListener('keydown', (event) => { if (event.key === '/' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) { event.preventDefault(); $('#search').focus(); } });
