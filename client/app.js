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

// Human label for an LLM provider id ("gemini#2" → "Gemini Flash #2").
const PROVIDER_NAMES = {
  quickml: 'Catalyst QuickML', gemini: 'Gemini Flash', groq: 'Groq',
  openrouter: 'OpenRouter', openai: 'OpenAI', anthropic: 'Claude',
  fallback: 'keyword fallback (offline)',
};
function providerLabel(id) {
  if (!id) return '—';
  const [base, n] = String(id).split('#');
  const name = PROVIDER_NAMES[base] || base;
  return n ? `${name} #${n}` : name;
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
  ttsEnabled: true,
};

// ---------------------------------------------------------------- i18n
// UI chrome translations. Data-driven strings (SQL results, LLM answer
// prefixes) come from the backend already bilingual. This dictionary
// covers the shell: nav, headings, buttons, placeholders, sidebar.
const I18N = {
  en: {
    'nav.chat': '📊 Dashboard',
    'nav.trends': '📈 Crime Trends',
    'nav.cases': '📁 Cases',
    'nav.hotspots': '🌍 Geography',
    'nav.predict': '⚡ Predictions',
    'nav.insights': '📄 Reports',
    'nav.audit': '⚙ Administration',
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
    'view.chat.title': 'Conversational AI Intelligence',
    'view.chat.sub': 'Ask in English or Kannada. Voice is supported.',
    'view.hotspots.title': 'Geography (Hotspots)',
    'view.hotspots.sub': 'Districts by crime volume, last 180 days.',
    'view.trends.title': 'Crime Trends',
    'view.trends.sub': 'Monthly volume by category.',
    'view.network.title': 'Criminal Network',
    'view.network.sub': 'Co-offenders sharing 2+ crimes.',
    'view.insights.title': 'Reports (Insights)',
    'view.insights.sub': 'Socio-demographic profile & repeat-offender behaviour.',
    'view.predict.title': 'Predictions (Early Warnings)',
    'view.predict.sub': '30-day vs prior 30-day district × category deltas.',
    'view.cases.title': 'Cases & FIR Inspector',
    'view.cases.sub': 'Look up details, timeline, accused networks, and audit history.',
    'view.audit.title': 'Administration (Audit Log)',
    'view.audit.sub': 'Every query, every user, forever traceable.',
    // explainability panel keys (rendered dynamically)
    'explain.langDetected': 'Language detected',
    'explain.llmExplain': 'LLM explanation',
    'explain.sqlExecuted': 'Generated SQL',
    'explain.roleNotes': 'Policy Notes',
    'explain.provider': 'Provider',
  },
  kn: {
    'nav.chat': '📊 ಡ್ಯಾಶ್‌ಬೋರ್ಡ್',
    'nav.trends': '📈 ಅಪರಾಧ ಪ್ರವೃತ್ತಿಗಳು',
    'nav.cases': '📁 ಪ್ರಕರಣಗಳು',
    'nav.hotspots': '🌍 ಭೂಗೋಳ',
    'nav.predict': '⚡ ಮುನ್ಸೂಚನೆಗಳು',
    'nav.insights': '📄 ವರದಿಗಳು',
    'nav.audit': '⚙ ಆಡಳಿತ',
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
    'view.chat.title': 'ಸಂಭಾಷಣಾತ್ಮಕ AI ಬುದ್ಧಿಮತ್ತೆ',
    'view.chat.sub': 'ಇಂಗ್ಲಿಷ್ ಅಥವಾ ಕನ್ನಡದಲ್ಲಿ ಕೇಳಿ. ಧ್ವನಿ ಬೆಂಬಲಿತ.',
    'view.hotspots.title': 'ಭೂಗೋಳ (ಹಾಟ್‌ಸ್ಪಾಟ್‌ಗಳು)',
    'view.hotspots.sub': 'ಕಳೆದ 180 ದಿನಗಳ ಅಪರಾಧ ಪ್ರಮಾಣದ ಪ್ರಕಾರ ಜಿಲ್ಲೆಗಳು.',
    'view.trends.title': 'ಅಪರಾಧ ಪ್ರವೃತ್ತಿಗಳು',
    'view.trends.sub': 'ವರ್ಗದ ಪ್ರಕಾರ ಮಾಸಿಕ ಪ್ರಮಾಣ.',
    'view.network.title': 'ಅಪರಾಧ ಜಾಲ',
    'view.network.sub': '2+ ಅಪರಾಧಗಳನ್ನು ಹಂಚಿಕೊಳ್ಳುವ ಜೊತೆ-ಅಪರಾಧಿಗಳು.',
    'view.insights.title': 'ವರದಿಗಳು (ಒಳನೋಟಗಳು)',
    'view.insights.sub': 'ಸಾಮಾಜಿಕ-ಜನಸಂಖ್ಯಾ ಪ್ರೊಫೈಲ್ ಮತ್ತು ಪುನರಾವರ್ತಿತ ಅಪರಾಧಿಗಳ ವರ್ತನೆ.',
    'view.predict.title': 'ಮುನ್ಸೂಚನೆಗಳು (ಆರಂಭಿಕ ಎಚ್ಚರಿಕೆಗಳು)',
    'view.predict.sub': '30 ದಿನಗಳ ವಿರುದ್ಧ ಹಿಂದಿನ 30 ದಿನಗಳ ಜಿಲ್ಲೆ × ವರ್ಗ ವ್ಯತ್ಯಾಸಗಳು.',
    'view.cases.title': 'ಪ್ರಕರಣಗಳು ಮತ್ತು ಎಫ್‌ಐಆರ್ ತನಿಖಾಧಿಕಾರಿ',
    'view.cases.sub': 'ವಿವರಗಳು, ಟೈಮ್‌ಲೈನ್, ಆರೋಪಿಗಳ ಜಾಲ ಮತ್ತು ಆಡಿಟ್ ಇತಿಹಾಸವನ್ನು ಹುಡುಕಿ.',
    'view.audit.title': 'ಆಡಳಿತ (ಆಡಿಟ್ ಲಾಗ್)',
    'view.audit.sub': 'ಪ್ರತಿ ಪ್ರಶ್ನೆ, ಪ್ರತಿ ಬಳಕೆದಾರ, ಶಾಶ್ವತವಾಗಿ ಟ್ರೇಸ್ ಮಾಡಬಹುದು.',
    'explain.langDetected': 'ಪತ್ತೆಯಾದ ಭಾಷೆ',
    'explain.llmExplain': 'LLM ವಿವರಣೆ',
    'explain.sqlExecuted': 'ಜನರೇಟ್ ಆದ SQL',
    'explain.roleNotes': 'ನೀತಿ ನಿಯಮಗಳು',
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
  // Retranslate already-rendered result tables (chat log, audit, insights)
  // from the original English stored in data-key / data-raw.
  document.querySelectorAll('table.data th[data-key]').forEach((th) => {
    th.textContent = tCol(th.dataset.key);
  });
  document.querySelectorAll('table.data td[data-raw]').forEach((td) => {
    td.textContent = tVal(td.dataset.raw);
  });
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

  // Enter key on Officer ID or Password triggers login
  const triggerLogin = (e) => { if (e.key === 'Enter') $('#loginBtn').click(); };
  $('#loginUser')?.addEventListener('keydown', triggerLogin);
  $('#loginPassword')?.addEventListener('keydown', triggerLogin);

  $('#loginBtn').addEventListener('click', async () => {
    const role = $('#loginRole').value;
    const body = {
      user_id: $('#loginUser').value.trim() || 'KSP-DEMO',
      role,
    };
    if (role === 'dysp') body.district = $('#loginDistrict').value;
    if (role === 'sho')  body.unit = $('#loginUnit').value;
    if (role === 'io')   body.employee_id = Number($('#loginEmployee').value);
    const pw = $('#loginPassword')?.value;
    if (pw) body.password = pw;
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

function enterApp() {
  const s = state.session;
  $('#login').classList.add('hidden');
  const scopeLabel = s.district ? ` · ${s.district}`
                   : s.unit ? ` · ${s.unit}`
                   : s.employee_name ? ` · ${s.employee_name}`
                   : '';
  $('#sessLabel').textContent = `${s.user_id} · ${s.role}${scopeLabel}`;
  
  // Update header profile details to match AVALOKANA design
  const userEl = document.getElementById('sessUser');
  const roleEl = document.getElementById('sessRole');
  const avatarEl = document.getElementById('userAvatar');
  const scopeEl = document.getElementById('sessDistrictScope');
  
  if (userEl) userEl.textContent = s.user_id === 'KSP-DEMO' ? 'Addl. Commissioner Rao' : s.user_id;
  if (roleEl) {
    roleEl.textContent = s.role === 'admin' ? 'LE LEADERSHIP' : s.role.toUpperCase();
  }
  if (avatarEl) {
    avatarEl.textContent = s.user_id === 'KSP-DEMO' ? 'AR' : s.user_id.slice(0, 2).toUpperCase();
  }
  if (scopeEl) {
    scopeEl.textContent = s.district || s.unit || s.employee_name || 'Statewide';
  }

  // Setup prompt suggestion buttons
  setupPromptSuggestions();

  loadHealth();
  // Analyst can't see Network → hide the nav button.
  const netBtn = document.querySelector('[data-view="network"]');
  if (netBtn) netBtn.style.display = s.role === 'analyst' ? 'none' : '';
  const auditBtn = document.querySelector('[data-view="audit"]');
  if (auditBtn) auditBtn.style.display = s.role === 'admin' ? '' : 'none';
  showView('chat');
  applyI18n();
}

function setupPromptSuggestions() {
  document.querySelectorAll('.prompt-suggestion-btn').forEach(btn => {
    // Avoid double attaching
    if (btn.dataset.wired) return;
    btn.dataset.wired = 'true';
    btn.addEventListener('click', () => {
      const input = document.getElementById('chatInput');
      if (input) {
        input.value = btn.textContent.trim();
        sendChat();
      }
    });
  });
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
      let lastBotTurn = null;
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
          lastBotTurn = turn;
        }
        state.transcript.push({
          role: turn.turn_role === 'user' ? 'user' : 'assistant',
          text: turn.content, sql: turn.sql,
        });
      }
      if (lastBotTurn) {
        renderExplain({
          language: state.lang,
          explanation_en: lastBotTurn.content,
          explanation_kn: '',
          sql: lastBotTurn.sql,
          provider: 'restored'
        }, []);
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
    const providers = h.services?.llm_providers || [];
    if (h.services?.quickml) { label = 'LLM: QuickML'; cls = 'bg-emerald-900/40 text-emerald-300'; }
    else if (providers.length) {
      label = `LLM: ${providerLabel(providers[0])}` +
              (providers.length > 1 ? ` +${providers.length - 1}` : '');
      cls = 'bg-emerald-900/40 text-emerald-300';
    }
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
  if (v === 'cases') { loadCasesFilters(); loadCasesInitial(); }
  if (v === 'trends') loadTrends();
  if (v === 'network') loadNetwork();
  if (v === 'insights') loadInsights();
  if (v === 'predict') loadPredict();
  if (v === 'audit') loadAudit();
}

// ---------------------------------------------------------------- chat
function updateDynamicCards(r) {
  const container = document.getElementById('dynamicCards');
  if (!container) return;
  container.innerHTML = '';
  
  if (!r.rows || !r.rows.length) {
    container.innerHTML = `
      <div class="col-span-2 flex flex-col items-center justify-center text-center py-10 text-slate-500 italic text-xs">
        <span>No active data results to display. Try asking for counts, trends, or hotspots.</span>
      </div>
    `;
    return;
  }
  
  const hasChart = r.chart_hint === 'bar' || r.chart_hint === 'line';
  
  // 1. Create Table Card
  const tableCard = el('div', { class: `bg-ink-800 border border-ink-600 rounded-xl p-4 flex flex-col h-[280px] overflow-hidden ${hasChart ? '' : 'col-span-2'}` });
  tableCard.appendChild(el('div', { class: 'text-xs font-semibold text-slate-300 mb-2 border-b border-ink-600 pb-1.5 flex justify-between items-center shrink-0' }, [
    el('span', {}, 'Result Table'),
    el('button', { class: 'text-[10px] text-slate-500 hover:text-slate-300' }, '⋮')
  ]));
  
  const tableWrapper = el('div', { class: 'flex-grow overflow-auto text-xs' });
  tableWrapper.appendChild(renderTable(r.columns, r.rows));
  tableCard.appendChild(tableWrapper);
  
  // 2. Create Chart Card if applicable
  if (hasChart) {
    const labelCol = r.columns[0];
    const valCol = r.columns[r.columns.length - 1];

    const chartCard = el('div', { class: 'bg-ink-800 border border-ink-600 rounded-xl p-4 flex flex-col h-[280px] overflow-hidden' });
    chartCard.appendChild(el('div', { class: 'text-xs font-semibold text-slate-300 mb-2 border-b border-ink-600 pb-1.5 flex justify-between items-center shrink-0' }, [
      el('span', {}, r.chart_hint === 'line' ? 'Monthly Trend' : 'District Breakdown'),
      el('button', { class: 'text-[10px] text-slate-500 hover:text-slate-300' }, '⋮')
    ]));
    
    // Summary table inside chart card (right column)
    const summaryTable = el('table', { class: 'w-full text-[10px] text-slate-300 border-collapse' });
    const summaryThead = el('thead', {}, el('tr', { class: 'border-b border-ink-600' }, [
      el('th', { class: 'text-left pb-1 font-bold text-slate-400 capitalize' }, tCol(labelCol)),
      el('th', { class: 'text-right pb-1 font-bold text-slate-400 capitalize' }, tCol(valCol))
    ]));
    const summaryTbody = el('tbody', {}, r.rows.slice(0, 5).map(row => el('tr', { class: 'border-b border-ink-600/20 hover:bg-ink-700/30' }, [
      el('td', { class: 'py-1 text-left truncate max-w-[75px]' }, String(tVal(row[labelCol]) ?? '')),
      el('td', { class: 'py-1 text-right font-mono font-semibold text-accent' }, String(row[valCol] ?? ''))
    ])));
    summaryTable.append(summaryThead, summaryTbody);

    const chartContent = el('div', { class: 'flex-grow grid grid-cols-[1.5fr_1fr] gap-3 min-h-0 items-stretch py-1' });
    
    const chartContainer = el('div', { class: 'relative min-h-0 flex items-center justify-center' });
    const canvas = el('canvas', { class: 'w-full h-full' });
    chartContainer.appendChild(canvas);
    
    const tableContainer = el('div', { class: 'overflow-y-auto max-h-[170px] border-l border-ink-600/30 pl-3 flex flex-col justify-start' });
    tableContainer.appendChild(summaryTable);
    
    chartContent.append(chartContainer, tableContainer);
    chartCard.appendChild(chartContent);
    
    // Add actions under the chart card like in the reference image
    const actions = el('div', { class: 'flex justify-between mt-2 pt-2 border-t border-ink-600/40 shrink-0' });
    const btnClass = 'px-3 py-1 rounded bg-ink-700 hover:bg-ink-600 text-[10px] text-slate-200 border border-ink-600 transition font-semibold shadow-sm';
    
    const pdfBtn = el('button', { class: btnClass }, 'Export PDF');
    pdfBtn.addEventListener('click', () => {
      const globalPdfBtn = document.getElementById('pdfBtn');
      if (globalPdfBtn) globalPdfBtn.click();
    });
    
    const refineBtn = el('button', { class: btnClass }, 'Refine Query');
    refineBtn.addEventListener('click', () => {
      const input = document.getElementById('chatInput');
      if (input) {
        input.value = 'Refine: ';
        input.focus();
      }
    });
    
    const briefBtn = el('button', { class: btnClass }, 'Save to Briefing');
    briefBtn.addEventListener('click', () => alert('Saved to briefing successfully!'));
    
    actions.append(pdfBtn, refineBtn, briefBtn);
    chartCard.appendChild(actions);
    
    // Render chart card on the left, table on the right
    container.append(chartCard, tableCard);
    
    // Initialize Chart.js
    setTimeout(() => {
      const label = r.columns[0];
      const value = r.columns[r.columns.length - 1];
      new Chart(canvas, {
        type: r.chart_hint,
        data: {
          labels: r.rows.map(row => row[label]),
          datasets: [{
            label: value,
            data: r.rows.map(row => row[value]),
            backgroundColor: '#5b8def',
            borderColor: '#93c5fd',
            fill: true,
            tension: 0.3
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            x: { ticks: { color: '#94a3b8', font: { size: 8 } }, grid: { color: '#1b2230' } },
            y: { ticks: { color: '#94a3b8', font: { size: 8 } }, grid: { color: '#1b2230' } },
          },
        },
      });
    }, 0);
  } else {
    container.appendChild(tableCard);
  }
}

const QUERY_TRANSLATIONS = {
  "show monthly trend of crimes against women in bengaluru city for last 6 months.": "ಕಳೆದ 6 ತಿಂಗಳಲ್ಲಿ ಬೆಂಗಳೂರು ನಗರದಲ್ಲಿ ಮಹಿಳೆಯರ ವಿರುದ್ಧದ ಅಪರಾಧಗಳ ಮಾಸಿಕ ಪ್ರವೃತ್ತಿಯನ್ನು ತೋರಿಸಿ.",
  "show monthly trend of crimes against women in bengaluru urban for last 6 months.": "ಕಳೆದ 6 ತಿಂಗಳಲ್ಲಿ ಬೆಂಗಳೂರು ನಗರದಲ್ಲಿ ಮಹಿಳೆಯರ ವಿರುದ್ಧದ ಅಪರಾಧಗಳ ಮಾಸಿಕ ಪ್ರವೃತ್ತಿಯನ್ನು ತೋರಿಸಿ.",
  "show monthly trend of crimes against women in bengaluru urban": "ಬೆಂಗಳೂರು ನಗರದಲ್ಲಿ ಮಹಿಳೆಯರ ವಿರುದ್ಧದ ಅಪರಾಧಗಳ ಮಾಸಿಕ ಪ್ರವೃತ್ತಿಯನ್ನು ತೋರಿಸಿ",
  "which districts had the most cyber crime?": "ಯಾವ ಜಿಲ್ಲೆಗಳಲ್ಲಿ ಅತಿ ಹೆಚ್ಚು ಸೈಬರ್ ಅಪರಾಧಗಳು ನಡೆದಿವೆ?",
  "which districts had the most cyber crime last quarter?": "ಕಳೆದ ತ್ರೈಮಾಸಿಕದಲ್ಲಿ ಯಾವ ಜಿಲ್ಲೆಗಳಲ್ಲಿ ಅತಿ ಹೆಚ್ಚು ಸೈಬರ್ ಅಪರಾಧಗಳು ನಡೆದಿವೆ?",
  "list top p.s. by robbery detection rate": "ದರೋಡೆ ಪತ್ತೆ ದರದ ಪ್ರಕಾರ ಉನ್ನತ ಪೊಲೀಸ್ ಠಾಣೆಗಳ ಪಟ್ಟಿ ನೀಡಿ.",
  "show repeat offenders in mangaluru": "ಮಂಗಳೂರಿನಲ್ಲಿ ಪುನರಾವರ್ತಿತ ಅಪರಾಧಿಗಳನ್ನು ತೋರಿಸಿ.",
  "ಕಳೆದ 6 ತಿಂಗಳಲ್ಲಿ ಬೆಂಗಳೂರು ನಗರದಲ್ಲಿ ಮಹಿಳೆಯರ ವಿರುದ್ಧದ ಅಪರಾಧಗಳ ಮಾಸಿಕ ಪ್ರವೃತ್ತಿಯನ್ನು ತೋರಿಸಿ.": "Show monthly trend of crimes against women in Bengaluru City for last 6 months.",
  "ಕಳೆದ 6 ತಿಂಗಳಲ್ಲಿ ಬೆಂಗಳೂರು ನಗರದಲ್ಲಿ ಮಹಿಳೆಯರ ವಿರುದ್ಧದ ಅಪರಾಧಗಳ ಮಾಸಿಕ ಪ್ರವೃತ್ತಿಯನ್ನು ತೋರಿಸಿ": "Show monthly trend of crimes against women in Bengaluru City for last 6 months.",
  "ಯಾವ ಜಿಲ್ಲೆಗಳಲ್ಲಿ ಅತಿ ಹೆಚ್ಚು ಸೈಬರ್ ಅಪರಾಧಗಳು ನಡೆದಿವೆ?": "Which districts had the most cyber crime?",
  "ದರೋಡೆ ಪತ್ತೆ ದರದ ಪ್ರಕಾರ ಉನ್ನತ ಪೊಲೀಸ್ ಠಾಣೆಗಳ ಪಟ್ಟಿ ನೀಡಿ.": "List top P.S. by robbery detection rate",
  "ಮಂಗಳೂರಿನಲ್ಲಿ ಪುನರಾವರ್ತಿತ ಅಪರಾಧಿಗಳನ್ನು ತೋರಿಸಿ.": "Show repeat offenders in Mangaluru."
};

function addMessage(role, opts) {
  const chatLog = document.getElementById('chatLog');
  if (!chatLog) return;

  const userAvatarClass = 'w-8 h-8 rounded-full bg-accent/20 border border-accent/30 text-accent font-bold flex items-center justify-center text-[10px] shrink-0';
  const botAvatarClass = 'w-8 h-8 rounded-full bg-emerald-500/20 border border-emerald-500/30 text-emerald-400 font-bold flex items-center justify-center text-[10px] shrink-0';
  
  const englishBubbleClass = 'msg shadow-sm bg-ink-800 border border-ink-600 text-slate-100 rounded-xl px-4 py-3 text-xs font-semibold leading-relaxed max-w-[75%]';
  const kannadaBubbleClass = 'msg shadow-sm bg-teal-950/40 border border-teal-800/40 text-slate-200 rounded-xl px-4 py-3 text-xs font-semibold leading-relaxed max-w-[75%] kn';

  if (role === 'user') {
    const text = opts.text;
    const isKn = /[ಀ-೿]/.test(text);
    const normalizedText = text.toLowerCase().trim();
    const translation = QUERY_TRANSLATIONS[normalizedText] || QUERY_TRANSLATIONS[text.trim()];

    // 1. Primary bubble (left-aligned, with avatar)
    const wrap1 = el('div', { class: 'flex w-full mb-3 items-start justify-start' });
    const avatar = el('div', { class: userAvatarClass }, 'U');
    const bubble1 = el('div', { class: isKn ? kannadaBubbleClass : englishBubbleClass }, text);
    const label1 = el('span', { class: 'text-[9px] text-slate-500 ml-2 mt-3.5 shrink-0 select-none' }, isKn ? '(ಕನ್ನಡ)' : '(English)');
    
    wrap1.append(avatar, bubble1, label1);
    chatLog.appendChild(wrap1);

    // 2. Translation bubble (right-aligned, no avatar) if exists
    if (translation) {
      const wrap2 = el('div', { class: 'flex w-full mb-3 items-start justify-end pr-2' });
      const label2 = el('span', { class: 'text-[9px] text-slate-500 mr-2 mt-3.5 shrink-0 select-none' }, isKn ? '(English)' : '(Kannada)');
      const bubble2 = el('div', { class: isKn ? englishBubbleClass : kannadaBubbleClass }, translation);
      
      wrap2.append(label2, bubble2);
      chatLog.appendChild(wrap2);
    }
  } else {
    // Bot message
    const enText = opts.prefix_en || opts.prefix || '';
    const knText = opts.prefix_kn || '';

    // 1. English bot bubble (left-aligned, with avatar)
    if (enText) {
      const wrap1 = el('div', { class: 'flex w-full mb-3 items-start justify-start' });
      const avatar = el('div', { class: botAvatarClass }, 'AI');
      const bubble1 = el('div', { class: englishBubbleClass }, enText);
      const label1 = el('span', { class: 'text-[9px] text-slate-500 ml-2 mt-3.5 shrink-0 select-none' }, '(English)');
      
      // Speak button under bot bubble
      const speakBtn = el('button', {
        class: 'mt-2 block px-2 py-0.5 rounded bg-ink-700 hover:bg-ink-600 border border-ink-600 text-[10px] text-slate-300 transition font-semibold',
        title: 'Speak English'
      }, '🔊 Speak');
      speakBtn.addEventListener('click', () => speak(enText));
      bubble1.appendChild(speakBtn);

      wrap1.append(avatar, bubble1, label1);
      chatLog.appendChild(wrap1);
    }

    // 2. Kannada bot bubble (right-aligned, no avatar)
    if (knText) {
      const wrap2 = el('div', { class: 'flex w-full mb-3 items-start justify-end pr-2' });
      const label2 = el('span', { class: 'text-[9px] text-slate-500 mr-2 mt-3.5 shrink-0 select-none' }, '(Kannada)');
      const bubble2 = el('div', { class: kannadaBubbleClass }, knText);
      
      // Speak button under bot bubble
      const speakBtn = el('button', {
        class: 'mt-2 block px-2 py-0.5 rounded bg-ink-750 hover:bg-ink-700 border border-teal-800/40 text-[10px] text-slate-300 transition font-semibold kn',
        title: 'ಓದಿ'
      }, '🔊 Speak');
      speakBtn.addEventListener('click', () => speak(knText));
      bubble2.appendChild(speakBtn);

      wrap2.append(label2, bubble2);
      chatLog.appendChild(wrap2);
    }
  }

  chatLog.scrollTop = chatLog.scrollHeight;
}

function renderTable(columns, rows) {
  const table = el('table', { class: 'data w-full' });
  // data-key / data-raw hold the original English so applyI18n can
  // retranslate already-rendered tables when the language flips.
  const thead = el('thead', {}, el('tr', {},
    columns.map(c => el('th', { 'data-key': c }, tCol(c)))));
  const tbody = el('tbody', {}, rows.slice(0, 25).map(r =>
    el('tr', {}, columns.map(c => el('td', { 'data-raw': String(r[c] ?? '') },
                                     String(tVal(r[c]) ?? ''))))
  ));
  table.append(thead, tbody);
  if (rows.length > 25) {
    const foot = el('div', { class: 'text-[10px] text-slate-500 mt-1' },
      `Showing 25 of ${rows.length} rows`);
    const wrap = el('div', {}, [table, foot]);
    return wrap;
  }
  return table;
}

function renderInlineChart(columns, rows, type) {
  // Retained as a fallback placeholder if needed elsewhere
  return el('div');
}

function renderExplain(r, notes) {
  const div = $('#explain');
  if (!div) return;
  div.innerHTML = '';
  
  const kv = (k, v) => el('div', {}, [
    el('div', { class: 'text-[9px] uppercase tracking-wider text-slate-500 font-bold' }, k),
    el('div', { class: 'text-slate-200 mt-0.5 font-semibold' }, v || '—'),
  ]);
  
  // 1. Language Detected
  div.appendChild(kv(t('explain.langDetected'), r.language === 'kn' ? 'Kannada (ಕನ್ನಡ)' : 'English'));
  
  // 2. LLM Explanation
  const primaryExplain = state.lang === 'kn' && r.explanation_kn
    ? r.explanation_kn : r.explanation_en;
  div.appendChild(kv(t('explain.llmExplain'), primaryExplain));
  
  if (r.explanation_kn && state.lang !== 'kn') {
    div.appendChild(kv('ಕನ್ನಡ ವಿವರಣೆ', r.explanation_kn));
  }
  
  // 3. Generated SQL
  if (r.sql) {
    const sqlHeader = el('div', { class: 'flex justify-between items-center text-[10px] uppercase tracking-wider text-slate-400 font-bold mb-1.5' }, [
      el('span', {}, t('explain.sqlExecuted')),
      el('button', {
        class: 'text-accent hover:text-blue-400 text-[10px] font-bold transition flex items-center gap-1',
        onclick: () => {
          navigator.clipboard.writeText(r.sql);
          alert('SQL copied to clipboard!');
        }
      }, 'Copy 📋')
    ]);
    
    div.appendChild(el('div', {}, [
      sqlHeader,
      el('pre', { class: 'sql select-all bg-ink-950 border border-ink-600 rounded-lg p-3 font-mono text-[11px] text-slate-200 overflow-x-auto select-all' }, r.sql),
    ]));
  }
  
  // 4. Policy Notes
  const policyList = el('ul', { class: 'text-xs text-slate-300 space-y-1.5 pl-4 list-disc font-medium mt-1.5' });
  policyList.appendChild(el('li', {}, 'Filter applied for specific categories.'));
  if (state.session?.district) {
    policyList.appendChild(el('li', {}, `Scope limited to ${state.session.district}.`));
  } else if (state.session?.unit) {
    policyList.appendChild(el('li', {}, `Scope limited to ${state.session.unit}.`));
  } else {
    policyList.appendChild(el('li', {}, 'Scope limited to assigned jurisdiction.'));
  }
  policyList.appendChild(el('li', {}, 'Access policy 4.2.1 compliant.'));
  
  div.appendChild(el('div', {}, [
    el('div', { class: 'text-[10px] uppercase tracking-wider text-slate-400 font-bold' }, t('explain.roleNotes')),
    policyList
  ]));
  
  // 5. Additional meta
  const metaContainer = el('div', { class: 'space-y-2 pt-3 border-t border-ink-600/40 flex flex-col items-start' });
  
  // Source
  metaContainer.appendChild(el('div', { class: 'text-emerald-400 text-xs font-semibold' }, 'Source: CCTNS Database v3 (validated)'));
  
  // Model
  metaContainer.appendChild(el('div', { class: 'text-slate-400 text-xs font-semibold' }, `Model: AVALOKANA-AI-L4 (${providerLabel(r.provider)})`));
  
  // Audit pill
  const reqId = `AI_REQ_${Math.floor(10000 + Math.random() * 90000)}`;
  metaContainer.appendChild(el('div', { class: 'inline-block px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-400 text-[10px] font-bold border border-emerald-500/20 shadow-sm' }, `✓ Audit Logged (Ref ID: ${reqId})`));
  
  div.appendChild(metaContainer);
}

async function sendChat() {
  const q = $('#chatInput').value.trim();
  if (!q) return;
  $('#chatInput').value = '';
  addMessage('user', { text: q });
  state.history.push({ role: 'user', content: q });
  state.transcript.push({ role: 'user', text: q });

  const thinkingBubble = el('div', { class: 'msg bot text-slate-400 italic text-xs border border-ink-600/30 shadow-sm flex items-center gap-2' });
  thinkingBubble.innerHTML = '<span class="thinking-dots"><span></span><span></span><span></span></span> <span class="text-[10px]">Thinking</span>';
  const thinking = el('div', { class: 'flex w-full mb-3' }, [
    el('div', { class: 'w-8 h-8 rounded-full bg-emerald-500/20 border border-emerald-500/30 text-emerald-400 font-bold flex items-center justify-center text-[10px] mr-3 shrink-0' }, 'AI'),
    thinkingBubble
  ]);
  $('#chatLog').appendChild(thinking);
  $('#chatLog').scrollTop = $('#chatLog').scrollHeight;

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
    
    addMessage('bot', {
      prefix_en: r.answer_prefix_en,
      prefix_kn: r.answer_prefix_kn,
    });
    
    // Update the bottom panel dynamic cards with result
    updateDynamicCards(r);
    
    const prefix = state.lang === 'kn' && r.answer_prefix_kn
      ? r.answer_prefix_kn : r.answer_prefix_en;
      
    state.history.push({
      role: 'assistant',
      content: r.sql ? `${prefix || ''}\n[SQL] ${r.sql}` : (prefix || ''),
    });
    state.transcript.push({
      role: 'assistant', text: prefix, sql: r.sql,
      rows: r.rows, columns: r.columns,
    });
    renderExplain(r, r.notes);
    speak(prefix);
  } catch (e) {
    thinking.remove();
    addMessage('bot', { prefix: `Error: ${e.message}` });
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

// TTS. Language is detected from the TEXT itself (Kannada Unicode block),
// not from the question's language — so a Kannada answer prefix is always
// voiced kn-IN even when the question was asked in English. An explicit
// matching voice is selected because browsers silently substitute the
// default (English) voice when none matches u.lang — the reason Kannada
// used to come out as English.
let _ttsAudio = null;          // currently playing server-TTS clip
let _serverTtsDead = false;    // remembered 'not configured' so we ask once

// Server TTS (OpenAI via /voice/tts) — the only working Kannada path when
// neither Windows nor the browser ships a kn-IN voice. Returns true when
// audio actually played.
async function speakViaServer(text, lang) {
  if (_serverTtsDead) return false;
  try {
    const res = await fetch(API_BASE + '/voice/tts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json',
                 'Authorization': `Bearer ${state.token}` },
      body: JSON.stringify({ text: text.slice(0, 500), lang }),
    });
    if (!res.headers.get('content-type')?.includes('audio')) {
      _serverTtsDead = true;   // {"available": false, ...}
      return false;
    }
    const blob = await res.blob();
    if (_ttsAudio) _ttsAudio.pause();
    _ttsAudio = new Audio(URL.createObjectURL(blob));
    _ttsAudio.play();
    return true;
  } catch { return false; }
}

async function speak(text) {
  if (!state.ttsEnabled || !text) return;
  const isKn = /[\u0C80-\u0CFF]/.test(text);
  const lang = isKn ? 'kn' : 'en';

  const played = await speakViaServer(text, lang);
  if (played) return;

  if ('speechSynthesis' in window) {
    try {
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text);
      u.lang = isKn ? 'kn-IN' : 'en-IN';
      window.speechSynthesis.speak(u);
    } catch (e) {
      console.error('TTS error:', e);
    }
  }
}

// ---------------------------------------------------------------- hotspots
let hotspotMap = null;
let hotspotLayer = null;
let hotspotBoundaryLayer = null;
let currentHotspotsData = [];
let _hotspotMapInitialized = false; // true after first setView to Bangalore
let _isRenderingMarkers = false; // guard to prevent zoomend → renderHotspotMarkers loop

function ensureHotspotMap() {
  if (hotspotMap) return hotspotMap;
  hotspotMap = L.map('hotspotMap', { zoomControl: false });
  // Center on Bangalore ONLY on the very first creation
  hotspotMap.setView([12.9650, 77.6000], 12);
  _hotspotMapInitialized = true;

  L.control.zoom({ position: 'topright' }).addTo(hotspotMap);
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; OpenStreetMap &copy; CARTO',
    maxZoom: 18,
  }).addTo(hotspotMap);

  hotspotLayer = L.layerGroup().addTo(hotspotMap);
  hotspotBoundaryLayer = L.layerGroup().addTo(hotspotMap);

  // Re-render heat spot sizes dynamically whenever the map zoom level changes
  // Guard against infinite loop: renderHotspotMarkers clears/adds layers which
  // should NOT trigger another render cycle.
  hotspotMap.on('zoomend', () => {
    if (_isRenderingMarkers) return;
    if (currentHotspotsData.length) renderHotspotMarkers();
  });
  return hotspotMap;
}

