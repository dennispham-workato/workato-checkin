// Load-time check for the check-in page: is this session link one we minted?
// GET /api/verify?key=&session_date=&sig=  ->  { valid: boolean, session_name }.
// When signing isn't configured, every link is treated as valid (demo mode).
// This is a UX gate; api/submit re-validates the signature on the real write.
//
// The session_name is a best-effort key -> name lookup (cached, timeout-bounded)
// so the attendee sees the friendly name instead of the raw code. It never
// affects `valid`: if Workato is slow/down the page just falls back to the code.

const sign = require("../lib/sign");
const { fetchSessionName } = require("../lib/sessions");

module.exports = async function handler(req, res) {
  const q = (req.query && typeof req.query === "object") ? req.query : queryFromUrl(req.url);
  const key = str(q.key);
  const session_date = str(q.session_date);
  const sig = str(q.sig);

  const valid = !sign.isConfigured() || sign.verifySession(key, session_date, sig);

  let session_name = "";
  if (valid && key) {
    try { session_name = await fetchSessionName(key); }
    catch { /* best-effort: leave blank, page falls back to the code */ }
  }

  res.status(200).json({ valid, session_name });
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
