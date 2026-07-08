// Returns the example survey questions for the trainer panel (shown when
// Qualtrics QR generation is toggled on).
// GET /api/additional_questions -> { questions: [text, ...] }. Gated behind a valid
// trainer token (via the X-Trainer-Token header) when signing is configured,
// mirroring /api/curricula; open in demo mode. Keeps the Workato token server-side.

const sign = require("../lib/sign");
const { fetchAdditionalQuestions } = require("../lib/additionalQuestions");

module.exports = async function handler(req, res) {
  if (req.method !== "GET") { res.status(405).json({ ok: false, message: "Method not allowed." }); return; }
  // Gate: require a valid trainer token when signing is configured; open in demo.
  if (sign.isConfigured()) {
    if (!sign.verifyToken(req.headers["x-trainer-token"] || "")) {
      res.status(401).json({ ok: false, message: "Trainer session expired." }); return;
    }
  }
  try { res.status(200).json({ questions: await fetchAdditionalQuestions() }); }
  catch { res.status(502).json({ ok: false, message: "Couldn't load additional questions." }); }
};
