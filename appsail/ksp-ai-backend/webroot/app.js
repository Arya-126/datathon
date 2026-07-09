/*
 * KSP Crime AI — frontend controller.
 * Vanilla JS; no build step. Talks to the FastAPI backend on same origin.
 */

const KANNADA_DISTRICTS = [
  "Bengaluru Urban","Bengaluru Rural","Mysuru","Mangaluru","Hubballi-Dharwad",
  "Belagavi","Kalaburagi","Ballari","Vijayapura","Shivamogga","Tumakuru",
  "Davanagere","Udupi","Chitradurga","Raichur",
];

// English → Kannada mapping for SQL result columns and common cell values.
// Applied only when state.lang === 'kn'; a missing key falls through to the
// English source (station names, accused names, etc. stay English by design).
const COLUMN_KN = {
  district: 'ಜಿಲ್ಲೆ', crime_no: 'ಎಫ್‌ಐಆರ್ ಸಂಖ್ಯೆ',
  crime_type: 'ಅಪರಾಧ ಪ್ರಕಾರ', station: 'ಠಾಣೆ', date: 'ದಿನಾಂಕ',
  status: 'ಸ್ಥಿತಿ', crimes: 'ಅಪರಾಧಗಳು', cases: 'ಪ್ರಕರಣಗಳು',
  month: 'ತಿಂಗಳು', category: 'ವರ್ಗ', hour: 'ಗಂಟೆ',
  offender: 'ಅಪರಾಧಿ', a_name: 'ವ್ಯಕ್ತಿ ಎ', b_name: 'ವ್ಯಕ್ತಿ ಬಿ',
  shared_cases: 'ಹಂಚಿಕೊಂಡ ಪ್ರಕರಣಗಳು', act: 'ಕಾಯ್ದೆ', section: 'ಕಲಂ',
  description: 'ವಿವರಣೆ', n: 'ಸಂಖ್ಯೆ', cyber_cases: 'ಸೈಬರ್ ಪ್ರಕರಣಗಳು',
  ndps_cases: 'ಎನ್‌ಡಿಪಿಎಸ್ ಪ್ರಕರಣಗಳು', subhead: 'ಉಪವಿಭಾಗ',
  crime_types: 'ಅಪರಾಧ ಪ್ರಕಾರಗಳು', heinous: 'ಘೋರ',
  final_report: 'ಅಂತಿಮ ವರದಿ', a_id: 'ಎ ಐಡಿ', b_id: 'ಬಿ ಐಡಿ',
};
const VALUE_KN = {
  // Districts (all 15 seeded)
  'Bengaluru Urban': 'ಬೆಂಗಳೂರು ನಗರ',
  'Bengaluru Rural': 'ಬೆಂಗಳೂರು ಗ್ರಾಮಾಂತರ',
  'Mysuru': 'ಮೈಸೂರು', 'Mangaluru': 'ಮಂಗಳೂರು',
  'Hubballi-Dharwad': 'ಹುಬ್ಬಳ್ಳಿ-ಧಾರವಾಡ', 'Belagavi': 'ಬೆಳಗಾವಿ',
  'Kalaburagi': 'ಕಲಬುರಗಿ', 'Ballari': 'ಬಳ್ಳಾರಿ',
  'Vijayapura': 'ವಿಜಯಪುರ', 'Shivamogga': 'ಶಿವಮೊಗ್ಗ',
  'Tumakuru': 'ತುಮಕೂರು', 'Davanagere': 'ದಾವಣಗೆರೆ',
  'Udupi': 'ಉಡುಪಿ', 'Chitradurga': 'ಚಿತ್ರದುರ್ಗ', 'Raichur': 'ರಾಯಚೂರು',
  // Crime types (seed's common set)
  'Murder': 'ಕೊಲೆ', 'Attempt to Murder': 'ಕೊಲೆ ಪ್ರಯತ್ನ',
  'Culpable Homicide': 'ದೋಷಪೂರ್ವಕ ಸಾವು',
  'Kidnapping': 'ಅಪಹರಣ', 'Rioting': 'ದಂಗೆ',
  'Dowry Harassment': 'ವರದಕ್ಷಿಣೆ ಕಿರುಕುಳ',
  'Forgery': 'ವಂಚನೆ', 'Ransomware': 'ರ್ಯಾನ್‌ಸಮ್‌ವೇರ್',
  'Hurt / Assault': 'ಗಾಯ / ಹಲ್ಲೆ', 'Theft': 'ಕಳ್ಳತನ',
  'Robbery': 'ದರೋಡೆ', 'Burglary': 'ಮನೆ ಕಳ್ಳತನ',
  'Cheating': 'ಮೋಸ', 'Rape': 'ಅತ್ಯಾಚಾರ',
  'Cyber Crimes': 'ಸೈಬರ್ ಅಪರಾಧಗಳು',
  'Phishing': 'ಫಿಶಿಂಗ್', 'Online Fraud': 'ಆನ್‌ಲೈನ್ ವಂಚನೆ',
  'Identity Theft': 'ವ್ಯಕ್ತಿತ್ವ ಕಳ್ಳತನ',
  // Statuses
  'Under Investigation': 'ತನಿಖೆಯಲ್ಲಿ',
  'Charge Sheeted': 'ದೋಷಾರೋಪ ಸಲ್ಲಿಸಲಾಗಿದೆ',
  'Referred / Zero FIR': 'ಶೂನ್ಯ ಎಫ್‌ಐಆರ್',
  'Closed': 'ಮುಚ್ಚಲಾಗಿದೆ', 'Pending': 'ಬಾಕಿ',
  // Gender
  'Male': 'ಪುರುಷ', 'Female': 'ಮಹಿಳೆ', 'Other': 'ಇತರ',
};

function tCol(name) {
  if (state.lang !== 'kn') return name;
  return COLUMN_KN[String(name).toLowerCase()] || name;
}
function tVal(v) {
  if (state.lang !== 'kn' || v == null) return v;
  return VALUE_KN[String(v)] || v;
}

const state = {
  token: null,
  session: null,
  conversationId: null, // server-side conversation (persistence + PDF unit)
  history: [],          // chat turns for context
  transcript: [],       // for client-side PDF fallback
  lang: 'en',
  view: 'chat',
  services: {},         // /health service map (which Catalyst paths are live)
  hotspotLevel: 'district',
};

