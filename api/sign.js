// Mints check-in link signatures. Trainer-only: requires a valid token issued
// by /api/trainer-login. Body: { token, items: [{ key, session_date }] }.
// Returns { ok:true, items:[{ key, session_date, sig }] }. When signing isn't
// configured (no SIGNING_SECRET), returns sig:null so the generator builds
// plain links and check-in stays in demo mode.

const sign = require("../lib/sign");

module.exports = function handler(req, res) {
  if (req.method !== "POST") {
    res.status(405).json({ ok: false, message: "Method not allowed." });
    return;
  }

  const body = readBody(req);
  const items = Array.isArray(body.items) ? body.items : [];

  if (!sign.isConfigured()) {
    // Demo mode: hand back unsigned items.
    res.status(200).json({ ok: true, items: items.map(unsigned) });
    return;
  }

  if (!sign.verifyToken(body.token)) {
    res.status(401).json({ ok: false, message: "Your trainer session expired. Please sign in again." });
    return;
  }

  const out = items.map(function (it) {
    const key = str(it && it.key);
    const session_date = str(it && it.session_date);
    return { key: key, session_date: session_date, sig: sign.signSession(key, session_date) };
  });

  res.status(200).json({ ok: true, items: out });
};

function unsigned(it) {
  return { key: str(it && it.key), session_date: str(it && it.session_date), sig: null };
}

function readBody(req) {
  if (req.body && typeof req.body === "object") return req.body;
  if (typeof req.body === "string") {
    try { return JSON.parse(req.body); } catch { return {}; }
  }
  return {};
}

function str(v) {
  return typeof v === "string" ? v.trim() : "";
}
