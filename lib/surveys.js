// Resolves the Qualtrics survey URL for each requested day. The trainer panel
// sends one item per session date describing which survey variant to use; the
// Workato recipe picks the matching form and returns the full URL (with the
// session params already embedded and encoded).
//
//   POST {base}/surveys   { array: [{ session_date, key, exp_set, acct_mgr,
//                                     training_name, session_name }] }
//   ->                    { array: [{ session_date, url }] }
//
// With no WORKATO_API_URL configured we synthesize a demo URL per item so the
// generator is testable in demo mode (mirrors MOCK_SESSIONS / MOCK_CURRICULA).

const { workatoPost, str } = require("./sessions");

const DEMO_FORM = "https://workato.qualtrics.com/jfe/form/SV_ePbryYXIurQPztY";

function buildDemoUrl(it) {
  const q = [
    "training_name=" + str(it.training_name),
    "session_date="  + encodeURIComponent(str(it.session_date)),
    "session_name="  + encodeURIComponent(str(it.session_name)),
    "key="           + encodeURIComponent(str(it.key)),
    "exp_set="       + (it.exp_set ? "true" : "false"),
    "acct_mgr="      + (it.acct_mgr ? "true" : "false"),
  ].join("&");
  return DEMO_FORM + "?" + q;
}

// The recipe replies { array: [{ session_date, url }] }; normalize to that list.
function normalize(data) {
  const arr = Array.isArray(data && data.array) ? data.array : [];
  return arr
    .map(s => ({ session_date: str(s && s.session_date), url: str(s && s.url) }))
    .filter(s => s.session_date && s.url);
}

async function fetchSurveyUrls(items) {
  const list = Array.isArray(items) ? items : [];
  const base = process.env.WORKATO_API_URL;

  if (!base) {
    return list.map(it => ({ session_date: str(it && it.session_date), url: buildDemoUrl(it || {}) }));
  }

  // The recipe expects the days wrapped as { array: [...] } and replies the same.
  const data = await workatoPost(base, "/surveys", { array: list });
  return normalize(data);
}

module.exports = { fetchSurveyUrls };