// ---------------------------------------------------------------- i18n
// UI chrome translations. Data-driven strings (SQL results, LLM answer
// prefixes) come from the backend already bilingual. This dictionary
// covers the shell: nav, headings, buttons, placeholders, sidebar.
const I18N = {
  en: {
    'nav.chat': '💬 Chat',
    'nav.hotspots': '🔥 Hotspots',
    'nav.trends': '📈 Trends',
    'nav.network': '🕸 Network',
    'nav.insights': '🧠 Insights',
    'nav.predict': '⚠ Early Warnings',
    'nav.audit': '🧾 Audit Log',
    'sidebar.signedInAs': 'Signed in as',
    'sidebar.signOut': 'Sign out ↗',
    'header.exportPdf': 'Export PDF',
    'chat.placeholder': "Ask, e.g. 'Which districts had the most cyber crime last quarter?'",
    'chat.send': 'Send',
    'chat.hint': 'Enter to send · Shift+Enter for newline · Kannada input supported',
    'chat.explainTitle': 'Explainability',
    'chat.explainEmpty': 'The SQL, LLM reasoning, and role-policy notes for the most recent answer will appear here.',
    'hotspots.district': 'Districts',
    'hotspots.station': 'Police stations',
    'hotspots.hint': 'Circle size = FIR volume (last 180 days); red tint = heinous share',
    'trends.hint': 'Monthly crime volume by category, last 24 months.',
    'audit.placeholder': 'Reverse lookup: FIR / CrimeNo (e.g. 1044300062026…)',
    'audit.who': 'Who touched this FIR?',
    'audit.showAll': 'Show all',
    // view titles + subtitles (used by showView)
    'view.chat.title': 'Chat',
    'view.chat.sub': 'Ask in English or Kannada. Voice is supported.',
    'view.hotspots.title': 'Hotspots',
    'view.hotspots.sub': 'Districts by crime volume, last 180 days.',
    'view.trends.title': 'Trends',
    'view.trends.sub': 'Monthly volume by category.',
    'view.network.title': 'Criminal Network',
    'view.network.sub': 'Co-offenders sharing 2+ crimes.',
    'view.insights.title': 'Insights',
    'view.insights.sub': 'Socio-demographic profile & repeat-offender behaviour.',
    'view.predict.title': 'Early Warnings',
    'view.predict.sub': '30-day vs prior 30-day district × category deltas.',
    'view.audit.title': 'Audit Log',
    'view.audit.sub': 'Every query, every user, forever traceable.',
    // explainability panel keys (rendered dynamically)
    'explain.langDetected': 'Language detected',
    'explain.llmExplain': 'LLM explanation',
    'explain.sqlExecuted': 'SQL executed',
    'explain.roleNotes': 'Role policy notes',
    'explain.provider': 'Provider',
  },
  kn: {
    'nav.chat': '💬 ಚಾಟ್',
    'nav.hotspots': '🔥 ಹಾಟ್‌ಸ್ಪಾಟ್‌ಗಳು',
    'nav.trends': '📈 ಟ್ರೆಂಡ್‌ಗಳು',
    'nav.network': '🕸 ನೆಟ್‌ವರ್ಕ್',
    'nav.insights': '🧠 ಒಳನೋಟಗಳು',
    'nav.predict': '⚠ ಮುನ್ಸೂಚನೆಗಳು',
    'nav.audit': '🧾 ಆಡಿಟ್ ಲಾಗ್',
    'sidebar.signedInAs': 'ಸೈನ್ ಇನ್ ಆಗಿರುವವರು',
    'sidebar.signOut': 'ಸೈನ್ ಔಟ್ ↗',
    'header.exportPdf': 'PDF ರಫ್ತು',
    'chat.placeholder': "ಕೇಳಿ, ಉದಾ. 'ಕಳೆದ ತ್ರೈಮಾಸಿಕದಲ್ಲಿ ಯಾವ ಜಿಲ್ಲೆಗಳಲ್ಲಿ ಹೆಚ್ಚು ಸೈಬರ್ ಅಪರಾಧಗಳು?'",
    'chat.send': 'ಕಳುಹಿಸಿ',
    'chat.hint': 'ಕಳುಹಿಸಲು Enter · ಹೊಸ ಸಾಲಿಗೆ Shift+Enter · ಕನ್ನಡ ಇನ್‌ಪುಟ್ ಬೆಂಬಲಿತ',
    'chat.explainTitle': 'ವಿವರಣೀಯತೆ',
    'chat.explainEmpty': 'ಇತ್ತೀಚಿನ ಉತ್ತರದ SQL, LLM ತರ್ಕ ಮತ್ತು ಪಾತ್ರ-ನೀತಿ ಟಿಪ್ಪಣಿಗಳು ಇಲ್ಲಿ ಗೋಚರಿಸುತ್ತವೆ.',
    'hotspots.district': 'ಜಿಲ್ಲೆಗಳು',
    'hotspots.station': 'ಪೊಲೀಸ್ ಠಾಣೆಗಳು',
    'hotspots.hint': 'ವೃತ್ತದ ಗಾತ್ರ = ಎಫ್‌ಐಆರ್ ಪ್ರಮಾಣ (ಕಳೆದ 180 ದಿನಗಳು); ಕೆಂಪು = ಘೋರ ಅಪರಾಧಗಳ ಪಾಲು',
    'trends.hint': 'ಕಳೆದ 24 ತಿಂಗಳ ವರ್ಗವಾರು ಮಾಸಿಕ ಅಪರಾಧ ಪ್ರಮಾಣ.',
    'audit.placeholder': 'ರಿವರ್ಸ್ ಲುಕ್‌ಅಪ್: ಎಫ್‌ಐಆರ್ / CrimeNo (ಉದಾ. 1044300062026…)',
    'audit.who': 'ಈ ಎಫ್‌ಐಆರ್ ಅನ್ನು ಯಾರು ನೋಡಿದ್ದಾರೆ?',
    'audit.showAll': 'ಎಲ್ಲಾ ತೋರಿಸಿ',
    'view.chat.title': 'ಚಾಟ್',
    'view.chat.sub': 'ಇಂಗ್ಲಿಷ್ ಅಥವಾ ಕನ್ನಡದಲ್ಲಿ ಕೇಳಿ. ಧ್ವನಿ ಬೆಂಬಲಿತ.',
    'view.hotspots.title': 'ಹಾಟ್‌ಸ್ಪಾಟ್‌ಗಳು',
    'view.hotspots.sub': 'ಕಳೆದ 180 ದಿನಗಳ ಅಪರಾಧ ಪ್ರಮಾಣದ ಪ್ರಕಾರ ಜಿಲ್ಲೆಗಳು.',
    'view.trends.title': 'ಟ್ರೆಂಡ್‌ಗಳು',
    'view.trends.sub': 'ವರ್ಗದ ಪ್ರಕಾರ ಮಾಸಿಕ ಪ್ರಮಾಣ.',
    'view.network.title': 'ಅಪರಾಧ ಜಾಲ',
    'view.network.sub': '2+ ಅಪರಾಧಗಳನ್ನು ಹಂಚಿಕೊಳ್ಳುವ ಜೊತೆ-ಅಪರಾಧಿಗಳು.',
    'view.insights.title': 'ಒಳನೋಟಗಳು',
    'view.insights.sub': 'ಸಾಮಾಜಿಕ-ಜನಸಂಖ್ಯಾ ಪ್ರೊಫೈಲ್ ಮತ್ತು ಪುನರಾವರ್ತಿತ ಅಪರಾಧಿಗಳ ವರ್ತನೆ.',
    'view.predict.title': 'ಮುನ್ಸೂಚನೆಗಳು',
    'view.predict.sub': '30 ದಿನಗಳ ವಿರುದ್ಧ ಹಿಂದಿನ 30 ದಿನಗಳ ಜಿಲ್ಲೆ × ವರ್ಗ ವ್ಯತ್ಯಾಸಗಳು.',
    'view.audit.title': 'ಆಡಿಟ್ ಲಾಗ್',
    'view.audit.sub': 'ಪ್ರತಿ ಪ್ರಶ್ನೆ, ಪ್ರತಿ ಬಳಕೆದಾರ, ಶಾಶ್ವತವಾಗಿ ಟ್ರೇಸ್ ಮಾಡಬಹುದು.',
    'explain.langDetected': 'ಪತ್ತೆಯಾದ ಭಾಷೆ',
    'explain.llmExplain': 'LLM ವಿವರಣೆ',
    'explain.sqlExecuted': 'ಕಾರ್ಯಗತ SQL',
    'explain.roleNotes': 'ಪಾತ್ರ ನೀತಿ ಟಿಪ್ಪಣಿಗಳು',
    'explain.provider': 'ಒದಗಿಸುವವರು',
  },
};

