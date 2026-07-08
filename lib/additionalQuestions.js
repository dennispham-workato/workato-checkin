// Returns the additional/example survey questions shown in the trainer panel when
// Qualtrics QR generation is toggled on. Mirrors fetchCurricula(): GET
// {base}/additional_questions, normalized to a flat array of question strings,
// cached briefly, with a demo-mode fallback when WORKATO_API_URL is unset.

const { workatoGet, str } = require("./sessions");

const TTL_MS = 5 * 60 * 1000;            // additional questions change rarely
let _cache = { at: 0, data: null };

const MOCK_QUESTIONS = [                  // demo mode (no WORKATO_API_URL)
  "How would you rate the overall quality of today's training?",
  "How confident do you feel applying what you learned?",
  "Was the pace of the session appropriate?",
  "How likely are you to recommend this training to a colleague?",
];

// The recipe replies { array: [{ question }] }; flatten to a list of strings.
function normalize(data) {
  const arr = Array.isArray(data && data.array) ? data.array : [];
  return arr.map(q => str(q && q.question)).filter(Boolean);
}

async function fetchAdditionalQuestions() {
  const base = process.env.WORKATO_API_URL;
  if (!base) return MOCK_QUESTIONS.slice();

  const now = Date.now();
  if (_cache.data && now - _cache.at < TTL_MS) return _cache.data;

  const data = await workatoGet(base, "/additional_questions");
  const questions = normalize(data);

  _cache = { at: now, data: questions };
  return questions;
}

module.exports = { fetchAdditionalQuestions };