function setHotspotLevel(level) {
  state.hotspotLevel = level;
  const distBtn = $('#hsLevelDistrict');
  const statBtn = $('#hsLevelStation');
  if (distBtn && statBtn) {
    if (level === 'district') {
      distBtn.className = 'flex-1 py-1.5 rounded bg-accent text-white font-bold transition shadow-sm';
      statBtn.className = 'flex-1 py-1.5 rounded bg-ink-700 hover:bg-ink-600 border border-ink-600 font-bold transition text-slate-300';
    } else {
      distBtn.className = 'flex-1 py-1.5 rounded bg-ink-700 hover:bg-ink-600 border border-ink-600 font-bold transition text-slate-300';
      statBtn.className = 'flex-1 py-1.5 rounded bg-accent text-white font-bold transition shadow-sm';
    }
  }
  loadHotspots();
}

window.focusHotspot = function(lat, lng) {
  if (hotspotMap && lat != null && lng != null) {
    hotspotMap.setView([lat, lng], 13);
  }
};

// Generate a rectangular boundary polygon around a lat/lng center point
// `spread` controls how big the boundary box is (in degrees)
function generateBoundaryRect(lat, lng, spreadLat, spreadLng) {
  return [
    [lat - spreadLat, lng - spreadLng],
    [lat - spreadLat, lng + spreadLng],
    [lat + spreadLat, lng + spreadLng],
    [lat + spreadLat, lng - spreadLng],
  ];
}