function t(key) {
  const lang = state.lang === 'kn' ? 'kn' : 'en';
  return (I18N[lang] && I18N[lang][key]) || I18N.en[key] || key;
}

// Sweep every element with data-i18n / data-i18n-placeholder and set its
// text/placeholder from the active language. Called on load and whenever
// #langSel changes.
function applyI18n() {
  document.querySelectorAll('[data-i18n]').forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach((el) => {
    el.setAttribute('placeholder', t(el.dataset.i18nPlaceholder));
  });
  // View title/subtitle depend on the current view — reapply from state.
  if (state.view) {
    const tt = t(`view.${state.view}.title`);
    const ts = t(`view.${state.view}.sub`);
    const titleEl = document.getElementById('viewTitle');
    const subEl = document.getElementById('viewSubtitle');
    if (titleEl) titleEl.textContent = tt;
    if (subEl) subEl.textContent = ts;
  }
  document.documentElement.lang = state.lang === 'kn' ? 'kn' : 'en';
}

// Session survives a reload: token + conversation id live in sessionStorage.
function persistSession() {
  try {
    sessionStorage.setItem('ksp', JSON.stringify({
      token: state.token, session: state.session,
      conversationId: state.conversationId, lang: state.lang,
    }));
  } catch {}
}
function clearSession() {
  try { sessionStorage.removeItem('ksp'); } catch {}
}

// ---------------------------------------------------------------- utilities
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// API base. Empty = same-origin (local dev / AppSail-served). On Catalyst
// Web Client Hosting, config.js sets window.KSP_CONFIG.apiBase to the
// AppSail URL so the hosted client can reach the backend cross-origin
// (backend sends CORS *).
const API_BASE = (window.KSP_CONFIG && window.KSP_CONFIG.apiBase) || '';

