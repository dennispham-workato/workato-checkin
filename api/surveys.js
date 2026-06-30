// Resolves the per-day Qualtrics survey URLs for the trainer panel.
// POST /api/surveys -> { surveys: [{ session_date, url }] }
//   body: [{ session_date, key, exp_set, acct_mgr, training_name, session_name }]
// Gated behind a valid trainer token (via the X-Trainer-Token header) when
// signing is configured, mirroring /api/sessions; open in demo mode. Keeps the
// Workato token server-side.

const sign = require("../lib/sign");
const { fetchSurveyUrls } = require("../lib/surveys");

module.exports = async function handler(req, res) {
  if (req.method !== "POST") { res.status(405).json({ ok: false, message: "Method not allowed." }); return; }
  // Gate: require a valid trainer token when signing is configured; open in demo.
  if (sign.isConfigured()) {
    if (!sign.verifyToken(req.headers["x-trainer-token"] || "")) {
      res.status(401).json({ ok: false, message: "Trainer session expired." }); return;
    }
  }
  const items = readBody(req);
  try { res.status(200).json({ surveys: await fetchSurveyUrls(items) }); }
  catch { res.status(502).json({ ok: false, message: "Couldn't load surveys." }); }
};

// The frontend posts a bare JSON array of per-day items.
function readBody(req) {
  if (Array.isArray(req.body)) return req.body;
  if (req.body && typeof req.body === "object" && Array.isArray(req.body.items)) return req.body.items;
  if (typeof req.body === "string") {
    try { const b = JSON.parse(req.body); return Array.isArray(b) ? b : (Array.isArray(b.items) ? b.items : []); }
    catch { return []; }
  }
  return [];
}