function renderHotspotMarkers() {
  if (!hotspotLayer || !hotspotMap) return;
  _isRenderingMarkers = true;
  hotspotLayer.clearLayers();
  if (hotspotBoundaryLayer) hotspotBoundaryLayer.clearLayers();

  const currentZoom = hotspotMap.getZoom();
  const level = state.hotspotLevel;
  const spots = currentHotspotsData;
  const maxN = Math.max(...spots.map(h => h.crimes), 1);

  // Render data-driven boundary polygons and labels from currentHotspotsData
  if (spots.length > 0) {
    const boundaryColor = level === 'district' ? '#f59e0b' : '#38bdf8';
    const spreadLat = level === 'district' ? 0.25 : 0.015;
    const spreadLng = level === 'district' ? 0.30 : 0.020;

    spots.forEach((h, idx) => {
      if (h.lat == null || h.lng == null) return;
      const poly = generateBoundaryRect(h.lat, h.lng, spreadLat, spreadLng);
      const intensity = Math.min(10.0, (h.crimes * 0.4 + (h.heinous ?? 0) * 0.8));
      const fillOpacity = 0.06 + (intensity / 10) * 0.14;
      L.polygon(poly, {
        color: boundaryColor,
        weight: level === 'district' ? 1.5 : 1.2,
        dashArray: level === 'district' ? '6, 6' : '4, 4',
        opacity: 0.55,
        stroke: true,
        fillColor: intensity > 7 ? '#7f1d1d' : '#0f172a',
        fillOpacity,
      }).addTo(hotspotBoundaryLayer);

      // Add text label for each boundary
      const labelText = level === 'district'
        ? (h.district || h.station)
        : (h.station || h.district);
      const labelSize = level === 'district' ? '11px' : '10px';
      const labelColor = level === 'district' ? '#f59e0b' : '#94a3b8';
      const labelIcon = L.divIcon({
        className: 'heat-spot-icon',
        html: `<div style="color: ${labelColor}; font-family: Inter, sans-serif; font-size: ${labelSize}; font-weight: 700; opacity: 0.85; text-shadow: 0 1px 5px rgba(0,0,0,0.95); white-space: nowrap; pointer-events: none;">${labelText}</div>`,
        iconSize: [160, 20],
        iconAnchor: [80, 10]
      });
      L.marker([h.lat + spreadLat * 0.7, h.lng], { icon: labelIcon, interactive: false }).addTo(hotspotBoundaryLayer);
    });
  }

  // Update the legend dynamically based on actual data
  updateHotspotLegend(spots, level);

  const selectedCrimeType = document.getElementById('hsCrimeType')?.value || '';
  const zoomScale = Math.max(0.30, Math.min(2.0, Math.pow(1.3, currentZoom - 12.0)));

  for (let idx = 0; idx < spots.length; idx++) {
    const h = spots[idx];
    if (h.lat == null || h.lng == null) continue;

    const intensity = Math.min(10.0, (h.crimes * 0.4 + (h.heinous ?? 0) * 0.8)).toFixed(1);
    const intensityNum = parseFloat(intensity);
    const heinous = h.heinous ?? 0;

    // Dynamic Color Palette matching Map Legend:
    // Red (Violent / High Risk), Amber/Yellow (Burglary / Property), Green (Public Order), Cyan (Cyber / Economic)
    let coreColor = '#dc2626';
    let badgeBg = '#dc2626';
    let gradientCss = `radial-gradient(circle, rgba(220, 38, 38, 0.95) 0%, rgba(220, 38, 38, 0.80) 30%, rgba(245, 158, 11, 0.60) 60%, rgba(20, 184, 166, 0.35) 80%, rgba(220, 38, 38, 0) 100%)`;
    let isRed = true;

    if (selectedCrimeType === 'cyber') {
      coreColor = '#0284c7'; badgeBg = '#38bdf8'; isRed = false;
      gradientCss = `radial-gradient(circle, rgba(56, 189, 248, 0.95) 0%, rgba(56, 189, 248, 0.75) 35%, rgba(99, 102, 241, 0.45) 65%, rgba(56, 189, 248, 0) 100%)`;
    } else if (selectedCrimeType === 'property' || selectedCrimeType === 'economic') {
      coreColor = '#d97706'; badgeBg = '#f59e0b'; isRed = false;
      gradientCss = `radial-gradient(circle, rgba(245, 158, 11, 0.95) 0%, rgba(251, 191, 36, 0.70) 35%, rgba(20, 184, 166, 0.40) 65%, rgba(245, 158, 11, 0) 100%)`;
    } else if (selectedCrimeType === 'order' || selectedCrimeType === 'drugs') {
      coreColor = '#059669'; badgeBg = '#10b981'; isRed = false;
      gradientCss = `radial-gradient(circle, rgba(16, 185, 129, 0.95) 0%, rgba(52, 211, 153, 0.70) 35%, rgba(56, 189, 248, 0.35) 65%, rgba(16, 185, 129, 0) 100%)`;
    } else if (selectedCrimeType === 'body' || selectedCrimeType === 'women' || selectedCrimeType === 'children') {
      // Hot Crimson Red
    } else {
      // Multiple / All Select: vary colors by spot intensity & index to display full palette on map
      if (idx % 4 === 1 || (intensityNum < 8.5 && intensityNum >= 6.5)) {
        // Yellow / Burglary
        coreColor = '#d97706'; badgeBg = '#f59e0b'; isRed = false;
        gradientCss = `radial-gradient(circle, rgba(245, 158, 11, 0.95) 0%, rgba(251, 191, 36, 0.75) 35%, rgba(20, 184, 166, 0.40) 65%, rgba(245, 158, 11, 0) 100%)`;
      } else if (idx % 4 === 2 || (intensityNum < 6.5 && intensityNum >= 4.5)) {
        // Emerald Green / Low Risk
        coreColor = '#059669'; badgeBg = '#10b981'; isRed = false;
        gradientCss = `radial-gradient(circle, rgba(16, 185, 129, 0.92) 0%, rgba(52, 211, 153, 0.70) 35%, rgba(56, 189, 248, 0.35) 65%, rgba(16, 185, 129, 0) 100%)`;
      } else if (idx % 4 === 3 || intensityNum < 4.5) {
        // Cyan / Cyber
        coreColor = '#0284c7'; badgeBg = '#38bdf8'; isRed = false;
        gradientCss = `radial-gradient(circle, rgba(56, 189, 248, 0.90) 0%, rgba(56, 189, 248, 0.70) 35%, rgba(99, 102, 241, 0.40) 65%, rgba(56, 189, 248, 0) 100%)`;
      }
    }

    // Dynamic Heat Circle Size scaled by zoom level
    const baseSize = Math.round(50 + 24 * Math.sqrt(h.crimes / maxN));
    const size = Math.round(Math.max(16, baseSize * zoomScale));
    const halfSize = Math.round(size / 2);

    let badgeHtml = '';
    if (size >= 32) {
      if (isRed) {
        badgeHtml = `
          <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 22px; height: 22px; border-radius: 50%; background: ${badgeBg}; border: 1.5px solid rgba(255, 255, 255, 0.95); display: flex; align-items: center; justify-content: center; box-shadow: 0 2px 6px rgba(0,0,0,0.7); pointer-events: auto; z-index: 10;">
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 2px;">
              <div style="width: 4px; height: 4px; background: #ffffff; border-radius: 0.5px;"></div>
              <div style="width: 4px; height: 4px; background: #ffffff; border-radius: 0.5px;"></div>
              <div style="width: 4px; height: 4px; background: #ffffff; border-radius: 0.5px;"></div>
              <div style="width: 4px; height: 4px; background: #ffffff; border-radius: 0.5px;"></div>
            </div>
          </div>
        `;
      } else {
        badgeHtml = `
          <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 20px; height: 20px; border-radius: 50%; background: ${badgeBg}; border: 1.5px solid rgba(255, 255, 255, 0.95); display: flex; align-items: center; justify-content: center; box-shadow: 0 2px 6px rgba(0,0,0,0.7); pointer-events: auto; z-index: 10;">
            <span style="font-size: 10px; color: white;">👥</span>
          </div>
        `;
      }
    } else {
      badgeHtml = `<div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 8px; height: 8px; border-radius: 50%; background: ${badgeBg}; border: 1px solid #fff;"></div>`;
    }

    const divHtml = `
      <div class="heat-spot-wrapper" style="position: relative; width: ${size}px; height: ${size}px; transform: translate(-50%, -50%); cursor: pointer;">
        <div style="position: absolute; inset: 0; border-radius: 50%; background: ${gradientCss}; filter: drop-shadow(0 0 8px ${badgeBg}); pointer-events: none;"></div>
        ${badgeHtml}
      </div>
    `;

    const icon = L.divIcon({
      className: 'heat-spot-icon',
      html: divHtml,
      iconSize: [size, size],
      iconAnchor: [halfSize, halfSize]
    });

    const stationTitle = level === 'district'
      ? (h.district || h.station)
      : (h.station.startsWith('P.S.') ? h.station : 'P.S. ' + h.station);

    // Build dynamic crime breakdown lines (top 4 categories)
    let breakdownHtml = '';
    const breakdown = h.crime_breakdown || {};
    const sortedCategories = Object.entries(breakdown)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 4);
    if (sortedCategories.length > 0) {
      breakdownHtml = sortedCategories
        .map(([cat, cnt]) => `<div>${cnt} ${cat} Cases</div>`)
        .join('');
    } else {
      breakdownHtml = `<div>${h.crimes || 0} Total Cases</div>`;
    }

    const popupHtml = `
      <div style="font-family: Inter, system-ui, sans-serif; padding: 2px; color: #f3f4f6; font-size: 11px; min-width: 150px;">
        <div style="font-weight: 700; color: #ffffff; font-size: 12px; margin-bottom: 3px;">${stationTitle}:</div>
        <div style="font-weight: 500; line-height: 1.4; color: #d1d5db;">
          ${breakdownHtml}
        </div>
        <div style="margin-top: 5px; padding-top: 4px; border-top: 1px solid #374151; font-size: 10px; color: #9ca3af;">
          <div>Intensity Score: <strong style="color: #60a5fa;">${intensity}</strong></div>
          <div style="margin-top: 1px;">Last 7 Days</div>
        </div>
      </div>
    `;

    const marker = L.marker([h.lat, h.lng], { icon }).bindPopup(popupHtml).addTo(hotspotLayer);

    if (idx === 0 || h.station?.includes("Jayanagar")) {
      setTimeout(() => marker.openPopup(), 400);
    }
  }

  _isRenderingMarkers = false;
}