async function api(path, opts = {}) {
  const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
  if (state.token) headers['Authorization'] = `Bearer ${state.token}`;
  const res = await fetch(API_BASE + path, { ...opts, headers });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status}: ${body}`);
  }
  return res.json();
}

function el(tag, attrs = {}, children = []) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'class') e.className = v;
    else if (k === 'html') e.innerHTML = v;
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v);
  }
  for (const c of [].concat(children)) {
    if (c == null) continue;
    e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
  }
  return e;
}

// ---------------------------------------------------------------- login
async function loadDistrictsInto(selectEl) {
  const r = await fetch(API_BASE + '/reference/districts').then(x => x.json());
  selectEl.innerHTML = r.districts
    .map(d => `<option value="${d.name}" data-id="${d.id}">${d.name}</option>`)
    .join('');
  return r.districts;
}

async function loadUnitsInto(selectEl, districtId) {
  const r = await fetch(`${API_BASE}/reference/units?district_id=${districtId}`).then(x => x.json());
  selectEl.innerHTML = r.units
    .map(u => `<option value="${u.name}" data-id="${u.id}">${u.name}</option>`)
    .join('');
  return r.units;
}

async function loadEmployeesInto(selectEl, unitId) {
  const r = await fetch(`${API_BASE}/reference/employees?unit_id=${unitId}`).then(x => x.json());
  const ios = r.employees.filter(e => e.designation === 'Investigating Officer'
                                    || e.designation === 'SHO'
                                    || e.designation === 'Cyber Investigator');
  const pool = ios.length ? ios : r.employees;
  selectEl.innerHTML = pool
    .map(e => `<option value="${e.id}">${e.name} — ${e.designation}</option>`)
    .join('');
  return pool;
}

async function initLogin() {
  // Preload district lists for every scope selector.
  await loadDistrictsInto($('#loginDistrict'));
  await loadDistrictsInto($('#unitDistrict'));
  await loadDistrictsInto($('#empDistrict'));

  // Wire cascades: unit picker depends on unitDistrict.
  $('#unitDistrict').addEventListener('change', async e => {
    const id = e.target.selectedOptions[0].dataset.id;
    await loadUnitsInto($('#loginUnit'), id);
  });
  // Employee picker: district → unit → employee cascade.
  $('#empDistrict').addEventListener('change', async e => {
    const id = e.target.selectedOptions[0].dataset.id;
    await loadUnitsInto($('#empUnit'), id);
    $('#empUnit').dispatchEvent(new Event('change'));
  });
  $('#empUnit').addEventListener('change', async e => {
    const id = e.target.selectedOptions[0].dataset.id;
    await loadEmployeesInto($('#loginEmployee'), id);
  });

  // Initial cascade population.
  $('#unitDistrict').dispatchEvent(new Event('change'));
  $('#empDistrict').dispatchEvent(new Event('change'));

  // Role switch → which scope fields are shown.
  $('#loginRole').addEventListener('change', e => {
    const role = e.target.value;
    $('#scopeDistrict').classList.toggle('hidden', role !== 'dysp');
    $('#scopeUnit').classList.toggle('hidden', role !== 'sho');
    $('#scopeEmp').classList.toggle('hidden', role !== 'io');
  });

  $('#loginBtn').addEventListener('click', async () => {
    const role = $('#loginRole').value;
    const body = {
      user_id: $('#loginUser').value.trim() || 'KSP-DEMO',
      role,
    };
    if (role === 'dysp') body.district = $('#loginDistrict').value;
    if (role === 'sho')  body.unit = $('#loginUnit').value;
    if (role === 'io')   body.employee_id = Number($('#loginEmployee').value);
    try {
      const r = await api('/login', { method: 'POST', body: JSON.stringify(body) });
      state.token = r.token;
      state.session = { user_id: r.user_id, role: r.role, ...body };
      state.conversationId = null;
      persistSession();
      enterApp();
    } catch (e) {
      alert(`Login failed: ${e.message}`);
    }
  });
}

// Post-login (or post-restore) UI setup.
function enterApp() {
  const s = state.session;
  $('#login').classList.add('hidden');
  const scopeLabel = s.district ? ` · ${s.district}`
                   : s.unit ? ` · ${s.unit}`
                   : s.employee_name ? ` · ${s.employee_name}`
                   : '';
  $('#sessLabel').textContent = `${s.user_id} · ${s.role}${scopeLabel}`;
  loadHealth();
  // Analyst can't see Network → hide the nav button.
  const netBtn = document.querySelector('[data-view="network"]');
  if (netBtn) netBtn.style.display = s.role === 'analyst' ? 'none' : '';
  const auditBtn = document.querySelector('[data-view="audit"]');
  if (auditBtn) auditBtn.style.display = s.role === 'admin' ? '' : 'none';
  showView('chat');
  applyI18n();
}

// Reload survival: validate the stored token, then replay the stored
// conversation into the chat log so context is not lost.
async function tryRestoreSession() {
  let saved;
  try { saved = JSON.parse(sessionStorage.getItem('ksp') || 'null'); } catch {}
  if (!saved?.token) return false;
  state.token = saved.token;
  state.lang = saved.lang || 'en';
  $('#langSel').value = state.lang;
  try {
    const me = await api('/me');
    state.session = { ...saved.session, ...me };
  } catch {
    state.token = null; clearSession(); return false;
  }
  state.conversationId = saved.conversationId || null;
  enterApp();
  if (state.conversationId) {
    try {
      const r = await api(`/conversations/${state.conversationId}`);
      for (const turn of r.turns) {
        if (turn.turn_role === 'user') {
          addMessage('user', { text: turn.content });
          state.history.push({ role: 'user', content: turn.content });
        } else {
          addMessage('bot', { prefix: turn.content, sql: turn.sql });
          state.history.push({
            role: 'assistant',
            content: turn.sql ? `${turn.content}\n[SQL] ${turn.sql}` : (turn.content || ''),
          });
        }
        state.transcript.push({
          role: turn.turn_role === 'user' ? 'user' : 'assistant',
          text: turn.content, sql: turn.sql,
        });
      }
    } catch { state.conversationId = null; }
  }
  return true;
}

async function loadHealth() {
  try {
    const h = await api('/health');
    state.services = h.services || {};
    // Choose the primary LLM label based on service_status.
    let label = 'LLM: fallback';
    let cls = 'bg-amber-900/40 text-amber-300';
    if (h.services?.quickml) { label = 'LLM: QuickML'; cls = 'bg-emerald-900/40 text-emerald-300'; }
    else if (h.services?.gemini) { label = 'LLM: Gemini'; cls = 'bg-emerald-900/40 text-emerald-300'; }
    $('#llmBadge').textContent = label;
    $('#llmBadge').className = 'px-2 py-1 rounded border border-ink-600 text-[11px] tracking-wider ' + cls;
  } catch {}
}

// ---------------------------------------------------------------- nav
function showView(v) {
  state.view = v;
  $$('.nav-btn').forEach(b => b.classList.toggle('active', b.dataset.view === v));
  $$('.view').forEach(s => s.classList.add('hidden'));
  const target = $(`#view-${v}`);
  target.classList.remove('hidden');
  target.classList.add('flex');
  $('#viewTitle').textContent = t(`view.${v}.title`);
  $('#viewSubtitle').textContent = t(`view.${v}.sub`);
  if (v === 'hotspots') loadHotspots();
  if (v === 'trends') loadTrends();
  if (v === 'network') loadNetwork();
  if (v === 'insights') loadInsights();
  if (v === 'predict') loadPredict();
  if (v === 'audit') loadAudit();
}

