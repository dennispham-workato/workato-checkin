// Trainer gate for /team. The generator page POSTs { password } here; we
// compare it to TRAINER_PASSWORD server-side with a constant-time check and
// return only pass/fail — the password itself never travels to the client.

const crypto = require("crypto");
const sign = require("../lib/sign");

module.exports = function handler(req, res) {
  if (req.method !== "POST") {
    res.status(405).json({ ok: false, message: "Method not allowed." });
    return;
  }

  const body = readBody(req);
  const supplied = typeof body.password === "string" ? body.password : "";
  const expected = process.env.TRAINER_PASSWORD || "";

  if (expected && timingSafeEqual(supplied, expected)) {
    // Hand back a short-lived token so the generator can mint signed links
    // without re-sending the password. Null when signing isn't configured.
    res.status(200).json({ ok: true, token: sign.issueToken() });
  } else {
    res.status(401).json({ ok: false });
  }
};

// Constant-time compare that tolerates unequal lengths without short-circuiting.
function timingSafeEqual(a, b) {
  const bufA = Buffer.from(a);
  const bufB = Buffer.from(b);
  if (bufA.length !== bufB.length) {
    // Still run a comparison to avoid leaking length via timing.
    crypto.timingSafeEqual(bufA, bufA);
    return false;
  }
  return crypto.timingSafeEqual(bufA, bufB);
}

function readBody(req) {
  if (req.body && typeof req.body === "object") return req.body;
  if (typeof req.body === "string") {
    try { return JSON.parse(req.body); } catch { return {}; }
  }
  return {};
}