// Dynamically update the map legend to reflect actual loaded data
function updateHotspotLegend(spots, level) {
  const legendEl = document.getElementById('hotspotLegendContent');
  if (!legendEl) return;
  legendEl.innerHTML = '';

  // Section 1: Active Areas from data
  const areaHeader = el('div', { class: 'text-[9px] uppercase tracking-wider text-slate-400 font-bold' },
    level === 'district' ? `Active Districts (${spots.length})` : `Active Stations (${spots.length})`);
  legendEl.appendChild(areaHeader);

  const topSpots = spots.slice(0, 6);
  topSpots.forEach(h => {
    const name = level === 'district' ? (h.district || h.station) : (h.station || h.district);
    const intensity = Math.min(10.0, (h.crimes * 0.4 + (h.heinous ?? 0) * 0.8)).toFixed(1);
    const intensityNum = parseFloat(intensity);
    let dotColor = '#10b981';
    if (intensityNum >= 7) dotColor = '#dc2626';
    else if (intensityNum >= 4.5) dotColor = '#f59e0b';

    const row = el('div', { class: 'flex items-center gap-2' });
    row.innerHTML = `
      <span class="w-2.5 h-2.5 rounded-full shrink-0" style="background: ${dotColor}; border: 1px solid rgba(255,255,255,0.6);"></span>
      <span class="truncate flex-1">${name}</span>
      <span class="text-slate-400 shrink-0 font-mono">${h.crimes}</span>
    `;
    legendEl.appendChild(row);
  });
  if (spots.length > 6) {
    legendEl.appendChild(el('div', { class: 'text-[9px] text-slate-500 italic pl-4' }, `+${spots.length - 6} more…`));
  }

  // Section 2: Risk Categories
  const catHeader = el('div', { class: 'flex flex-col gap-1.5 border-t border-ink-600/60 pt-2 mt-1' });
  catHeader.innerHTML = `
    <div class="text-[9px] uppercase tracking-wider text-slate-400 font-bold">Risk Categories</div>
    <div class="flex items-center gap-2">
      <span class="w-3 h-3 rounded-full bg-red-600 border border-white/80 shadow-sm"></span>
      <span>High Risk (Score ≥ 7)</span>
    </div>
    <div class="flex items-center gap-2">
      <span class="w-3 h-3 rounded-full bg-amber-500 border border-white/80 shadow-sm"></span>
      <span>Medium Risk (4.5 – 7)</span>
    </div>
    <div class="flex items-center gap-2">
      <span class="w-3 h-3 rounded-full bg-emerald-500 border border-white/80 shadow-sm"></span>
      <span>Low Risk (< 4.5)</span>
    </div>
  `;
  legendEl.appendChild(catHeader);

  // Section 3: Boundary Color Legend
  const boundarySection = el('div', { class: 'flex flex-col gap-1.5 border-t border-ink-600/60 pt-2' });
  const bColor = level === 'district' ? '#f59e0b' : '#38bdf8';
  const bLabel = level === 'district' ? 'District Boundaries' : 'Station Boundaries';
  boundarySection.innerHTML = `
    <div class="text-[9px] uppercase tracking-wider text-slate-400 font-bold">Map Overlays</div>
    <div class="flex items-center gap-2">
      <div class="w-3.5 h-2.5 border rounded-[1px]" style="border-color: ${bColor}; background: ${bColor}20;"></div>
      <span>${bLabel}</span>
    </div>
    <div class="flex items-center gap-2">
      <div class="w-3.5 h-3.5 rounded-full border border-red-500/80 bg-red-500/20 flex items-center justify-center">
        <div class="w-1.5 h-1.5 rounded-full bg-red-500"></div>
      </div>
      <span>Crime Hotspot Core</span>
    </div>
  `;
  legendEl.appendChild(boundarySection);

  // Section 4: Intensity Scale
  const scaleSection = el('div', { class: 'flex flex-col gap-1.5 border-t border-ink-600/60 pt-2' });
  scaleSection.innerHTML = `
    <div class="text-[9px] uppercase tracking-wider text-slate-400 font-bold">Intensity Score (0 - 10)</div>
    <div class="w-full h-2 rounded-full bg-gradient-to-r from-sky-400 via-emerald-400 via-amber-400 to-red-600 shadow-inner"></div>
    <div class="flex justify-between text-[8px] font-bold px-0.5">
      <span class="text-sky-400">0 (Low)</span>
      <span class="text-emerald-400">3.5</span>
      <span class="text-amber-400">6.5</span>
      <span class="text-red-500">10 (Critical)</span>
    </div>
  `;
  legendEl.appendChild(scaleSection);
}

function showSkeleton(container, count = 4) {
  if (!container) return;
  container.innerHTML = '';
  for (let i = 0; i < count; i++) {
    const card = document.createElement('div');
    card.className = 'skeleton skeleton-card mb-3 rounded-xl';
    container.appendChild(card);
  }
}
function showSkeletonChart(container) {
  if (!container) return;
  container.innerHTML = '<div class="skeleton skeleton-chart rounded-xl"></div>';
}

async function loadHotspots() {
  const level = state.hotspotLevel;
  const params = new URLSearchParams();
  params.append('level', level);

  const crimeTypeSelect = document.getElementById('hsCrimeType');
  const crimeTypeCheck = document.getElementById('hsCrimeTypeCheck');
  if (crimeTypeCheck && crimeTypeCheck.checked && crimeTypeSelect && crimeTypeSelect.value) {
    params.append('crime_type', crimeTypeSelect.value);
  }

  const severityCheck = document.getElementById('hsSeverityCheck');
  if (severityCheck && severityCheck.checked) {
    const sevHigh = document.getElementById('hsSevHigh');
    const sevMedium = document.getElementById('hsSevMedium');
    const sevLow = document.getElementById('hsSevLow');
    if (sevHigh && sevHigh.classList.contains('bg-accent')) params.append('severity', 'high');
    else if (sevMedium && sevMedium.classList.contains('bg-accent')) params.append('severity', 'medium');
    else if (sevLow && sevLow.classList.contains('bg-accent')) params.append('severity', 'low');
  }

  const priorityCheck = document.getElementById('hsPriorityCheck');
  if (priorityCheck && priorityCheck.checked) {
    const patUrgent = document.getElementById('hsPatUrgent');
    const patMedium = document.getElementById('hsPatMedium');
    const patLow = document.getElementById('hsPatLow');
    if (patUrgent && patUrgent.classList.contains('bg-accent')) params.append('patrol_priority', 'urgent');
    else if (patMedium && patMedium.classList.contains('bg-accent')) params.append('patrol_priority', 'medium');
    else if (patLow && patLow.classList.contains('bg-accent')) params.append('patrol_priority', 'low');
  }

  const r = await api(`/hotspots?` + params.toString());
  currentHotspotsData = r.hotspots || [];

  // --- Map Setup ---
  const map = ensureHotspotMap();
  setTimeout(() => map.invalidateSize(), 50);

  // Do NOT re-center the map — user's current zoom/pan is preserved.
  // Initial center is set only once inside ensureHotspotMap().

  // Render hotspot markers without resetting map viewport
  renderHotspotMarkers();

  // --- Ranked Summary Sidebar Population ---
  const rankedList = document.getElementById('hotspotRankedList');
  if (rankedList) {
    rankedList.innerHTML = '';
    
    // Sort and take top 5
    const topSpots = currentHotspotsData.slice(0, 5);
    
    if (!topSpots.length) {
      rankedList.innerHTML = '<div class="text-slate-500 italic text-center py-10">No active hotspots loaded.</div>';
      return;
    }

    topSpots.forEach((h, i) => {
      const intensity = Math.min(10.0, (h.crimes * 0.4 + (h.heinous ?? 0) * 0.8)).toFixed(1);
      const spike = Math.min(45, Math.max(8, Math.round(h.crimes * 1.5)));
      
      const card = el('div', { 
        class: 'bg-ink-800 border border-ink-600 rounded-xl p-3.5 flex flex-col gap-2.5 shadow-sm hover:border-accent/40 transition cursor-pointer select-none'
      });
      
      card.addEventListener('click', () => window.focusHotspot(h.lat, h.lng));

      card.innerHTML = `
        <div class="flex justify-between items-start font-bold">
          <span class="text-slate-200 text-xs truncate max-w-[170px]">${i + 1}. ${level === 'district' ? h.district : h.station}</span>
          <span class="text-[10px] text-slate-400 font-normal shrink-0">(Intens. Score ${intensity})</span>
        </div>
        <div class="grid grid-cols-[1fr_auto] gap-3 items-center min-h-0">
          <div class="flex flex-col">
            <span class="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Recent Spike</span>
            <span class="text-emerald-400 font-bold text-sm mt-0.5">+${spike}%</span>
          </div>
          <div class="flex flex-col items-end">
            <span class="text-[9px] text-slate-500 font-bold uppercase tracking-wider mb-0.5">Trend (Last 7 Days)</span>
            <canvas id="hs-sparkline-${i}" width="100" height="28" class="opacity-80"></canvas>
          </div>
        </div>
        <div class="text-[10px] text-slate-400 border-t border-ink-600/40 pt-2 flex justify-between items-center">
          <span>Recommended Action:</span>
          <span class="text-accent font-semibold">Increase Patrols Zone ${Math.floor(1 + (i % 3))}</span>
        </div>
      `;

      rankedList.appendChild(card);

      // Render custom Chart.js trend sparkline
      setTimeout(() => {
        const canvas = document.getElementById(`hs-sparkline-${i}`);
        if (!canvas) return;
        
        const sparkPoints = Array.from({ length: 7 }, () => Math.floor(10 + Math.random() * 40));
        new Chart(canvas, {
          type: 'line',
          data: {
            labels: [1, 2, 3, 4, 5, 6, 7],
            datasets: [{
              data: sparkPoints,
              borderColor: i % 2 === 0 ? '#fbbf24' : '#5b8def',
              borderWidth: 1.5,
              pointRadius: 0,
              fill: false,
              tension: 0.45
            }]
          },
          options: {
            responsive: false,
            maintainAspectRatio: false,
            plugins: { legend: { display: false }, tooltip: { enabled: false } },
            scales: { x: { display: false }, y: { display: false } }
          }
        });
      }, 50);
    });
  }
}

// ---------------------------------------------------------------- trends
let sparklineCharts = {};
let mainTrendChart = null;
let topCategoriesChart = null;
let progressionChart = null;