// ---------------------------------------------------------------- chat
function addMessage(role, opts) {
  const cls = role === 'user' ? 'msg user' : 'msg bot';
  const wrap = el('div', { class: 'flex' });
  const bubble = el('div', { class: cls });

  if (role === 'bot' && opts.prefix) {
    bubble.appendChild(el('div', { class: 'prefix' }, opts.prefix));
  }
  if (opts.text) {
    bubble.appendChild(el('div', {}, opts.text));
  }
  if (opts.rows && opts.rows.length && opts.chart !== 'network') {
    bubble.appendChild(renderTable(opts.columns, opts.rows));
    if (opts.chart === 'bar' || opts.chart === 'line') {
      bubble.appendChild(renderInlineChart(opts.columns, opts.rows, opts.chart));
    }
  } else if (opts.chart === 'network' && opts.rows?.length) {
    bubble.appendChild(el('button', {
      class: 'mt-3 px-3 py-1.5 rounded bg-ink-700 border border-ink-600 hover:bg-ink-600 text-sm',
      onclick: () => showView('network'),
    }, '→ Open in Network view'));
  }
  if (role === 'bot' && opts.sql) {
    bubble.appendChild(el('pre', { class: 'sql' }, opts.sql));
  }
  wrap.appendChild(bubble);
  $('#chatLog').appendChild(wrap);
  $('#chatLog').scrollTop = $('#chatLog').scrollHeight;
}

function renderTable(columns, rows) {
  const table = el('table', { class: 'data' });
  const thead = el('thead', {}, el('tr', {},
    columns.map(c => el('th', {}, tCol(c)))));
  const tbody = el('tbody', {}, rows.slice(0, 25).map(r =>
    el('tr', {}, columns.map(c => el('td', {}, String(tVal(r[c]) ?? ''))))
  ));
  table.append(thead, tbody);
  if (rows.length > 25) {
    const foot = el('div', { class: 'text-[11px] text-slate-500 mt-1' },
      `Showing 25 of ${rows.length} rows`);
    const wrap = el('div', {}, [table, foot]);
    return wrap;
  }
  return table;
}

function renderInlineChart(columns, rows, type) {
  if (columns.length < 2 || rows.length > 40) return el('div');
  const label = columns[0], value = columns[columns.length - 1];
  const canvas = el('canvas', { height: '100' });
  const wrap = el('div', { class: 'mt-3 bg-ink-900 p-3 rounded' }, canvas);
  setTimeout(() => {
    new Chart(canvas, {
      type,
      data: {
        labels: rows.map(r => r[label]),
        datasets: [{
          label: value,
          data: rows.map(r => r[value]),
          backgroundColor: '#5b8def',
          borderColor: '#93c5fd',
        }],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: '#94a3b8' }, grid: { color: '#17233e' } },
          y: { ticks: { color: '#94a3b8' }, grid: { color: '#17233e' } },
        },
      },
    });
  }, 0);
  return wrap;
}

function renderExplain(r, notes) {
  const div = $('#explain');
  div.innerHTML = '';
  const kv = (k, v) => el('div', {}, [
    el('div', { class: 'text-[11px] uppercase tracking-wider text-slate-500' }, k),
    el('div', { class: 'text-slate-200 mt-0.5' }, v || '—'),
  ]);
  div.appendChild(kv(t('explain.langDetected'), r.language));
  const primaryExplain = state.lang === 'kn' && r.explanation_kn
    ? r.explanation_kn : r.explanation_en;
  div.appendChild(kv(t('explain.llmExplain'), primaryExplain));
  if (r.explanation_kn && state.lang !== 'kn') {
    div.appendChild(kv('ವಿವರಣೆ', r.explanation_kn));
  }
  if (r.sql) {
    div.appendChild(el('div', {}, [
      el('div', { class: 'text-[11px] uppercase tracking-wider text-slate-500 mb-1' }, t('explain.sqlExecuted')),
      el('pre', { class: 'sql' }, r.sql),
    ]));
  }
  if (notes?.length) {
    div.appendChild(kv(t('explain.roleNotes'), notes.join('; ')));
  }
  const providerLabel = { quickml: 'Catalyst QuickML', gemini: 'Gemini Flash',
                          fallback: 'keyword fallback (offline)' };
  div.appendChild(kv(t('explain.provider'), providerLabel[r.provider] || r.provider));
}

async function sendChat() {
  const q = $('#chatInput').value.trim();
  if (!q) return;
  $('#chatInput').value = '';
  addMessage('user', { text: q });
  state.history.push({ role: 'user', content: q });
  state.transcript.push({ role: 'user', text: q });

  const thinking = el('div', { class: 'flex' },
    el('div', { class: 'msg bot text-slate-400 italic' }, '…'));
  $('#chatLog').appendChild(thinking);

  try {
    const r = await api('/chat', {
      method: 'POST',
      body: JSON.stringify({
        query: q,
        history: state.history,
        conversation_id: state.conversationId,
      }),
    });
    thinking.remove();
    if (r.conversation_id) {
      state.conversationId = r.conversation_id;
      persistSession();
    }
    const prefix = state.lang === 'kn' && r.answer_prefix_kn
      ? r.answer_prefix_kn : r.answer_prefix_en;
    addMessage('bot', {
      prefix,
      rows: r.rows,
      columns: r.columns,
      sql: r.sql,
      chart: r.chart_hint,
    });
    // Include the executed SQL in the assistant turn so follow-ups
    // ("only Mysuru", "just last month") refine the previous query.
    state.history.push({
      role: 'assistant',
      content: r.sql ? `${prefix || ''}\n[SQL] ${r.sql}` : (prefix || ''),
    });
    state.transcript.push({
      role: 'assistant', text: prefix, sql: r.sql,
      rows: r.rows, columns: r.columns,
    });
    renderExplain(r, r.notes);
    if (r.chart_hint === 'network' && r.rows?.length) {
      // Prime the network view with the returned pairs.
      state.pendingNetwork = r.rows;
    }
    // Optional voice output
    speak(prefix, r.language);
  } catch (e) {
    thinking.remove();
    addMessage('bot', { text: `Error: ${e.message}` });
  }
}

// ---------------------------------------------------------------- voice
// Two paths, picked at click time:
//   - server STT via /voice/asr when the org has a Zia speech endpoint
//     configured (state.services.zia_stt) — audio stays in the audit boundary
//   - on-device Web Speech (kn-IN / en-IN) otherwise — works everywhere
let recognizer = null;
let mediaRec = null;

