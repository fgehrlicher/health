const $ = (selector) => document.querySelector(selector);
const fieldIds = ['kind', 'source-name', 'preparation-state', 'min-protein', 'min-fiber', 'max-energy', 'sort'];
const queryKeys = {
  'source-name': 'source_name',
  'preparation-state': 'preparation_state',
  'min-protein': 'min_protein',
  'min-fiber': 'min_fiber',
  'max-energy': 'max_energy',
};
const pageSize = 24;
let offset = 0;
let currentRequest;
let searchTimer;

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[character]);
}

function prettyNumber(value, maximumFractionDigits = 2) {
  if (value === null || value === undefined) return '—';
  return new Intl.NumberFormat(undefined, { maximumFractionDigits }).format(Number(value));
}

function titleCase(value) {
  return value ? value.charAt(0).toUpperCase() + value.slice(1).replaceAll('_', ' ') : '';
}

function sourceBasis(source) {
  return source ? `per ${prettyNumber(source.reference_quantity)} ${source.reference_unit}` : 'No nutrition source';
}

function stateFromUrl() {
  const params = new URLSearchParams(window.location.search);
  $('#search').value = params.get('q') || '';
  for (const id of fieldIds) {
    $("#" + id).value = params.get(queryKeys[id] || id) || (id === 'sort' ? 'name' : '');
  }
  offset = Math.max(0, Number.parseInt(params.get('offset') || '0', 10) || 0);
  updateFilterBadge();
}

function paramsFromControls() {
  const params = new URLSearchParams();
  const q = $('#search').value.trim();
  if (q) params.set('q', q);
  for (const id of fieldIds) {
    const value = $('#' + id).value;
    if (value && !(id === 'sort' && value === 'name')) params.set(queryKeys[id] || id, value);
  }
  if (offset) params.set('offset', String(offset));
  return params;
}

function updateFilterBadge() {
  const active = fieldIds.filter((id) => id !== 'sort' && $('#' + id).value).length;
  $('#active-filter-count').textContent = active ? `${active} active` : 'Filters';
}

function updateUrlAndLoad() {
  updateFilterBadge();
  const params = paramsFromControls();
  const next = params.size ? `?${params}` : window.location.pathname;
  window.history.replaceState(null, '', next);
  loadFoods();
}