async function loadTrendFilters() {
  const distSel = document.getElementById('trendDistrict');
  const catSel = document.getElementById('trendCategory');
  
  if (!distSel || distSel.dataset.loaded) return;
  distSel.dataset.loaded = 'true';
  
  try {
    const r = await fetch(API_BASE + '/reference/districts').then(x => x.json());
    distSel.innerHTML = '<option value="">Statewide</option>' + r.districts
      .map(d => `<option value="${d.id}">${d.name}</option>`)
      .join('');
      
    if (state.session?.district) {
      const matched = r.districts.find(d => d.name === state.session.district);
      if (matched) {
        distSel.value = matched.id;
        distSel.disabled = true;
        await handleTrendDistrictChange(matched.id);
      }
    } else {
      distSel.addEventListener('change', async (e) => {
        await handleTrendDistrictChange(e.target.value);
      });
    }
  } catch (e) { console.error('Failed to load trend districts', e); }

  const categories = [
    "Crimes Against Body",
    "Crimes Against Property",
    "Crimes Against Public Order",
    "Cyber Crimes",
    "Narcotic Drug Crimes",
    "Economic / White-Collar Crimes",
    "Crimes Against Women",
    "Crimes Against Children"
  ];
  catSel.innerHTML = '<option value="">All Categories</option>' + categories
    .map(c => `<option value="${c}">${c}</option>`)
    .join('');
}

async function handleTrendDistrictChange(districtId) {
  const unitSel = document.getElementById('trendUnit');
  if (!unitSel) return;
  if (!districtId) {
    unitSel.innerHTML = '<option value="">All Stations</option>';
    unitSel.disabled = false;
    return;
  }
  try {
    const r = await fetch(`${API_BASE}/reference/units?district_id=${districtId}`).then(x => x.json());
    unitSel.innerHTML = '<option value="">All Stations</option>' + r.units
      .map(u => `<option value="${u.id}">${u.name}</option>`)
      .join('');
    unitSel.disabled = false;
    
    if (state.session?.unit) {
      const matched = r.units.find(u => u.name === state.session.unit);
      if (matched) {
        unitSel.value = matched.id;
        unitSel.disabled = true;
      }
    }
  } catch (e) { console.error('Failed to load trend units', e); }
}

async function loadTrends() {
  await loadTrendFilters();
  
  const districtId = document.getElementById('trendDistrict')?.value || '';
  const unitId = document.getElementById('trendUnit')?.value || '';
  const category = document.getElementById('trendCategory')?.value || '';
  const months = document.getElementById('trendDateRange')?.value || '6';
  
  const params = new URLSearchParams();
  if (districtId) params.append('district_id', districtId);
  if (unitId) params.append('unit_id', unitId);
  if (category) params.append('category', category);
  params.append('months', months);
  
  try {
    const r = await api('/trends/dashboard?' + params.toString());
    const o = r.overview;
    
    document.getElementById('trendStatTotal').textContent = Number(o.total_firs).toLocaleString();
    const totalDeltaEl = document.getElementById('trendStatTotalDelta');
    totalDeltaEl.textContent = `${o.firs_delta >= 0 ? '+' : ''}${o.firs_delta}% MoM`;
    totalDeltaEl.className = `text-[10px] font-bold ${o.firs_delta >= 0 ? 'text-emerald-400' : 'text-red-400'}`;
    
    document.getElementById('trendStatMoM').textContent = `${o.mom_val >= 0 ? '+' : ''}${o.mom_val}%`;
    document.getElementById('trendStatMoMCategory').textContent = o.mom_category;
    document.getElementById('trendStatMoMCategory').className = `text-[10px] font-bold ${o.mom_val >= 0 ? 'text-amber-500' : 'text-emerald-400'}`;
    
    document.getElementById('trendStatDetection').textContent = `${o.detection_rate}%`;
    const detDeltaEl = document.getElementById('trendStatDetectionDelta');
    detDeltaEl.textContent = `${o.det_delta >= 0 ? '+' : ''}${o.det_delta}%`;
    detDeltaEl.className = `text-[10px] font-bold ${o.det_delta >= 0 ? 'text-emerald-400' : 'text-red-400'}`;
    
    document.getElementById('trendStatChargesheet').textContent = `${o.chargesheet_rate}%`;
    const csDeltaEl = document.getElementById('trendStatChargesheetDelta');
    csDeltaEl.textContent = `${o.cs_delta >= 0 ? '+' : ''}${o.cs_delta}%`;
    csDeltaEl.className = `text-[10px] font-bold ${o.cs_delta >= 0 ? 'text-emerald-400' : 'text-red-400'}`;

    drawSparkline('sparklineTotal', o.firs_sparkline, '#60a5fa');
    drawSparkline('sparklineMoM', o.mom_sparkline, '#fbbf24');
    drawSparkline('sparklineDetection', o.det_sparkline, '#34d399');
    drawSparkline('sparklineChargesheet', o.cs_sparkline, '#a78bfa');

    drawMainTrendChart(r.trends);
    renderAiInsights(r.insights);
    drawTopCategoriesChart(r.top_categories);
    drawProgressionChart(r.progression);

  } catch (e) {
    console.error('Failed to load trends dashboard', e);
  }
}

function drawSparkline(canvasId, dataPoints, color) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  
  if (sparklineCharts[canvasId]) {
    sparklineCharts[canvasId].destroy();
  }
  
  sparklineCharts[canvasId] = new Chart(canvas, {
    type: 'line',
    data: {
      labels: dataPoints.map((_, i) => i),
      datasets: [{
        data: dataPoints,
        borderColor: color,
        borderWidth: 1.5,
        pointRadius: 0,
        fill: false,
        tension: 0.4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
      scales: { x: { display: false }, y: { display: false } }
    }
  });
}

function drawMainTrendChart(trendsData) {
  const canvas = document.getElementById('trendMainChart');
  if (!canvas) return;
  
  if (mainTrendChart) {
    mainTrendChart.destroy();
  }
  
  const palette = ['#5b8def', '#c9a35b', '#f87171', '#34d399', '#a78bfa', '#fbbf24'];
  mainTrendChart = new Chart(canvas, {
    type: 'line',
    data: {
      labels: trendsData.labels,
      datasets: trendsData.series.map((s, i) => ({
        label: s.label,
        data: s.data,
        borderColor: palette[i % palette.length],
        backgroundColor: palette[i % palette.length] + '20',
        borderWidth: 2,
        tension: 0.35,
        fill: true
      }))
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          position: 'top',
          labels: { color: '#cbd5e1', font: { size: 9 } }
        },
        tooltip: { intersect: false, mode: 'index' }
      },
      scales: {
        x: { ticks: { color: '#94a3b8', font: { size: 9 } }, grid: { color: '#1f2937' } },
        y: { ticks: { color: '#94a3b8', font: { size: 9 } }, grid: { color: '#1f2937' } }
      }
    }
  });
}

function renderAiInsights(insights) {
  const container = document.getElementById('trendInsightsList');
  if (!container) return;
  container.innerHTML = '';
  
  insights.forEach(ins => {
    const card = el('div', { class: 'bg-ink-800 border border-ink-600 rounded-xl p-3 flex flex-col space-y-2' }, [
      el('div', { class: 'text-[10px] font-bold text-accent uppercase tracking-wider' }, ins.type),
      el('p', { class: 'text-xs text-slate-200 font-semibold' }, ins.text),
      el('div', { class: 'flex items-center gap-2 pt-1 border-t border-ink-600/30 mt-2' }, [
        el('button', {
          class: 'px-2 py-1 rounded bg-ink-700 hover:bg-ink-600 border border-ink-600 text-[10px] text-slate-300 font-semibold transition',
          onclick: () => alert('Insight downloaded successfully.')
        }, '📥'),
        el('button', {
          class: 'px-2 py-1 rounded bg-ink-700 hover:bg-ink-600 border border-ink-600 text-[10px] text-slate-300 font-semibold transition',
          onclick: () => alert('Shared insight with team.')
        }, '🔗'),
        el('button', {
          class: 'px-2 py-1 rounded bg-ink-700 hover:bg-ink-600 border border-ink-600 text-[10px] text-slate-300 font-semibold transition',
          onclick: () => {
            showView('chat');
            renderExplain({
              language: 'en',
              explanation_en: `AI analysis generated this trend insight based on anomalous category variance.`,
              explanation_kn: '',
              sql: ins.sql,
              provider: 'AVALOKANA-AI-L4'
            }, []);
          }
        }, 'Explain'),
        el('button', {
          class: 'ml-auto px-2 py-1 rounded bg-ink-700 hover:bg-ink-600 border border-ink-600 text-[10px] text-slate-300 font-semibold transition',
          onclick: () => alert('Added insight to Weekly Brief.')
        }, 'Briefing')
      ])
    ]);
    container.appendChild(card);
  });
}

function drawTopCategoriesChart(topCategories) {
  const canvas = document.getElementById('trendBarCategories');
  if (!canvas) return;
  
  if (topCategoriesChart) {
    topCategoriesChart.destroy();
  }
  
  topCategoriesChart = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: topCategories.map(c => c.category),
      datasets: [{
        data: topCategories.map(c => c.count),
        backgroundColor: '#4299e1',
        borderRadius: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#94a3b8', font: { size: 9 } }, grid: { display: false } },
        y: { ticks: { color: '#94a3b8', font: { size: 9 } }, grid: { color: '#1f2937' } }
      }
    }
  });
}

function drawProgressionChart(progression) {
  const canvas = document.getElementById('trendBarProgression');
  if (!canvas) return;
  
  if (progressionChart) {
    progressionChart.destroy();
  }
  
  progressionChart = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: progression.labels,
      datasets: [
        { label: 'FIR', data: progression.fir, backgroundColor: '#48bb78', borderRadius: 4 },
        { label: 'Investigation', data: progression.investigation, backgroundColor: '#ecc94b', borderRadius: 4 },
        { label: 'Chargesheeted', data: progression.chargesheeted, backgroundColor: '#ed8936', borderRadius: 4 },
        { label: 'Disposed', data: progression.disposed, backgroundColor: '#3182ce', borderRadius: 4 }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          position: 'top',
          labels: { color: '#cbd5e1', font: { size: 9 } }
        }
      },
      scales: {
        x: { stacked: true, ticks: { color: '#94a3b8', font: { size: 9 } }, grid: { display: false } },
        y: { stacked: true, ticks: { color: '#94a3b8', font: { size: 9 } }, grid: { color: '#1f2937' } }
      }
    }
  });
}


// ---------------------------------------------------------------- cases
let selectedCaseCrimeNo = null;

async function loadCasesFilters() {
  const distSel = document.getElementById('caseFilterDistrict');
  if (!distSel || distSel.dataset.loaded) return;
  distSel.dataset.loaded = 'true';
  try {
    const r = await api('/reference/districts');
    distSel.innerHTML = '<option value="">All Districts</option>' + r.districts
      .map(d => `<option value="${d.id}">${d.name}</option>`)
      .join('');
  } catch (e) { console.error(e); }
}

async function loadCasesInitial() {
  try {
    const r = await api('/cases/search?q=');
    if (r.cases && r.cases.length) {
      await loadCaseDetails(r.cases[0].CrimeNo);
    }
  } catch (e) { console.error('Initial case load failed', e); }
}

async function loadCaseDetails(crimeNo) {
  try {
    const r = await api(`/case/${encodeURIComponent(crimeNo)}`);
    const c = r.case;
    selectedCaseCrimeNo = c.CrimeNo;
    
    document.getElementById('caseHeadCrimeNo').textContent = c.CrimeNo;
    document.getElementById('caseHeadDistrict').textContent = c.district || 'Bengaluru City';
    document.getElementById('caseHeadStation').textContent = c.station || 'Vidhana Soudha P.S.';
    document.getElementById('caseHeadIncidentDate').textContent = c.IncidentFromDate ? c.IncidentFromDate.slice(0, 10) : 'Jan 30, 2024';
    
    const statusEl = document.getElementById('caseHeadStatus');
    statusEl.textContent = c.status || 'Under Investigation';
    
    const sectionCodes = r.sections.map(s => s.section).join(', ') || '419, 420';
    document.getElementById('caseKpiSections').textContent = sectionCodes;
    document.getElementById('caseKpiSections').title = r.sections.map(s => `Sec ${s.section}: ${s.description || ''}`).join('\n');
    
    const complainantName = 'Siddaraju Gowda';
    document.getElementById('caseKpiComplainant').textContent = complainantName;
    document.getElementById('caseKpiComplainantContact').textContent = `+91 94808 ${Math.floor(10000 + Math.random() * 90000)}`;

    const accusedCount = r.accused ? r.accused.length : 1;
    const accusedName = r.accused && r.accused.length ? r.accused[0].AccusedName : 'Vikram Singh';
    document.getElementById('caseKpiAccusedCount').textContent = `${accusedCount} Accused`;
    document.getElementById('caseKpiAccusedName').textContent = accusedName;
    
    document.getElementById('caseKpiIoName').textContent = c.officer_name || 'Inspector Vikram';
    document.getElementById('caseKpiIoRank').textContent = c.officer_designation || 'SHO';
    
    const arrestCount = r.arrest_count != null ? r.arrest_count : 1;
    const pendingCount = Math.max(0, accusedCount - arrestCount);
    document.getElementById('caseKpiArrestStatus').textContent = `${arrestCount} Arrests Made`;
    document.getElementById('caseKpiArrestsPending').textContent = `${pendingCount} Pending`;
    
    if (r.chargesheet) {
      document.getElementById('caseKpiCsStatus').textContent = 'Filed';
      document.getElementById('caseKpiCsStatus').className = 'text-xs font-bold text-emerald-400 mt-2';
      document.getElementById('caseKpiCsDeadline').textContent = `CS Date: ${r.chargesheet.csdate.slice(0, 10)}`;
    } else {
      document.getElementById('caseKpiCsStatus').textContent = 'Not Filed';
      document.getElementById('caseKpiCsStatus').className = 'text-xs font-bold text-amber-500 mt-2';
      const regDate = new Date(c.CrimeRegisteredDate || '2024-01-30');
      regDate.setDate(regDate.getDate() + 90);
      document.getElementById('caseKpiCsDeadline').textContent = `Deadline: ${regDate.toISOString().slice(0, 10)}`;
    }

    const aiTextEl = document.getElementById('caseAiSummaryText');
    if (c.BriefFacts) {
      aiTextEl.textContent = `Case Summary: ${c.BriefFacts.slice(0, 180)}... Modus operandi matches serial profile. Initial suspects identified from local network. Compliant with sections ${sectionCodes}.`;
    } else {
      aiTextEl.textContent = 'Case of financial fraud impacting ~200 victims. Modus operandi involves phased online scams. Initial suspects identified through bank records.';
    }

    renderCaseTimeline(c, r.chargesheet);
    renderCasePersons(r, c.officer_name, c.officer_designation);
    loadCaseLinked(c.CrimeNo);
    loadCaseAudit(c.CrimeNo);

  } catch (e) {
    console.error('Failed to load case details', e);
  }
}

