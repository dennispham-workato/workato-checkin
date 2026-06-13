// Lists the training curricula for the trainer panel's curriculum checkboxes.
// GET /api/curricula -> { curricula: [{ label, name }] }. Gated behind a valid
// trainer token (via the X-Trainer-Token header) when signing is configured,
// mirroring /api/sessions; open in demo mode. Keeps the Workato token server-side.

const sign = require("../lib/sign");
const { fetchCurricula } = require("../lib/curricula");

module.exports = async function handler(req, res) {
  if (req.method !== "GET") { res.status(405).json({ ok: false, message: "Method not allowed." }); return; }
  // Gate: require a valid trainer token when signing is configured; open in demo.
  if (sign.isConfigured()) {
    if (!sign.verifyToken(req.headers["x-trainer-token"] || "")) {
      res.status(401).json({ ok: false, message: "Trainer session expired." }); return;
    }
  }
  try { res.status(200).json({ curricula: await fetchCurricula() }); }      // our API returns the correct spelling
  catch { res.status(502).json({ ok: false, message: "Couldn't load curricula." }); }
};