async function recordAndTranscribe() {
  const lang = state.lang === 'kn' ? 'kn-IN' : 'en-IN';
  if (mediaRec) { mediaRec.stop(); return; }  // second click = stop
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const chunks = [];
  mediaRec = new MediaRecorder(stream);
  mediaRec.ondataavailable = (e) => chunks.push(e.data);
  mediaRec.onstop = async () => {
    stream.getTracks().forEach(t => t.stop());
    $('#voiceBtn').classList.remove('rec-btn');
    mediaRec = null;
    const form = new FormData();
    form.append('audio', new Blob(chunks, { type: 'audio/webm' }), 'q.webm');
    try {
      const res = await fetch(`${API_BASE}/voice/asr?lang=${lang}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${state.token}` },
        body: form,
      });
      const j = await res.json();
      if (j.available && j.text) {
        $('#chatInput').value = j.text;
        sendChat();
        return;
      }
    } catch {}
    // Server path degraded mid-flight → fall back to Web Speech next click.
    state.services.zia_stt = false;
  };
  mediaRec.start();
  $('#voiceBtn').classList.add('rec-btn');
  setTimeout(() => { if (mediaRec?.state === 'recording') mediaRec.stop(); }, 8000);
}

function setupVoice() {
  const Ctor = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (Ctor) {
    recognizer = new Ctor();
    recognizer.continuous = false;
    recognizer.interimResults = false;
    recognizer.onend = () => $('#voiceBtn').classList.remove('rec-btn');
    recognizer.onerror = () => $('#voiceBtn').classList.remove('rec-btn');
    recognizer.onresult = (e) => {
      const text = e.results[0][0].transcript;
      $('#chatInput').value = text;
      sendChat();
    };
  }

  $('#voiceBtn').addEventListener('click', () => {
    if (state.services?.zia_stt) {
      recordAndTranscribe().catch(() => {});
      return;
    }
    if (!recognizer) return;
    recognizer.lang = state.lang === 'kn' ? 'kn-IN' : 'en-IN';
    try { recognizer.start(); $('#voiceBtn').classList.add('rec-btn'); }
    catch {}
  });

  if (!Ctor && !navigator.mediaDevices) {
    $('#voiceBtn').disabled = true;
    $('#voiceBtn').title = 'Voice not supported in this browser';
  }
}

function speak(text, lang) {
  if (!text || !window.speechSynthesis) return;
  const u = new SpeechSynthesisUtterance(text.slice(0, 220));
  u.lang = lang === 'kn' ? 'kn-IN' : 'en-IN';
  u.rate = 1.0;
  speechSynthesis.cancel();
  speechSynthesis.speak(u);
}

// ---------------------------------------------------------------- hotspots
let hotspotMap = null;
let hotspotLayer = null;

function ensureHotspotMap() {
  if (hotspotMap) return hotspotMap;
  hotspotMap = L.map('hotspotMap', { zoomControl: true })
    .setView([14.5, 76.2], 7);  // Karnataka
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; OpenStreetMap &copy; CARTO',
    maxZoom: 18,
  }).addTo(hotspotMap);
  return hotspotMap;
}

function setHotspotLevel(level) {
  state.hotspotLevel = level;
  $('#hsLevelDistrict').className = level === 'district'
    ? 'px-3 py-1.5 rounded bg-accent text-white text-sm'
    : 'px-3 py-1.5 rounded bg-ink-700 border border-ink-600 text-sm hover:bg-ink-600';
  $('#hsLevelStation').className = level === 'station'
    ? 'px-3 py-1.5 rounded bg-accent text-white text-sm'
    : 'px-3 py-1.5 rounded bg-ink-700 border border-ink-600 text-sm hover:bg-ink-600';
  loadHotspots();
}

