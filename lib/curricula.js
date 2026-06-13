// Lists the training curricula for the trainer panel's curriculum checkboxes.
// Mirrors fetchSessions(): GET {base}/curricula, normalized to [{ label, name }],
// cached briefly, with a demo-mode fallback when WORKATO_API_URL is unset.

const { workatoGet, str } = require("./sessions");

const TTL_MS = 5 * 60 * 1000;            // curricula change rarely
let _cache = { at: 0, data: null };

const MOCK_CURRICULA = [                  // demo mode (no WORKATO_API_URL) = today's list
  { label: "Workato Foundations Level 1",      name: "wf1" },
  { label: "Agentic Builder Essentials",       name: "abe" },
  { label: "Customized Training",              name: "customized" },
  { label: "Integration Developer Essentials", name: "ide" },
  { label: "MCP",                              name: "mcp" }
];

async function fetchCurricula() {
  const base = process.env.WORKATO_API_URL;
  if (!base) return MOCK_CURRICULA.slice();

  const now = Date.now();
  if (_cache.data && now - _cache.at < TTL_MS) return _cache.data;

  const data = await workatoGet(base, "/curricula");
  const arr  = data.curriucla || data.cuuricula || data.curricula || [];   // absorb misspellings
  const curricula = (Array.isArray(arr) ? arr : [])
    .map(c => ({ label: str(c.label), name: str(c.name) }))
    .filter(c => c.label && c.name);

  _cache = { at: now, data: curricula };
  return curricula;
}

module.exports = { fetchCurricula };
