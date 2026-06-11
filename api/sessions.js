// Lists training sessions for the trainer's Session dropdown.
// GET /api/sessions -> { sessions: [{ key, name }] }. Gated behind a valid
// trainer token (via the X-Trainer-Token header) when signing is configured,
// mirroring /api/sign; open in demo mode. Keeps the Workato token server-side.

const sign = require("../lib/sign");
const { fetchSessions } = require("../lib/sessions");

module.exports = async function handler(req, res) {
  if (req.method !== "GET") { res.status(405).json({ ok: false, message: "Method not allowed." }); return; }
  // Gate: require a valid trainer token when signing is configured; open in demo.
  if (sign.isConfigured()) {
    if (!sign.verifyToken(req.headers["x-trainer-token"] || "")) {
      res.status(401).json({ ok: false, message: "Trainer session expired." }); return;
    }
  }
  try { res.status(200).json({ sessions: await fetchSessions() }); }
  catch { res.status(502).json({ ok: false, message: "Couldn't load sessions." }); }
};