async function loadHotspots() {
  const level = state.hotspotLevel;
  const r = await api(`/hotspots?level=${level}`);
  const spots = r.hotspots;
  const body = $('#hotspotBody');
  body.innerHTML = '';

  // --- Map: circle size ∝ crimes, red tint ∝ heinous share ---
  const map = ensureHotspotMap();
  setTimeout(() => map.invalidateSize(), 50);
  if (hotspotLayer) hotspotLayer.remove();
  hotspotLayer = L.layerGroup().addTo(map);
  const maxN = Math.max(...spots.map(h => h.crimes), 1);
  const pts = [];
  for (const h of spots) {
    if (h.lat == null || h.lng == null) continue;
    pts.push([h.lat, h.lng]);
    const share = h.crimes ? (h.heinous ?? 0) / h.crimes : 0;
    const color = share > 0.35 ? '#f87171' : share > 0.2 ? '#fbbf24' : '#5b8def';
    const radius = 6 + 22 * Math.sqrt(h.crimes / maxN);
    const label = level === 'district'
      ? `<b>${h.district}</b><br>${h.crimes} FIRs · ${h.heinous ?? 0} heinous · ${h.active_stations ?? 0} stations`
      : `<b>${h.station}</b><br>${h.district}<br>${h.crimes} FIRs · ${h.heinous ?? 0} heinous`;
    L.circleMarker([h.lat, h.lng], {
      radius, color, weight: 1.5, fillColor: color, fillOpacity: 0.35,
    }).bindPopup(label).addTo(hotspotLayer);
  }
  if (pts.length > 1) map.fitBounds(pts, { padding: [30, 30] });
  else if (pts.length === 1) map.setView(pts[0], 11);

  // --- Ranked cards below the map ---
  const grid = el('div', { class: 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4' });
  for (const h of spots.slice(0, 15)) {
    const pct = Math.round((h.crimes / maxN) * 100);
    grid.appendChild(el('div', { class: 'hotspot-card' }, [
      el('div', { class: 'flex items-baseline justify-between' }, [
        el('div', { class: 'text-lg font-semibold' },
          level === 'district' ? h.district : h.station),
        el('div', { class: 'text-xs text-slate-400' }, `${h.crimes} crimes`),
      ]),
      el('div', { class: 'mt-2 h-2 rounded bg-ink-900 overflow-hidden' },
        el('div', { class: 'h-full bg-khaki-500', style: `width:${pct}%` })),
      el('div', { class: 'mt-2 flex justify-between text-xs text-slate-400' }, [
        el('span', {}, level === 'district'
          ? `${h.heinous ?? 0} heinous · ${h.active_stations ?? 0} stations`
          : `${h.heinous ?? 0} heinous · ${h.district}`),
        el('span', {},
          (h.lat != null && h.lng != null)
            ? `${h.lat.toFixed(2)}, ${h.lng.toFixed(2)}`
            : ''),
      ]),
    ]));
  }
  body.appendChild(grid);
}

// ---------------------------------------------------------------- trends
let trendChart = null;
async function loadTrends() {
  const r = await api('/trends');
  if (trendChart) trendChart.destroy();
  const palette = ['#5b8def', '#c9a35b', '#f87171', '#34d399', '#a78bfa', '#fbbf24'];
  trendChart = new Chart($('#trendChart'), {
    type: 'line',
    data: {
      labels: r.labels,
      datasets: r.series.map((s, i) => ({
        label: s.label,
        data: s.data,
        borderColor: palette[i % palette.length],
        backgroundColor: palette[i % palette.length] + '30',
        borderWidth: 2,
        tension: 0.3,
        fill: false,
      })),
    },
    options: {
      responsive: true,
      plugins: {
        legend: { labels: { color: '#cbd5e1' } },
        tooltip: { intersect: false, mode: 'index' },
      },
      scales: {
        x: { ticks: { color: '#94a3b8' }, grid: { color: '#17233e' } },
        y: { ticks: { color: '#94a3b8' }, grid: { color: '#17233e' } },
      },
    },
  });
}

// ---------------------------------------------------------------- network
let networkInstance = null;
async function loadNetwork() {
  try {
    const r = await api('/network');
    const container = $('#networkBody');
    container.innerHTML = '';
    if (!r.nodes.length) {
      container.appendChild(el('div', { class: 'p-6 text-slate-400' },
        'No co-offender clusters at min_shared=2.'));
      return;
    }
    const nodes = new vis.DataSet(r.nodes.map(n => ({
      id: n.id, label: n.name,
      value: n.crimes,
      color: { background: '#1e2c4d', border: '#5b8def', highlight: { background: '#5b8def' } },
      font: { color: '#e2e8f0', size: 13 },
    })));
    const edges = new vis.DataSet(r.edges.map(e => ({
      from: e.source, to: e.target,
      value: e.weight, label: `${e.weight}`,
      color: { color: '#c9a35b', opacity: 0.6 },
      font: { color: '#94a3b8', size: 10, strokeWidth: 0 },
    })));
    networkInstance = new vis.Network(container, { nodes, edges }, {
      physics: { stabilization: true, barnesHut: { gravitationalConstant: -3000 } },
      nodes: { shape: 'dot', scaling: { min: 8, max: 34 } },
      edges: { smooth: { type: 'continuous' }, scaling: { min: 1, max: 6 } },
    });
  } catch (e) {
    $('#networkBody').innerHTML = `<div class="p-6 text-amber-400">${e.message}</div>`;
  }
}

// ---------------------------------------------------------------- predict
// ---------------------------------------------------------------- insights
let insightsCharts = [];
async function loadInsights() {
  const body = $('#insightsBody');
  body.innerHTML = '';
  insightsCharts.forEach(c => { try { c.destroy(); } catch {} });
  insightsCharts = [];

  // --- Socio-demographic panels ---
  body.appendChild(el('h3', {
    class: 'text-xs uppercase tracking-wider text-slate-400 mb-3',
  }, 'Socio-demographic insights'));
  const grid = el('div', {
    class: 'grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 mb-8',
  });
  body.appendChild(grid);

  let ov;
  try {
    ov = await api('/demographics/overview');
  } catch (e) {
    grid.appendChild(el('div', { class: 'text-amber-400' }, e.message));
    ov = { panels: [] };
  }
  const palette = ['#5b8def', '#c9a35b', '#f87171', '#34d399', '#a78bfa', '#fbbf24'];
  for (const panel of ov.panels) {
    const canvas = el('canvas', { height: '160' });
    grid.appendChild(el('div', { class: 'hotspot-card' }, [
      el('div', { class: 'text-sm font-semibold mb-2' }, panel.label),
      canvas,
    ]));
    const chart = new Chart(canvas, {
      type: 'bar',
      data: {
        labels: panel.labels,
        datasets: [{ data: panel.counts, backgroundColor: palette }],
      },
      options: {
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: '#94a3b8', font: { size: 10 } }, grid: { display: false } },
          y: { ticks: { color: '#94a3b8' }, grid: { color: '#17233e' } },
        },
      },
    });
    insightsCharts.push(chart);
  }

  // --- Behavioural profiling: repeat offenders + recidivism ---
  body.appendChild(el('h3', {
    class: 'text-xs uppercase tracking-wider text-slate-400 mb-3',
  }, 'Behavioural profiling — repeat offenders'));

  let prof;
  try {
    prof = await api('/profiling/repeat-offenders?min_cases=2&limit=15');
  } catch (e) {
    body.appendChild(el('div', { class: 'text-amber-400' }, e.message));
    return;
  }
  const rec = prof.recidivism;
  body.appendChild(el('div', { class: 'hotspot-card mb-4 flex items-center gap-6' }, [
    el('div', {}, [
      el('div', { class: 'text-3xl font-bold text-khaki-500' }, `${rec.recidivism_pct}%`),
      el('div', { class: 'text-xs text-slate-400' }, 'recidivism rate'),
    ]),
    el('div', { class: 'text-sm text-slate-300' },
      `${rec.repeat_offenders} of ${rec.total_offenders} identified offenders appear in more than one FIR (cross-case identity via PersonAlias).`),
  ]));

  const cols = ['name', 'cases', 'arrests', 'heinous', 'crime_heads'];
  body.appendChild(renderTable(cols, prof.offenders));
}

