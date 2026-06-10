// Check-in proxy. The browser POSTs { email, key, session_date } here; this
// function validates the input and forwards it to a single Workato endpoint
// (GET with query params + an API-TOKEN header), keeping the token server-side.
// With no Workato env configured it falls back to a no-op mock so the app runs
// locally / in demo mode before secrets are set.

const sign = require("../lib/sign");

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

module.exports = async function handler(req, res) {
  if (req.method !== "POST") {
    res.status(405).json({ status: "error", message: "Method not allowed." });
    return;
  }

  const body = readBody(req);
  const email = str(body.email).toLowerCase();
  const key = str(body.key);
  const session_date = str(body.session_date);
  const sig = str(body.sig);

  // Validate + normalize.
  if (!EMAIL_RE.test(email)) {
    res.status(400).json({ status: "error", message: "Please enter a valid email address." });
    return;
  }
  if (!key) {
    res.status(400).json({ status: "error", message: "Missing session — please rescan the QR code." });
    return;
  }
  if (!session_date) {
    res.status(400).json({ status: "error", message: "Missing session date — please rescan the QR code." });
    return;
  }

  // When signing is configured, the link must carry a signature we minted.
  // This is the real gate: a guessed/edited URL can't produce a valid sig.
  if (sign.isConfigured() && !sign.verifySession(key, session_date, sig)) {
    res.status(403).json({ status: "error", message: "This check-in link isn't valid. Please rescan the QR code." });
    return;
  }

  const baseUrl = process.env.WORKATO_API_URL;

  // Mock mode (local dev / demo): no external call, just report success.
  if (!baseUrl) {
    res.status(200).json({ status: "submitted" });
    return;
  }

  try {
    // The Workato endpoint is a GET that reads query params (matches the recipe trigger).
    const url = new URL(baseUrl);
    url.searchParams.set("key", key);
    url.searchParams.set("session_date", session_date);
    url.searchParams.set("email", email);

    const headers = { accept: "application/json" };
    // Workato API Management authenticates API-key clients via the API-TOKEN header.
    const apiKey = process.env.WORKATO_API_KEY && process.env.WORKATO_API_KEY.trim();
    if (apiKey) headers["API-TOKEN"] = apiKey;

    const workatoRes = await fetch(url, {
      method: "GET",
      headers,
      // A check-in should fail fast rather than hang.
      signal: AbortSignal.timeout(10000),
    });

    if (!workatoRes.ok) {
      res.status(502).json({ status: "error", message: "Couldn't save your check-in. Please try again." });
      return;
    }

    res.status(200).json({ status: "submitted" });
  } catch (err) {
    res.status(502).json({ status: "error", message: "Couldn't save your check-in. Please try again." });
  }
};

// Vercel's Node runtime parses JSON bodies into req.body, but guard for the
// raw-string case (e.g. under some local setups) so we always get an object.
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
