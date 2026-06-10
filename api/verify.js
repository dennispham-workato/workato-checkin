// Load-time check for the check-in page: is this session link one we minted?
// GET /api/verify?key=&session_date=&sig=  ->  { valid: boolean }.
// When signing isn't configured, every link is treated as valid (demo mode).
// This is a UX gate; api/submit re-validates the signature on the real write.

const sign = require("../lib/sign");

module.exports = function handler(req, res) {
  const q = (req.query && typeof req.query === "object") ? req.query : queryFromUrl(req.url);
  const key = str(q.key);
  const session_date = str(q.session_date);
  const sig = str(q.sig);

  if (!sign.isConfigured()) {
    res.status(200).json({ valid: true });
    return;
  }

  res.status(200).json({ valid: sign.verifySession(key, session_date, sig) });
};

function queryFromUrl(url) {
  try {
    const u = new URL(url, "http://localhost");
    const out = {};
    u.searchParams.forEach(function (v, k) { out[k] = v; });
    return out;
  } catch {
    return {};
  }
}

function str(v) {
  return typeof v === "string" ? v.trim() : "";
}