async function loadPredict() {
  const r = await api('/predict');
  const body = $('#predictBody');
  body.innerHTML = '';
  const header = el('div', { class: 'mb-4' }, [
    el('div', { class: 'text-sm text-slate-400' },
      `Comparing ${r.window_current[0]} → ${r.window_current[1]} against prior 30 days`),
  ]);
  body.appendChild(header);
  if (!r.warnings.length) {
    body.appendChild(el('div', { class: 'text-emerald-400 mb-6' },
      'No unusual spikes detected.'));
  } else {
    const list = el('div', { class: 'space-y-3 mb-8' });
    for (const w of r.warnings) {
      list.appendChild(el('div', { class: 'hotspot-card flex items-start justify-between gap-3' }, [
        el('div', {}, [
          el('div', { class: 'font-semibold' }, `${w.district} · ${w.category}`),
          el('div', { class: 'text-sm text-slate-300 mt-1' }, w.message),
        ]),
        el('div', { class: `badge ${w.severity}` }, w.severity),
      ]));
    }
    body.appendChild(list);
  }

  // --- Forward-looking forecast (next 30 days) ---
  const fc = r.forecast;
  if (fc?.forecast?.length) {
    body.appendChild(el('h3', {
      class: 'text-xs uppercase tracking-wider text-slate-400 mb-1',
    }, 'Forecast — next 30 days'));
    body.appendChild(el('p', { class: 'text-[11px] text-slate-500 mb-3' },
      fc.model));
    const arrows = { rising: '▲', falling: '▼', flat: '→' };
    const colors = { rising: 'text-red-400', falling: 'text-emerald-400',
                     flat: 'text-slate-400' };
    const grid = el('div', {
      class: 'grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3',
    });
    for (const f of fc.forecast) {
      grid.appendChild(el('div', { class: 'hotspot-card flex items-center justify-between gap-3' }, [
        el('div', {}, [
          el('div', { class: 'font-semibold text-sm' }, `${f.district}`),
          el('div', { class: 'text-xs text-slate-400' }, f.category),
        ]),
        el('div', { class: 'text-right' }, [
          el('div', { class: `font-bold ${colors[f.direction]}` },
            `${arrows[f.direction]} ${f.predicted_next_30d}`),
          el('div', { class: 'text-[10px] text-slate-500' },
            `last 30d: ${f.last_30d}`),
        ]),
      ]));
    }
    body.appendChild(grid);
  }
}

// ---------------------------------------------------------------- audit
async function loadAudit(firFilter) {
  try {
    const path = firFilter
      ? `/audit/fir/${encodeURIComponent(firFilter)}` : '/audit';
    const r = await api(path);
    const body = $('#auditBody');
    body.innerHTML = '';
    if (firFilter) {
      body.appendChild(el('div', { class: 'text-xs text-slate-400 mb-3' },
        `${r.entries.length} audit entr${r.entries.length === 1 ? 'y' : 'ies'} touching "${firFilter}"`));
    }
    const columns = ['timestamp', 'user_id', 'role', 'action', 'query', 'result_summary'];
    body.appendChild(renderTable(columns, r.entries));
  } catch (e) {
    $('#auditBody').innerHTML = `<div class="text-amber-400">${e.message}</div>`;
  }
}

// ---------------------------------------------------------------- PDF export
// Server-side first (Catalyst SmartBrowz — proper fonts incl. Kannada, and a
// copy lands in Stratus for the audit trail); jsPDF fallback offline.
async function exportPDF() {
  if (state.conversationId) {
    try {
      const res = await fetch(API_BASE + '/export/pdf', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${state.token}`,
        },
        body: JSON.stringify({ conversation_id: state.conversationId }),
      });
      if (res.ok && res.headers.get('content-type')?.includes('pdf')) {
        const blob = await res.blob();
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = `ksp-conversation-${state.conversationId}.pdf`;
        a.click();
        URL.revokeObjectURL(a.href);
        return;
      }
    } catch {}
    // fall through to client-side rendering
  }
  exportPDFClient();
}

function exportPDFClient() {
  const { jsPDF } = window.jspdf;
  const pdf = new jsPDF({ unit: 'pt', format: 'a4' });
  const now = new Date().toISOString().slice(0, 19).replace('T', ' ');
  pdf.setFontSize(16); pdf.text('KSP Crime AI — Conversation Transcript', 40, 50);
  pdf.setFontSize(10); pdf.setTextColor(120);
  pdf.text(`Session: ${state.session?.user_id || '—'} · Role: ${state.session?.role || '—'}`, 40, 68);
  pdf.text(`Exported: ${now}`, 40, 82);
  pdf.setTextColor(0);
  let y = 110;
  const line = (txt, indent = 0) => {
    const wrapped = pdf.splitTextToSize(txt, 500 - indent);
    for (const ln of wrapped) {
      if (y > 780) { pdf.addPage(); y = 50; }
      pdf.text(ln, 40 + indent, y); y += 14;
    }
  };
  if (!state.transcript.length) {
    line('(No conversation yet.)');
  }
  for (const t of state.transcript) {
    pdf.setFont(undefined, 'bold');
    line(t.role === 'user' ? 'Investigator' : 'AI');
    pdf.setFont(undefined, 'normal');
    if (t.text) line(t.text, 12);
    if (t.sql) {
      pdf.setFont('Courier', 'normal'); pdf.setFontSize(9);
      line(t.sql, 12);
      pdf.setFont(undefined, 'normal'); pdf.setFontSize(10);
    }
    if (t.rows?.length) {
      line(`(${t.rows.length} rows)`, 12);
    }
    y += 6;
  }
  pdf.save(`ksp-crime-ai-${now.replace(/[: ]/g, '-')}.pdf`);
}

// ---------------------------------------------------------------- boot
document.addEventListener('DOMContentLoaded', async () => {
  setupVoice();
  $$('.nav-btn').forEach(b => b.addEventListener('click',
    () => showView(b.dataset.view)));
  $('#sendBtn').addEventListener('click', sendChat);
  $('#chatInput').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); }
  });
  $('#pdfBtn').addEventListener('click', exportPDF);
  $('#langSel').addEventListener('change', (e) => {
    state.lang = e.target.value; persistSession(); applyI18n();
  });
  $('#logoutBtn').addEventListener('click', () => {
    clearSession(); location.reload();
  });
  $('#hsLevelDistrict').addEventListener('click', () => setHotspotLevel('district'));
  $('#hsLevelStation').addEventListener('click', () => setHotspotLevel('station'));
  $('#auditFirBtn').addEventListener('click',
    () => loadAudit($('#auditFir').value.trim()));
  $('#auditAllBtn').addEventListener('click', () => {
    $('#auditFir').value = ''; loadAudit();
  });
  // Restore saved language (if any) BEFORE any UI text is rendered.
  try {
    const saved = JSON.parse(sessionStorage.getItem('ksp') || 'null');
    if (saved?.lang) { state.lang = saved.lang; $('#langSel').value = saved.lang; }
  } catch {}
  applyI18n();
  await initLogin();
  await tryRestoreSession();  // reload survival — skips login if token valid
});