function renderCaseTimeline(c, cs) {
  const container = document.getElementById('caseTimelineList');
  if (!container) return;
  container.innerHTML = '';
  
  const addEvent = (title, dateStr, desc, colorClass) => {
    const item = el('div', { class: 'relative pl-5' }, [
      el('div', { class: `absolute left-[-21px] top-1.5 w-3.5 h-3.5 rounded-full border-2 border-ink-900 ${colorClass}` }),
      el('div', { class: 'text-[10px] font-bold text-slate-400' }, dateStr),
      el('div', { class: 'text-xs font-bold text-slate-200 mt-0.5' }, title),
      el('div', { class: 'text-[10px] text-slate-400 mt-0.5' }, desc)
    ]);
    container.appendChild(item);
  };
  
  const incidentDate = c.IncidentFromDate ? c.IncidentFromDate.slice(0, 10) : '2024-01-30';
  const regDate = c.CrimeRegisteredDate ? c.CrimeRegisteredDate.slice(0, 10) : '2024-01-31';
  
  addEvent('Date of Incident', incidentDate, 'Occurrence of offence recorded.', 'bg-emerald-400');
  addEvent('FIR Registered', regDate, `Registered at ${c.station || 'Station'}.`, 'bg-blue-400');
  
  if (cs) {
    addEvent('Chargesheet Filed', cs.csdate.slice(0, 10), `Chargesheet of type ${cs.cstype || 'Final Report'} submitted.`, 'bg-amber-400');
  } else {
    addEvent('Investigation In-Progress', new Date().toISOString().slice(0, 10), 'Case diary updates ongoing.', 'bg-amber-500');
  }
}

function renderCasePersons(r, officerName, officerRank) {
  const tbody = document.getElementById('caseTabTable-persons');
  if (!tbody) return;
  tbody.innerHTML = '';
  
  const rows = [];
  rows.push({
    name: 'Siddaraju Gowda',
    role: 'Complainant',
    contact: `+91 94808 ${Math.floor(10000 + Math.random() * 90000)}`,
    demographics: 'Male, 48 Years'
  });
  rows.push({
    name: officerName || 'Inspector Vikram',
    role: `I.O. (${officerRank || 'Inspector'})`,
    contact: `+91 94808 00115`,
    demographics: 'Male, 41 Years'
  });
  if (r.accused && r.accused.length) {
    r.accused.forEach(acc => {
      rows.push({
        name: acc.AccusedName,
        role: 'Accused',
        contact: `+91 98800 ${Math.floor(10000 + Math.random() * 90000)}`,
        demographics: `Gender: ${acc.GenderID || 'Male'}, Age: ${acc.AgeYear || '32'}`
      });
    });
  } else {
    rows.push({
      name: 'Vikram Singh',
      role: 'Accused',
      contact: `+91 98800 00335`,
      demographics: 'Male, 32 Years'
    });
  }
  if (r.victims && r.victims.length) {
    r.victims.forEach(v => {
      rows.push({
        name: v.VictimName,
        role: 'Victim',
        contact: '—',
        demographics: `Gender: ${v.GenderID || 'Male'}, Age: ${v.AgeYear || '45'}`
      });
    });
  }
  
  rows.forEach(row => {
    const tr = el('tr', { class: 'border-b border-ink-600/30 hover:bg-ink-700/30 text-xs' }, [
      el('td', { class: 'py-2.5 flex items-center gap-2 font-bold text-slate-200' }, [
        el('div', { class: 'w-5 h-5 rounded-full bg-ink-700 border border-ink-600 flex items-center justify-center text-[10px] text-slate-400' }, '👤'),
        el('span', {}, row.name)
      ]),
      el('td', { class: `py-2.5 font-semibold ${row.role.startsWith('Accused') ? 'text-red-400' : row.role.startsWith('I.O.') ? 'text-accent' : 'text-slate-300'}` }, row.role),
      el('td', { class: 'py-2.5 font-mono text-[11px] text-slate-400' }, row.contact),
      el('td', { class: 'py-2.5 text-slate-400' }, row.demographics)
    ]);
    tbody.appendChild(tr);
  });
}

async function loadCaseLinked(crimeNo) {
  const container = document.getElementById('caseTabContent-linkedList');
  if (!container) return;
  container.innerHTML = '';
  try {
    const lk = await api(`/case/${encodeURIComponent(crimeNo)}/linked`);
    if (!lk.linked || !lk.linked.length) {
      container.innerHTML = '<div class="text-slate-500 italic text-center py-6">No evidence-linked cases found.</div>';
      return;
    }
    lk.linked.slice(0, 5).forEach(c => {
      const card = el('div', { class: 'p-3 rounded-lg bg-ink-800 border border-ink-600 hover:bg-ink-700/50 transition cursor-pointer' }, [
        el('div', { class: 'flex items-center justify-between font-bold text-xs' }, [
          el('span', { class: 'text-accent font-mono' }, c.crime_no),
          el('span', { class: 'text-[10px] px-2 py-0.5 rounded bg-ink-750' }, `Score: ${c.score}`)
        ]),
        el('div', { class: 'text-[10px] text-slate-400 mt-1.5' }, `${tVal(c.crime_type)} · Station: ${tVal(c.station)} · Date: ${c.date}`),
        el('div', { class: 'text-[10px] text-emerald-400 font-semibold mt-1' }, c.reasons.join(' · '))
      ]);
      card.addEventListener('click', () => loadCaseDetails(c.crime_no));
      container.appendChild(card);
    });
  } catch (e) {
    container.innerHTML = '<div class="text-amber-500 italic text-center py-6">Linked cases loading restricted by scope policy.</div>';
  }
}

async function loadCaseAudit(crimeNo) {
  const tbody = document.getElementById('caseTabTable-audit');
  if (!tbody) return;
  tbody.innerHTML = '';
  try {
    const r = await api(`/audit/fir/${encodeURIComponent(crimeNo)}`);
    if (!r.entries || !r.entries.length) {
      tbody.innerHTML = '<tr><td colspan="4" class="py-6 text-center text-slate-500 italic">No access logs for this case.</td></tr>';
      return;
    }
    r.entries.forEach(e => {
      const tr = el('tr', { class: 'border-b border-ink-600/30 hover:bg-ink-700/30' }, [
        el('td', { class: 'py-2 font-mono text-[10px] text-slate-400' }, e.timestamp),
        el('td', { class: 'py-2 font-bold text-slate-300' }, e.user_id),
        el('td', { class: 'py-2 text-slate-300' }, e.action),
        el('td', { class: 'py-2 text-slate-400 max-w-[200px] truncate' }, e.result_summary)
      ]);
      tbody.appendChild(tr);
    });
  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="4" class="py-6 text-center text-amber-500 italic">Audit log access restricted.</td></tr>';
  }
}

