// Talks to the Workato attendance API. Two helpers:
//   fetchSessions()        -> GET {base}/sessions, normalized to [{ key, name }]
//                             for the trainer dropdown (api/sessions.js).
//   fetchSessionName(key)  -> GET {base}/sessionName?key=…, the clean display
//                             name for one session (api/verify.js, attendee page).
// Both are cached briefly so a burst of attendees for one training collapses to
// ~1 Workato call per warm lambda.
//
// With no WORKATO_API_URL configured these fall back to MOCK_SESSIONS so the app
// runs locally / in demo mode before secrets are set.

const TTL_MS = 60 * 1000;
let _listCache = { at: 0, data: null };   // /sessions list (trainer dropdown)
const _nameCache = new Map();             // key -> { at, name } for /sessionName

const MOCK_SESSIONS = [           // demo data when WORKATO_API_URL is unset
  { key: "ETT-561", name: "Integration Developer Bootcamp NA Cohort #5 | Palo Alto" },
  { key: "ETT-633", name: "MCP Marketing Training | In-Person" },
];

function joinUrl(base, path) { return base.replace(/\/+$/, "") + path; }
function str(v) { return typeof v === "string" ? v.trim() : ""; }

// Workato API Management authenticates API-key clients via the API-TOKEN header
// (omitted when unset, e.g. in demo mode).
function workatoHeaders() {
  const headers = { accept: "application/json" };
  const apiKey = str(process.env.WORKATO_API_KEY);
  if (apiKey) headers["API-TOKEN"] = apiKey;
  return headers;
}

async function workatoGet(base, path) {
  const r = await fetch(joinUrl(base, path), {
    method: "GET",
    headers: workatoHeaders(),
    signal: AbortSignal.timeout(8000),
  });
  if (!r.ok) throw new Error(path + " " + r.status);
  return r.json().catch(() => ({}));
}

async function fetchSessions() {
  const base = process.env.WORKATO_API_URL;
  if (!base) return MOCK_SESSIONS.slice();                 // demo mode

  const now = Date.now();
  if (_listCache.data && now - _listCache.at < TTL_MS) return _listCache.data;

  const data = await workatoGet(base, "/sessions");
  const assets = Array.isArray(data.assets) ? data.assets : [];
  const sessions = assets
    .map(a => ({ key: str(a.asset_id), name: str(a.asset_name) }))
    .filter(s => s.key && s.name)
    .sort((a, b) => a.name.localeCompare(b.name));

  _listCache = { at: now, data: sessions };
  return sessions;
}

async function fetchSessionName(key) {
  const k = str(key);
  if (!k) return "";

  const base = process.env.WORKATO_API_URL;
  if (!base) {                                             // demo mode
    const s = MOCK_SESSIONS.find(m => m.key.toLowerCase() === k.toLowerCase());
    return s ? s.name : "";
  }

  const now = Date.now();
  const hit = _nameCache.get(k);
  if (hit && now - hit.at < TTL_MS) return hit.name;

  const data = await workatoGet(base, "/sessionName?key=" + encodeURIComponent(k));
  const name = str(data.session_name);
  _nameCache.set(k, { at: now, name });
  return name;
}

module.exports = { fetchSessions, fetchSessionName, joinUrl, workatoHeaders };