async function fetchJson(url, signal) {
  const response = await fetch(url, { signal });
  if (!response.ok) {
    const error = new Error(response.status === 503 ? 'The local database is unavailable.' : `Request failed (${response.status}).`);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

function setConnection(online) {
  const status = $('#connection-status');
  status.classList.toggle('is-offline', !online);
  status.lastChild.textContent = online ? ' Local catalog' : ' Database offline';
}

function addOptions(id, values) {
  const select = $('#' + id);
  const chosen = select.value;
  for (const value of values) {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = titleCase(value);
    select.append(option);
  }
  select.value = chosen;
}

async function loadFacets() {
  try {
    const facets = await fetchJson('/api/foods/facets');
    $('#total-foods').textContent = new Intl.NumberFormat().format(facets.foods);
    $('#total-sources').textContent = new Intl.NumberFormat().format(facets.sources);
    addOptions('kind', facets.kinds);
    addOptions('source-name', facets.source_names);
    addOptions('preparation-state', facets.preparation_states);
    stateFromUrl();
    setConnection(true);
  } catch (error) {
    setConnection(false);
  }
}

function cardMarkup(food) {
  const source = food.source;
  const subtitle = food.brand || food.aliases.find((alias) => alias !== food.name) || food.preparation_state || 'Ingredient';
  const values = [
    ['Energy', source?.energy_kcal, 'kcal'],
    ['Protein', source?.protein_g, 'g'],
    ['Carbs', source?.carbs_g, 'g'],
    ['Fiber', source?.fiber_g, 'g'],
  ];
  return `
    <div class="food-card-top"><span class="kind-pill">${escapeHtml(food.kind)}</span><span class="food-card-arrow" aria-hidden="true">↗</span></div>
    <h4>${escapeHtml(food.name)}</h4>
    <div class="food-card-subtitle">${escapeHtml(subtitle)}</div>
    <div class="macro-strip">${values.map(([label, value, unit]) => `<div><span class="macro-value">${escapeHtml(prettyNumber(value))}</span><span class="macro-label">${label} ${value === null || value === undefined ? '' : unit}</span></div>`).join('')}</div>
    <div class="card-source"><span>${escapeHtml(source?.source_name || 'No source yet')} · ${escapeHtml(sourceBasis(source))}</span><span>${food.source_count} ${food.source_count === 1 ? 'source' : 'sources'}</span></div>`;
}

function renderFoods(payload) {
  const grid = $('#food-grid');
  grid.replaceChildren();
  $('#result-count').textContent = `${new Intl.NumberFormat().format(payload.total)} ${payload.total === 1 ? 'food' : 'foods'} found`;
  if (!payload.items.length) {
    const empty = document.createElement('div');
    empty.className = 'empty-state';
    empty.innerHTML = `<span class="empty-state-symbol">✳</span><h4>Nothing in this corner yet.</h4><p>Try a broader search or clear some filters.</p>`;
    grid.append(empty);
  } else {
    for (const food of payload.items) {
      const card = document.createElement('button');
      card.type = 'button';
      card.className = 'food-card';
      card.setAttribute('aria-label', `View ${food.name} and its nutrition sources`);
      card.innerHTML = cardMarkup(food);
      card.addEventListener('click', () => openFood(food.slug));
      grid.append(card);
    }
  }
  const pagination = $('#pagination');
  pagination.hidden = payload.total <= pageSize;
  $('#previous-page').disabled = offset === 0;
  $('#next-page').disabled = offset + pageSize >= payload.total;
  $('#page-label').textContent = payload.total ? `${offset + 1}–${Math.min(offset + pageSize, payload.total)} of ${payload.total}` : '';
}

async function loadFoods() {
  if (currentRequest) currentRequest.abort();
  currentRequest = new AbortController();
  const query = paramsFromControls();
  query.set('limit', String(pageSize));
  try {
    const payload = await fetchJson(`/api/foods?${query}`, currentRequest.signal);
    renderFoods(payload);
    setConnection(true);
  } catch (error) {
    if (error.name === 'AbortError') return;
    const invalidFilter = error.status === 422;
    setConnection(invalidFilter);
    $('#result-count').textContent = invalidFilter ? 'Invalid filter' : 'Catalog unavailable';
    $('#food-grid').innerHTML = invalidFilter
      ? `<div class="empty-state"><span class="empty-state-symbol">◌</span><h4>That filter needs a second look.</h4><p>Check the values above or clear the filters.</p></div>`
      : `<div class="empty-state"><span class="empty-state-symbol">◌</span><h4>We can't reach your foods.</h4><p>Start PostgreSQL with <code>make db-up</code>, then refresh.</p></div>`;
    $('#pagination').hidden = true;
  }
}

function sourceMarkup(source) {
  const values = [
    ['Energy', source.energy_kcal, 'kcal'], ['Protein', source.protein_g, 'g'],
    ['Fat', source.fat_g, 'g'], ['Carbs', source.carbs_g, 'g'], ['Fiber', source.fiber_g, 'g'],
  ];
  return `<section class="detail-source"><div class="detail-source-heading"><strong>${escapeHtml(source.source_name)}</strong><span>${escapeHtml(sourceBasis(source))}</span></div>
    <p class="detail-source-food">${escapeHtml(source.food_name)}${source.external_id ? ` · ${escapeHtml(source.external_id)}` : ''}</p>
    <div class="detail-nutrients">${values.map(([label, value, unit]) => `<div><strong>${escapeHtml(value ?? '—')}</strong><span>${label} ${value === null ? '' : unit}</span></div>`).join('')}</div></section>`;
}

async function openFood(slug) {
  const dialog = $('#food-dialog');
  $('#detail-content').innerHTML = '<p class="detail-section-label">Loading food…</p>';
  if (!dialog.open) dialog.showModal();
  try {
    const food = await fetchJson(`/api/foods/${encodeURIComponent(slug)}`);
    const detail = $('#detail-content');
    detail.innerHTML = `<span class="kind-pill detail-kind">${escapeHtml(food.kind)}</span>
      <h2 class="detail-title" id="detail-title">${escapeHtml(food.name)}</h2>
      <p class="detail-meta">${[food.brand, food.preparation_state, ...food.aliases].filter(Boolean).map(escapeHtml).join(' · ') || 'No additional names recorded'}</p>
      <p class="detail-section-label">NUTRITION SOURCES / ${food.sources.length}</p>
      ${food.sources.length ? food.sources.map(sourceMarkup).join('') : '<p class="detail-meta">No nutrition source yet.</p>'}
      <p class="detail-note">Amounts belong to each named source and its reference quantity. A dash means the value is unknown—not zero.</p>`;
  } catch (error) {
    $('#detail-content').innerHTML = '<p class="detail-section-label">Could not load this food. Please try again.</p>';
  }
}

function initializeTheme() {
  const saved = window.localStorage.getItem('food-atlas-theme');
  const dark = saved ? saved === 'dark' : window.matchMedia('(prefers-color-scheme: dark)').matches;
  document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  $('#theme-toggle').addEventListener('click', () => {
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    window.localStorage.setItem('food-atlas-theme', next);
  });
}

initializeTheme();
stateFromUrl();
loadFacets().then(loadFoods);

$('#search-form').addEventListener('submit', (event) => { event.preventDefault(); clearTimeout(searchTimer); offset = 0; updateUrlAndLoad(); });
$('#search').addEventListener('input', () => { clearTimeout(searchTimer); searchTimer = setTimeout(() => { offset = 0; updateUrlAndLoad(); }, 250); });
for (const id of fieldIds) $('#' + id).addEventListener('change', () => { offset = 0; updateUrlAndLoad(); });
$('#clear-filters').addEventListener('click', () => { $('#search').value = ''; for (const id of fieldIds) $('#' + id).value = id === 'sort' ? 'name' : ''; offset = 0; updateUrlAndLoad(); });
$('#previous-page').addEventListener('click', () => { offset = Math.max(0, offset - pageSize); updateUrlAndLoad(); $('.results').scrollIntoView({ block: 'start' }); });
$('#next-page').addEventListener('click', () => { offset += pageSize; updateUrlAndLoad(); $('.results').scrollIntoView({ block: 'start' }); });
$('#filter-toggle').addEventListener('click', () => { const open = $('#filters-panel').classList.toggle('is-open'); $('#filter-toggle').setAttribute('aria-expanded', String(open)); });
$('#close-dialog').addEventListener('click', () => $('#food-dialog').close());
$('#food-dialog').addEventListener('click', (event) => { if (event.target === $('#food-dialog')) $('#food-dialog').close(); });
window.addEventListener('popstate', () => { stateFromUrl(); loadFoods(); });
document.addEventListener('keydown', (event) => { if (event.key === '/' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) { event.preventDefault(); $('#search').focus(); } });