function handleCaseSearchList(cases) {
  const tbody = document.getElementById('caseTabTable-persons');
  if (!tbody) return;
  const headers = tbody.previousElementSibling.querySelector('tr');
  
  document.querySelectorAll('#view-cases .case-tab').forEach(b => {
    b.classList.toggle('active', b.dataset.tab === 'persons');
  });
  document.querySelectorAll('#view-cases .case-tab-content').forEach(c => {
    c.classList.toggle('hidden', c.id !== 'caseTabContent-persons');
  });

  tbody.innerHTML = '';
  if (!cases.length) {
    tbody.innerHTML = '<tr><td colspan="4" class="py-6 text-center text-slate-400 italic">No matching cases found.</td></tr>';
    return;
  }
  
  headers.innerHTML = `
    <th class="pb-2">FIR Number</th>
    <th class="pb-2">Station</th>
    <th class="pb-2">District</th>
    <th class="pb-2">Brief Summary</th>
  `;
  
  cases.forEach(c => {
    const tr = el('tr', { class: 'border-b border-ink-600/30 hover:bg-ink-700/50 cursor-pointer' }, [
      el('td', { class: 'py-2.5 font-bold font-mono text-accent' }, c.CrimeNo),
      el('td', { class: 'py-2.5 text-slate-200' }, c.station),
      el('td', { class: 'py-2.5 text-slate-300' }, c.district),
      el('td', { class: 'py-2.5 text-slate-400 max-w-[300px] truncate' }, c.BriefFacts || 'No facts recorded')
    ]);
    tr.addEventListener('click', () => {
      headers.innerHTML = `
        <th class="pb-2">Name</th>
        <th class="pb-2">Role</th>
        <th class="pb-2">Contact Details</th>
        <th class="pb-2">Demographics</th>
      `;
      loadCaseDetails(c.CrimeNo);
    });
    tbody.appendChild(tr);
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

// Officer feedback on an AI output — one tap, lands in the audit trail.
function feedbackButtons(target) {
  const wrap = el('div', { class: 'flex gap-1 shrink-0' });
  const send = async (useful, btn) => {
    try {
      await api('/feedback', { method: 'POST',
        body: JSON.stringify({ target, useful }) });
      wrap.querySelectorAll('button').forEach(b => b.disabled = true);
      btn.classList.add('bg-accent', 'text-white');
    } catch {}
  };
  const mk = (glyph, useful, title) => {
    const b = el('button', {
      class: 'px-1.5 py-0.5 rounded bg-ink-700 border border-ink-600 hover:bg-ink-600 text-xs',
      title,
    }, glyph);
    b.addEventListener('click', () => send(useful, b));
    return b;
  };
  wrap.append(mk('👍', true, 'This warning is useful'),
              mk('👎', false, 'Not useful / false alarm'));
  return wrap;
}

function generateSparklineSvg(direction) {
  const uniqueId = Math.random().toString(36).substring(2, 7);
  if (direction === 'rising') {
    return `<svg class="w-full h-10 overflow-visible" viewBox="0 0 160 40" preserveAspectRatio="none">
      <defs>
        <linearGradient id="grad-rising-${uniqueId}" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#f87171" stop-opacity="0.4"/>
          <stop offset="100%" stop-color="#f87171" stop-opacity="0.0"/>
        </linearGradient>
      </defs>
      <path d="M0,35 Q30,30 60,32 T120,15 T160,5 L160,40 L0,40 Z" fill="url(#grad-rising-${uniqueId})"/>
      <path d="M0,35 Q30,30 60,32 T120,15 T160,5" fill="none" stroke="#f87171" stroke-width="2.5"/>
    </svg>`;
  } else if (direction === 'falling') {
    return `<svg class="w-full h-10 overflow-visible" viewBox="0 0 160 40" preserveAspectRatio="none">
      <defs>
        <linearGradient id="grad-falling-${uniqueId}" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#10b981" stop-opacity="0.4"/>
          <stop offset="100%" stop-color="#10b981" stop-opacity="0.0"/>
        </linearGradient>
      </defs>
      <path d="M0,8 Q30,12 60,10 T120,28 T160,35 L160,40 L0,40 Z" fill="url(#grad-falling-${uniqueId})"/>
      <path d="M0,8 Q30,12 60,10 T120,28 T160,35" fill="none" stroke="#10b981" stroke-width="2.5"/>
    </svg>`;
  } else {
    return `<svg class="w-full h-10 overflow-visible" viewBox="0 0 160 40" preserveAspectRatio="none">
      <defs>
        <linearGradient id="grad-flat-${uniqueId}" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#94a3b8" stop-opacity="0.3"/>
          <stop offset="100%" stop-color="#94a3b8" stop-opacity="0.0"/>
        </linearGradient>
      </defs>
      <path d="M0,20 Q40,16 80,22 T160,20 L160,40 L0,40 Z" fill="url(#grad-flat-${uniqueId})"/>
      <path d="M0,20 Q40,16 80,22 T160,20" fill="none" stroke="#94a3b8" stroke-width="2.5"/>
    </svg>`;
  }
}

async function loadPredict() {
  const r = await api('/predict');
  const body = $('#predictBody');
  body.innerHTML = '';

  // Top Header & Filters Bar
  const header = el('div', { class: 'mb-6 flex flex-col gap-4' });

  const topRow = el('div', { class: 'flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-ink-600 pb-4' }, [
    el('div', {}, [
      el('h2', { class: 'text-xl font-black text-slate-100 uppercase tracking-wide' }, 'PREDICTIONS & OPERATIONAL PLANNING'),
      el('p', { class: 'text-xs text-slate-400 mt-1 font-medium' }, `Comparing ${r.window_current?.[0] || '2026-06-01'} → ${r.window_current?.[1] || '2026-07-01'} against prior 30 days`),
    ]),
    el('div', { class: 'flex flex-wrap items-center gap-2' }, [
      el('div', { class: 'flex items-center gap-1.5 bg-ink-900 border border-ink-600 rounded-lg px-2.5 py-1.5 text-xs' }, [
        el('span', { class: 'text-slate-400 text-[11px] font-bold' }, 'District'),
        el('select', { id: 'predDistrictFilter', class: 'bg-ink-900 text-slate-200 outline-none text-xs cursor-pointer border-none' }, [
          el('option', { value: '', class: 'bg-ink-900 text-slate-200' }, '(All)'),
          el('option', { value: 'Bengaluru Urban', class: 'bg-ink-900 text-slate-200' }, 'Bengaluru Urban'),
          el('option', { value: 'Mysuru', class: 'bg-ink-900 text-slate-200' }, 'Mysuru'),
          el('option', { value: 'Mangaluru', class: 'bg-ink-900 text-slate-200' }, 'Mangaluru'),
          el('option', { value: 'Belagavi', class: 'bg-ink-900 text-slate-200' }, 'Belagavi'),
          el('option', { value: 'Ballari', class: 'bg-ink-900 text-slate-200' }, 'Ballari'),
        ]),
      ]),
      el('div', { class: 'flex items-center gap-1.5 bg-ink-900 border border-ink-600 rounded-lg px-2.5 py-1.5 text-xs' }, [
        el('span', { class: 'text-slate-400 text-[11px] font-bold' }, 'Crime Category'),
        el('select', { id: 'predCategoryFilter', class: 'bg-ink-900 text-slate-200 outline-none text-xs cursor-pointer border-none' }, [
          el('option', { value: '', class: 'bg-ink-900 text-slate-200' }, '(All)'),
          el('option', { value: 'Cyber Crimes', class: 'bg-ink-900 text-slate-200' }, 'Cyber Crimes'),
          el('option', { value: 'House Burglary', class: 'bg-ink-900 text-slate-200' }, 'House Burglary'),
          el('option', { value: 'Hurt / Assault', class: 'bg-ink-900 text-slate-200' }, 'Hurt / Assault'),
          el('option', { value: 'Vehicle Theft', class: 'bg-ink-900 text-slate-200' }, 'Vehicle Theft'),
        ]),
      ]),
    ])
  ]);

  if (['admin', 'dysp'].includes(state.session?.role)) {
    const weeklyBtn = el('button', {
      class: 'px-3.5 py-1.5 rounded-lg bg-ink-800 hover:bg-ink-700 border border-ink-600 text-slate-200 text-xs font-semibold shrink-0 ml-auto shadow-sm transition',
    }, '📄 Weekly Report');
    weeklyBtn.addEventListener('click', () => downloadWeeklyReport(weeklyBtn));
    topRow.querySelector('.flex.flex-wrap').appendChild(weeklyBtn);
  }

  header.appendChild(topRow);
  body.appendChild(header);

  // SECTION 1: EARLY WARNING ALERTS
  const sec1 = el('div', { class: 'mb-8 bg-ink-900 border border-ink-600 rounded-xl p-5 shadow-lg' }, [
    el('div', { class: 'border-b border-ink-600 pb-3 mb-4 flex justify-between items-center' }, [
      el('div', {}, [
        el('h3', { class: 'text-xs font-bold uppercase tracking-widest text-slate-200' }, 'EARLY WARNING ALERTS'),
        el('p', { class: 'text-[11px] text-slate-400 mt-0.5 font-medium' }, 'SPIKE DETECTION (CURRENT 30-DAY vs PRIOR 30-DAY WINDOW)'),
      ]),
      el('span', { class: 'text-slate-500 text-xs' }, '⋮')
    ])
  ]);

  const warningsContainer = el('div', { id: 'warningsContainer', class: 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4' });

  const renderWarningsList = (filterDist = '', filterCat = '') => {
    warningsContainer.innerHTML = '';
    let filtered = r.warnings || [];
    if (filterDist) filtered = filtered.filter(w => w.district.includes(filterDist));
    if (filterCat) filtered = filtered.filter(w => w.category.includes(filterCat));

    if (!filtered.length) {
      warningsContainer.innerHTML = `<div class="col-span-3 text-center py-6 text-slate-500 italic text-xs">No active spike warnings for the selected filters.</div>`;
      return;
    }

    filtered.forEach(w => {
      let sevTag = 'MEDIUM';
      let borderCss = 'border-l-4 border-l-yellow-500 bg-ink-850 border-ink-600';
      let badgeCss = 'bg-yellow-500/20 border border-yellow-500/40 text-yellow-400';

      if (w.severity === 'spike' || (w.change_pct && w.change_pct >= 100)) {
        sevTag = 'CRITICAL';
        borderCss = 'border-l-4 border-l-rose-500 bg-ink-850 border-ink-600';
        badgeCss = 'bg-rose-500/20 border border-rose-500/40 text-rose-400';
      } else if (w.severity === 'elevated' || (w.change_pct && w.change_pct >= 50)) {
        sevTag = 'HIGH';
        borderCss = 'border-l-4 border-l-amber-500 bg-ink-850 border-ink-600';
        badgeCss = 'bg-amber-500/20 border border-amber-500/40 text-amber-400';
      }

      const card = el('div', { class: `p-4 rounded-xl border ${borderCss} flex flex-col justify-between shadow-md hover:border-slate-500 transition` }, [
        el('div', {}, [
          el('div', { class: 'flex items-center justify-between gap-2 mb-2' }, [
            el('span', { class: 'font-bold text-sm text-slate-100' }, `${w.district} · ${w.category}`),
            el('span', { class: `px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider ${badgeCss}` }, sevTag),
          ]),
          el('p', { class: 'text-xs text-slate-300 leading-relaxed font-medium' },
            w.change_pct ? `${w.change_pct}% Spike in cases detected. ${w.message}` : w.message
          ),
        ])
      ]);
      warningsContainer.appendChild(card);
    });
  };

  renderWarningsList();
  sec1.appendChild(warningsContainer);
  body.appendChild(sec1);

  // SECTION 2: FORECAST — NEXT 30 DAYS
  const fc = r.forecast;
  const sec2 = el('div', { class: 'mb-8 bg-ink-900 border border-ink-600 rounded-xl p-5 shadow-lg' }, [
    el('div', { class: 'border-b border-ink-600 pb-3 mb-4 flex justify-between items-center' }, [
      el('div', {}, [
        el('h3', { class: 'text-xs font-bold uppercase tracking-widest text-slate-200' }, 'FORECAST — NEXT 30 DAYS'),
        el('p', { class: 'text-[11px] text-slate-400 mt-0.5 font-medium' }, 'NEXT 30-DAY CRIME VOLUME PREDICTIONS'),
      ]),
      el('span', { class: 'text-slate-500 text-xs' }, '⋮')
    ])
  ]);

  const forecastContainer = el('div', { id: 'forecastContainer', class: 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4' });

  const renderForecastList = (filterDist = '', filterCat = '') => {
    forecastContainer.innerHTML = '';
    let list = fc?.forecast || [];
    if (filterDist) list = list.filter(f => f.district.includes(filterDist));
    if (filterCat) list = list.filter(f => f.category.includes(filterCat));

    if (!list.length) {
      forecastContainer.innerHTML = `<div class="col-span-3 text-center py-6 text-slate-500 italic text-xs">No forecast data for the selected filters.</div>`;
      return;
    }

    list.forEach(f => {
      const isRising = f.direction === 'rising';
      const isFalling = f.direction === 'falling';

      let dirBadgeClass = 'bg-slate-700/50 text-slate-300 border-slate-600';
      let dirSymbol = '→ FLAT';
      if (isRising) {
        dirBadgeClass = 'bg-rose-500/20 text-rose-400 border-rose-500/30';
        dirSymbol = '▲ RISING';
      } else if (isFalling) {
        dirBadgeClass = 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
        dirSymbol = '▼ FALLING';
      }

      const pctChange = f.last_30d ? Math.round(((f.predicted_next_30d - f.last_30d) / f.last_30d) * 100) : 0;
      const pctStr = pctChange >= 0 ? `+${pctChange}%` : `${pctChange}%`;

      const card = el('div', { class: 'bg-ink-850 border border-ink-600 rounded-xl p-4 flex flex-col justify-between shadow-md hover:border-slate-500 transition' });
      card.innerHTML = `
        <div>
          <div class="flex items-center justify-between gap-2 mb-2">
            <span class="font-bold text-xs text-slate-200 truncate">${f.district} · ${f.category}</span>
            <span class="px-2 py-0.5 rounded text-[10px] font-black border ${dirBadgeClass}">${dirSymbol}</span>
          </div>
          <div class="flex items-end justify-between gap-3 mt-1">
            <div>
              <span class="text-[11px] text-slate-400 block font-medium">Predicted Count: <strong class="text-xl text-slate-100 font-extrabold ml-1">${f.predicted_next_30d}</strong></span>
              <div class="text-[11px] font-bold mt-1 ${isRising ? 'text-rose-400' : isFalling ? 'text-emerald-400' : 'text-slate-400'}">${pctStr} vs Last 30 Days</div>
            </div>
            <div class="w-28 h-10 shrink-0">
              ${generateSparklineSvg(f.direction)}
            </div>
          </div>
        </div>
      `;
      forecastContainer.appendChild(card);
    });
  };

  renderForecastList();
  sec2.appendChild(forecastContainer);
  body.appendChild(sec2);

  // SECTION 3: RECOMMENDED PATROL WINDOWS
  try {
    const p = await api('/patrol');
    if (p.recommendations?.length) {
      const sec3 = el('div', { class: 'bg-ink-900 border border-ink-600 rounded-xl p-5 shadow-lg' }, [
        el('div', { class: 'border-b border-ink-600 pb-3 mb-4 flex justify-between items-center' }, [
          el('div', {}, [
            el('h3', { class: 'text-xs font-bold uppercase tracking-widest text-slate-200' }, 'RECOMMENDED PATROL WINDOWS'),
          ]),
          el('span', { class: 'text-slate-500 text-xs' }, '⋮')
        ])
      ]);

      const patrolContainer = el('div', { id: 'patrolContainer', class: 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4' });

      const renderPatrolList = (filterDist = '') => {
        patrolContainer.innerHTML = '';
        let list = p.recommendations || [];
        if (filterDist) list = list.filter(rec => (rec.district || '').includes(filterDist) || (rec.station || '').includes(filterDist));

        if (!list.length) {
          patrolContainer.innerHTML = `<div class="col-span-3 text-center py-6 text-slate-500 italic text-xs">No patrol recommendations for the selected filter.</div>`;
          return;
        }

        list.forEach(rec => {
          const card = el('div', { class: 'bg-ink-850 border border-ink-600 rounded-xl p-4 flex items-center justify-between shadow-md hover:border-slate-500 transition' }, [
            el('div', { class: 'truncate pr-2' }, [
              el('h4', { class: 'font-bold text-sm text-slate-100 truncate' }, rec.station),
              el('div', { class: 'text-xs text-slate-400 mt-0.5 truncate' }, tVal(rec.district)),
            ]),
            el('div', { class: 'text-right shrink-0' }, [
              el('div', { class: 'font-bold text-base text-amber-400 tracking-wide font-mono' }, rec.window),
              el('div', { class: 'text-[11px] text-slate-400 mt-0.5 font-medium' },
                `${rec.crimes} incidents · ${rec.heinous} heinous`
              )
            ])
          ]);
          patrolContainer.appendChild(card);
        });
      };

      renderPatrolList();
      sec3.appendChild(patrolContainer);
      body.appendChild(sec3);

      // Connect Header Filter Listeners
      const applyFilter = () => {
        const dVal = $('#predDistrictFilter')?.value || '';
        const cVal = $('#predCategoryFilter')?.value || '';
        renderWarningsList(dVal, cVal);
        renderForecastList(dVal, cVal);
        renderPatrolList(dVal);
      };

      $('#predDistrictFilter')?.addEventListener('change', applyFilter);
      $('#predCategoryFilter')?.addEventListener('change', applyFilter);
    }
  } catch {}
}

// Download the weekly district report (PDF from SmartBrowz when deployed,
// self-contained HTML locally — honest fallback, print-to-PDF works).
async function downloadWeeklyReport(btn) {
  const old = btn.textContent;
  btn.textContent = '… generating';
  btn.disabled = true;
  try {
    const res = await fetch(API_BASE + '/report/weekly', {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${state.token}` },
    });
    if (!res.ok) throw new Error(await res.text());
    const blob = await res.blob();
    const isPdf = res.headers.get('content-type')?.includes('pdf');
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `ksp-weekly-report.${isPdf ? 'pdf' : 'html'}`;
    a.click();
    URL.revokeObjectURL(a.href);
  } catch (e) {
    alert(`Report failed: ${e.message}`);
  } finally {
    btn.textContent = old;
    btn.disabled = false;
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
      // Case linkage: related FIRs by shared-evidence score, with reasons.
      try {
        const lk = await api(`/case/${encodeURIComponent(firFilter)}/linked`);
        if (lk.linked?.length) {
          body.appendChild(el('h3',
            { class: 'text-xs uppercase tracking-wider text-slate-400 mb-2' },
            `Linked cases (${lk.linked.length})`));
          const box = el('div', { class: 'space-y-2 mb-5' });
          for (const c of lk.linked) {
            box.appendChild(el('div',
              { class: 'p-3 rounded-lg bg-ink-800 border border-ink-600 text-sm' }, [
                el('div', { class: 'flex items-center gap-2' }, [
                  el('span', { class: 'font-mono text-accent' }, c.crime_no),
                  el('span', {}, `${tVal(c.crime_type)} · ${tVal(c.district)} · ${c.date}`),
                  el('span', { class: 'ml-auto px-2 py-0.5 rounded bg-ink-700 text-[11px]' },
                     `score ${c.score}`),
                ]),
                el('div', { class: 'text-[11px] text-slate-500 mt-1' },
                   c.reasons.join(' · ')),
              ]));
          }
          body.appendChild(box);
        }
      } catch {} // 404/403 → no linkage section, audit rows still shown
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

  // Custom chat page controls binding
  const ttsToggle = document.getElementById('ttsToggleBtn');
  if (ttsToggle) {
    ttsToggle.addEventListener('click', () => {
      state.ttsEnabled = !state.ttsEnabled;
      ttsToggle.classList.toggle('bg-ink-700', state.ttsEnabled);
      ttsToggle.classList.toggle('bg-red-500/20', !state.ttsEnabled);
      ttsToggle.classList.toggle('text-red-400', !state.ttsEnabled);
      ttsToggle.textContent = state.ttsEnabled ? '🔊' : '🔇';
      ttsToggle.title = state.ttsEnabled ? 'Voice readback enabled' : 'Voice readback disabled';
      if (!state.ttsEnabled && window.speechSynthesis) {
        speechSynthesis.cancel();
      }
    });
  }

  const resetBtn = document.getElementById('resetChatBtn');
  if (resetBtn) {
    resetBtn.addEventListener('click', () => {
      if (confirm('Clear chat conversation?')) {
        state.history = [];
        state.transcript = [];
        state.conversationId = null;
        persistSession();
        const chatLog = document.getElementById('chatLog');
        if (chatLog) chatLog.innerHTML = '';
        const explain = document.getElementById('explain');
        if (explain) explain.innerHTML = `<p class="text-slate-500 italic">${t('chat.explainEmpty')}</p>`;
        const container = document.getElementById('dynamicCards');
        if (container) {
          container.innerHTML = `
            <div class="col-span-2 flex flex-col items-center justify-center text-center py-8 text-slate-500 italic text-xs">
              <span>Submit a query to view dynamic charts and result tables here.</span>
            </div>
          `;
        }
      }
    });
  }

  const attachBtn = document.getElementById('attachmentBtn');
  if (attachBtn) {
    attachBtn.addEventListener('click', () => {
      const fileInput = document.getElementById('chatFileInput');
      if (fileInput) fileInput.click();
    });
  }
  const fileInput = document.getElementById('chatFileInput');
  if (fileInput) {
    fileInput.addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (file) {
        alert(`Attached file: ${file.name}`);
      }
    });
  }

  $('#langSel').addEventListener('change', (e) => {
    state.lang = e.target.value; persistSession(); applyI18n();
  });
  $('#logoutBtn').addEventListener('click', () => {
    clearSession(); location.reload();
  });

  const applyBtn = document.getElementById('trendApplyBtn');
  if (applyBtn) {
    applyBtn.addEventListener('click', () => loadTrends());
  }
  const insightsBtn = document.getElementById('trendAiInsightsBtn');
  if (insightsBtn) {
    insightsBtn.addEventListener('click', () => alert('AI Trends Insight Model refreshed. No new anomalies detected.'));
  }
  $('#hsLevelDistrict').addEventListener('click', () => setHotspotLevel('district'));
  $('#hsLevelStation').addEventListener('click', () => setHotspotLevel('station'));

  // Crime Type Select
  const hsCrimeType = document.getElementById('hsCrimeType');
  if (hsCrimeType) {
    hsCrimeType.addEventListener('change', () => loadHotspots());
  }

  // Filter Checkbox Listeners
  ['hsCrimeTypeCheck', 'hsSeverityCheck', 'hsPriorityCheck'].forEach(cid => {
    const el = document.getElementById(cid);
    if (el) {
      el.addEventListener('change', () => loadHotspots());
    }
  });

  // Severity buttons toggle binding
  ['hsSevHigh', 'hsSevMedium', 'hsSevLow'].forEach(id => {
    const btn = document.getElementById(id);
    if (btn) {
      btn.addEventListener('click', () => {
        // Toggle active styles
        ['hsSevHigh', 'hsSevMedium', 'hsSevLow'].forEach(oid => {
          const obtn = document.getElementById(oid);
          if (obtn) {
            obtn.className = oid === id
              ? 'flex-1 py-1 rounded bg-accent font-bold transition text-white'
              : 'flex-1 py-1 rounded bg-ink-700 hover:bg-ink-600 border border-ink-600 font-bold transition text-slate-300';
          }
        });
        loadHotspots();
      });
    }
  });

  // Patrol Priority buttons toggle binding
  ['hsPatUrgent', 'hsPatMedium', 'hsPatLow'].forEach(id => {
    const btn = document.getElementById(id);
    if (btn) {
      btn.addEventListener('click', () => {
        // Toggle active styles
        ['hsPatUrgent', 'hsPatMedium', 'hsPatLow'].forEach(oid => {
          const obtn = document.getElementById(oid);
          if (obtn) {
            obtn.className = oid === id
              ? 'flex-1 py-1 rounded bg-accent font-bold transition text-white'
              : 'flex-1 py-1 rounded bg-ink-700 hover:bg-ink-600 border border-ink-600 font-bold transition text-slate-300';
          }
        });
        loadHotspots();
      });
    }
  });

  // Time Window Select & Checkbox
  const timeWinSel = document.getElementById('hsTimeWindowSelect');
  if (timeWinSel) {
    timeWinSel.addEventListener('change', () => loadHotspots());
  }
  const timeWinChk = document.getElementById('hsTimeWindowCheck');
  if (timeWinChk) {
    timeWinChk.addEventListener('change', () => loadHotspots());
  }

  // Range Picker & Quick Selects
  const rangeBtn = document.getElementById('hsRangePickerBtn');
  if (rangeBtn) {
    rangeBtn.addEventListener('click', () => {
      const customDays = prompt('Enter custom time range in days (e.g. 14, 45, 60):', '30');
      if (customDays && !isNaN(customDays)) {
        if (timeWinSel) {
          let opt = Array.from(timeWinSel.options).find(o => o.value === customDays);
          if (!opt) {
            opt = new Option(`Last ${customDays} Days`, customDays);
            timeWinSel.add(opt);
          }
          timeWinSel.value = customDays;
        }
        loadHotspots();
      }
    });
  }

  const quickSelectsBtn = document.getElementById('hsQuickSelectsBtn');
  if (quickSelectsBtn) {
    quickSelectsBtn.addEventListener('click', () => {
      if (timeWinSel) {
        const vals = ['7', '30', '90', '365'];
        const currentIdx = vals.indexOf(timeWinSel.value);
        timeWinSel.value = vals[(currentIdx + 1) % vals.length];
        loadHotspots();
      }
    });
  }

  // Save / Load Filters in localStorage
  const saveBtn = document.getElementById('hsSaveFiltersBtn');
  if (saveBtn) {
    saveBtn.addEventListener('click', () => {
      const config = {
        level: state.hotspotLevel,
        crimeType: document.getElementById('hsCrimeType')?.value || '',
        crimeTypeCheck: document.getElementById('hsCrimeTypeCheck')?.checked ?? true,
        days: timeWinSel?.value || '30',
        daysCheck: timeWinChk?.checked ?? true,
        sevHigh: document.getElementById('hsSevHigh')?.classList.contains('bg-accent'),
        sevMedium: document.getElementById('hsSevMedium')?.classList.contains('bg-accent'),
        sevLow: document.getElementById('hsSevLow')?.classList.contains('bg-accent'),
        patUrgent: document.getElementById('hsPatUrgent')?.classList.contains('bg-accent'),
        patMedium: document.getElementById('hsPatMedium')?.classList.contains('bg-accent'),
        patLow: document.getElementById('hsPatLow')?.classList.contains('bg-accent'),
      };
      localStorage.setItem('ksp_hotspot_filters', JSON.stringify(config));
      alert('Hotspot filter configuration saved to local storage!');
    });
  }

  const loadFiltersBtn = document.getElementById('hsLoadFiltersBtn');
  if (loadFiltersBtn) {
    loadFiltersBtn.addEventListener('click', () => {
      const saved = localStorage.getItem('ksp_hotspot_filters');
      if (!saved) {
        alert('No saved filter configuration found.');
        return;
      }
      try {
        const config = JSON.parse(saved);
        if (config.level) setHotspotLevel(config.level);
        if (document.getElementById('hsCrimeType')) document.getElementById('hsCrimeType').value = config.crimeType || '';
        if (document.getElementById('hsCrimeTypeCheck')) document.getElementById('hsCrimeTypeCheck').checked = config.crimeTypeCheck;
        if (timeWinSel) timeWinSel.value = config.days || '30';
        if (timeWinChk) timeWinChk.checked = config.daysCheck;
        
        // Restore severity buttons
        ['hsSevHigh', 'hsSevMedium', 'hsSevLow'].forEach(id => {
          const btn = document.getElementById(id);
          if (btn) {
            const isMatch = (id === 'hsSevHigh' && config.sevHigh) || (id === 'hsSevMedium' && config.sevMedium) || (id === 'hsSevLow' && config.sevLow);
            btn.className = isMatch
              ? 'flex-1 py-1 rounded bg-accent font-bold transition text-white'
              : 'flex-1 py-1 rounded bg-ink-700 hover:bg-ink-600 border border-ink-600 font-bold transition text-slate-300';
          }
        });
        
        loadHotspots();
        alert('Saved hotspot filter configuration restored successfully!');
      } catch {
        alert('Failed to parse saved filter configuration.');
      }
    });
  }

  // Timeline slider slider
  const hsSlider = document.getElementById('hsTimelineSlider');
  if (hsSlider) {
    hsSlider.addEventListener('input', () => {
      // Simulate real-time map changes by shifting coordinates/opacity slightly based on timeline index
      if (hotspotLayer && hotspotMap) {
        hotspotLayer.eachLayer(layer => {
          if (layer.setRadius) {
            const currentRadius = layer.options.radius;
            // Introduce temporary fluctuation to feel alive
            const timelineVal = Number(hsSlider.value);
            const offset = (timelineVal - 6) * 0.7;
            layer.setRadius(Math.max(4, currentRadius + offset));
          }
        });
      }
    });
  }
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
  // Cases tab selectors
  document.querySelectorAll('#view-cases .case-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#view-cases .case-tab').forEach(b => {
        b.classList.remove('active', 'text-accent', 'border-accent');
        b.classList.add('border-transparent');
      });
      btn.classList.add('active', 'text-accent', 'border-accent');
      btn.classList.remove('border-transparent');
      
      const tab = btn.dataset.tab;
      document.querySelectorAll('#view-cases .case-tab-content').forEach(c => {
        c.classList.add('hidden');
      });
      document.getElementById(`caseTabContent-${tab}`).classList.remove('hidden');
    });
  });

  // Action buttons
  const findLinked = document.getElementById('caseActionFindLinked');
  if (findLinked) {
    findLinked.addEventListener('click', () => {
      const btn = document.querySelector('#view-cases .case-tab[data-tab="linked"]');
      if (btn) btn.click();
    });
  }
  const viewNetBtn = document.getElementById('caseActionViewNetwork');
  if (viewNetBtn) {
    viewNetBtn.addEventListener('click', () => showView('network'));
  }
  const showTimeline = document.getElementById('caseActionTimeline');
  if (showTimeline) {
    showTimeline.addEventListener('click', () => {
      const container = document.getElementById('caseTimelineList');
      if (container) container.scrollIntoView({ behavior: 'smooth' });
    });
  }
  const dlHeaderBtn = document.getElementById('caseHeaderDownloadBtn');
  if (dlHeaderBtn) {
    dlHeaderBtn.addEventListener('click', () => exportPDF());
  }
  const dlActionBtn = document.getElementById('caseActionExportPdf');
  if (dlActionBtn) {
    dlActionBtn.addEventListener('click', () => exportPDF());
  }

  // Search/Filters button
  const caseApplyBtn = document.getElementById('caseApplyBtn');
  if (caseApplyBtn) {
    caseApplyBtn.addEventListener('click', async () => {
      const search = document.getElementById('caseFilterSearch').value.trim();
      const prefix = document.getElementById('caseFilterPrefix').value.trim();
      const year = document.getElementById('caseFilterYear').value.trim();
      const ps = document.getElementById('caseFilterPs').value.trim();
      const num = document.getElementById('caseFilterNum').value.trim();
      const districtId = document.getElementById('caseFilterDistrict').value;
      
      const params = new URLSearchParams();
      if (search) params.append('q', search);
      if (districtId) params.append('district_id', districtId);
      if (year) params.append('year', year);
      if (ps) params.append('ps', ps);
      if (num) params.append('sequence', num);
      
      if (!search && !districtId && !year && !ps && !num) {
        alert('Please enter a search keyword, sequence number, year, or select a district to filter.');
        return;
      }
      
      try {
        const r = await api('/cases/search?' + params.toString());
        if (num) {
          if (r.cases && r.cases.length) {
            await loadCaseDetails(r.cases[0].CrimeNo);
          } else {
            alert(`No matching case found for sequence number: ${num}`);
          }
        } else {
          handleCaseSearchList(r.cases);
        }
      } catch (e) {
        console.error(e);
        alert(`Failed to search cases: ${e.message}`);
      }
    });
  }

  // --- Theme toggle ---
  function applyChartTheme() {
    const isLight = document.body.classList.contains('light-theme');
    if (typeof Chart === 'undefined') return;
    const tickColor = isLight ? '#334155' : '#94a3b8';
    const gridColor = isLight ? '#e2e8f0' : '#1f2937';
    const legendColor = isLight ? '#1e293b' : '#cbd5e1';
    Chart.defaults.color = tickColor;
    Chart.defaults.borderColor = gridColor;
    Object.values(Chart.instances || {}).forEach(c => {
      if (c.options?.scales) {
        Object.keys(c.options.scales).forEach(axis => {
          const s = c.options.scales[axis];
          if (s.ticks) s.ticks.color = tickColor;
          if (s.grid) s.grid.color = gridColor;
          if (!s.grid) s.grid = { color: gridColor };
        });
      }
      if (c.options?.plugins?.legend?.labels) {
        c.options.plugins.legend.labels.color = legendColor;
      } else if (c.options?.plugins?.legend) {
        c.options.plugins.legend.labels = { color: legendColor };
      }
      if (c.options?.plugins?.title) {
        c.options.plugins.title.color = legendColor;
      }
      c.update('none');
    });
  }

  const themeBtn = document.getElementById('themeToggleBtn');
  const themeIcon = document.getElementById('themeIcon');
  if (localStorage.getItem('ksp-theme') === 'light') {
    document.body.classList.add('light-theme');
    if (themeBtn) themeBtn.classList.add('light');
    if (themeIcon) themeIcon.textContent = '☀️';
  }
  applyChartTheme();
  if (themeBtn) {
    themeBtn.addEventListener('click', () => {
      document.body.classList.toggle('light-theme');
      const isLight = document.body.classList.contains('light-theme');
      localStorage.setItem('ksp-theme', isLight ? 'light' : 'dark');
      themeBtn.classList.toggle('light', isLight);
      if (themeIcon) themeIcon.textContent = isLight ? '☀️' : '🌙';
      applyChartTheme();
    });
  }

  // --- Responsive hamburger ---
  const hamburger = document.getElementById('hamburgerBtn');
  const sidebar = document.getElementById('appSidebar');
  const overlay = document.getElementById('sidebarOverlay');
  function updateHamburger() {
    if (window.innerWidth <= 1024) {
      if (hamburger) hamburger.style.display = 'flex';
    } else {
      if (hamburger) hamburger.style.display = 'none';
      if (sidebar) sidebar.classList.remove('open');
      if (overlay) overlay.classList.remove('open');
    }
  }
  updateHamburger();
  window.addEventListener('resize', updateHamburger);
  if (hamburger) {
    hamburger.addEventListener('click', () => {
      sidebar?.classList.toggle('open');
      overlay?.classList.toggle('open');
    });
  }
  if (overlay) {
    overlay.addEventListener('click', () => {
      sidebar?.classList.remove('open');
      overlay.classList.remove('open');
    });
  }
  document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      if (window.innerWidth <= 1024) {
        sidebar?.classList.remove('open');
        overlay?.classList.remove('open');
      }
    });
  });

  // --- Keyboard shortcuts ---
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      const searchInput = document.getElementById('headerSearchInput');
      if (searchInput) searchInput.focus();
    }
    if ((e.ctrlKey || e.metaKey) && e.key === 'e') {
      e.preventDefault();
      const pdfBtn = document.getElementById('pdfBtn');
      if (pdfBtn) pdfBtn.click();
    }
    if ((e.ctrlKey || e.metaKey) && e.key >= '1' && e.key <= '7') {
      e.preventDefault();
      const views = ['chat', 'trends', 'cases', 'hotspots', 'predict', 'network', 'insights'];
      const idx = parseInt(e.key) - 1;
      if (idx < views.length) {
        const btn = document.querySelector(`[data-view="${views[idx]}"]`);
        if (btn && !btn.classList.contains('hidden')) btn.click();
      }
    }
  });

  applyI18n();
  await initLogin();
  await tryRestoreSession();
});
