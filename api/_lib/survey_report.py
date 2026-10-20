# Builds the Workato-branded post-training survey PDF from a Qualtrics CSV.
# Used by api/survey-report.py; kept here (an underscore folder, so not a
# route) so it can be run and tested locally without the HTTP layer.
#
# Mirrors the pull-training-survey-report Claude skill: same grouping, scoring,
# section layout and brand styling. Body contract lives with the endpoint:
#   { ett_key, csv, summaries?: [{ curriculum, session_date, summary }],
#     flags?: [str], timezone?: str }
#
# Personal data: only an allow-list of columns is ever read (ratings,
# categoricals, topics, free text, grouping fields). Emails, names, IPs and
# locations are never touched, so they can't leak into the PDF.

import csv
import io
import os
import re
import statistics
import unicodedata
from datetime import datetime, timezone as dt_timezone
from xml.sax.saxutils import escape

import arabic_reshaper
from bidi import algorithm as bidi_algorithm
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily, stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (
    Flowable, Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
    TableStyle,
)

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:  # pragma: no cover - zoneinfo ships with Python 3.9+
    ZoneInfo = None
    ZoneInfoNotFoundError = Exception


ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
LOGO_LINE = os.path.join(ASSETS, "workato-logo.png")  # skill: workato-logo_line_blk.png
LOGO_ICON = os.path.join(ASSETS, "workato-icon.png")  # skill: workato-logo_icon_blk.png

# ---- Brand (white-background variant, per the skill) ------------------------
WHITE = HexColor("#FFFFFF")
INK = HexColor("#111010")
MUTED = HexColor("#686868")
TEAL = HexColor("#67EADD")        # header fills, accent rules
TEAL_DARK = HexColor("#3EA2A8")   # group labels / pre-headers (teal text on white)
TEAL_CARD = HexColor("#22DBC8")   # metric card left border
ROW_ALT = HexColor("#F8FFFE")
GRID = HexColor("#DADADA")

FONT = "Helvetica"
FONT_BOLD = "Helvetica-Bold"

PAGE_W, PAGE_H = letter
MARGIN = 0.6 * inch
FRAME_PAD = 6  # SimpleDocTemplate's frame padding on each side
CONTENT_W = PAGE_W - 2 * MARGIN - 2 * FRAME_PAD
CELL_PAD = 3

# ---- Survey column map (from the skill) -------------------------------------
RATING_CODES = ["Q4", "Q5", "Q21", "Q22", "Q27", "Q28", "Q3"]
CATEGORICAL_CODES = ["Q7", "Q6"]
TOPIC_PREFIX = "Q29_"
FREE_TEXT_CODES = ["Q30", "Q8", "Q9", "Q10", "Q11", "Q12"]

# Short labels for the overview table headers and the notes line. Q3 is
# CSAT-style and Q5 the closest to NPS, but it's a 5-point agree scale, so
# neither is ever labelled NPS.
SHORT = {
    "Q4": "Apply", "Q5": "Recommend", "Q21": "Depth", "Q22": "Labs",
    "Q27": "Lab guide", "Q28": "Unblocked", "Q3": "Satisfied",
    "Q7": "future training interest", "Q6": "how challenging",
    "Q29": "topics for deeper coverage", "Q30": "next automation idea",
    "Q8": "more time on", "Q9": "less time on", "Q10": "how to improve",
    "Q11": "other feedback", "Q12": "quote",
}

SCALE = [
    (5, "Strongly Agree"), (4, "Agree"), (3, "Neither Agree Nor Disagree"),
    (2, "Disagree"), (1, "Strongly Disagree"),
]
SCALE_LOOKUP = {label.lower(): score for score, label in SCALE}


# ---- Respondent text in any script ------------------------------------------
# The built-in Helvetica only has WinAnsi (cp1252) glyphs. The report's own text
# always stays in Helvetica (brand). Respondent text (comments, categorical
# values, summaries) that Helvetica can't encode is drawn cluster by cluster in
# a bundled Noto font chosen by script, with Hebrew/Arabic reordered into visual
# order (python-bidi) and Arabic letters joined (arabic-reshaper) first. Only
# the drawing changes: the answer's characters and wording are never edited.
# Emoji and scripts none of the fonts cover (e.g. CJK) get a grey placeholder
# and a line in Notes.

FONT_DIR = os.path.join(ASSETS, "fonts")
UNI_FONTS = {  # key: (regular name, file, bold name, file); OFL-*.txt alongside
    "noto": ("NotoSans", "NotoSans-Regular.ttf", "NotoSans-Bold", "NotoSans-Bold.ttf"),
    "hebrew": ("NotoSansHebrew", "NotoSansHebrew-Regular.ttf",
               "NotoSansHebrew-Bold", "NotoSansHebrew-Bold.ttf"),
    "arabic": ("NotoSansArabic", "NotoSansArabic-Regular.ttf",
               "NotoSansArabic-Bold", "NotoSansArabic-Bold.ttf"),
}
_COVERAGE = {}  # key -> set of code points the font can draw (filled lazily)

PLACEHOLDER = {"emoji": "[emoji]", "other": "[unsupported text]"}

# Lam-alef ligatures are mandatory in Arabic; the decorative "Allah" ligature
# is turned off so the drawn letters match the typed ones. Harakat are kept.
_RESHAPER = arabic_reshaper.ArabicReshaper(configuration={
    "delete_harakat": False, "delete_tatweel": False, "support_ligatures": True,
    "arabic ligature allah": False,
})


def helvetica_can_draw(text):
    try:
        text.encode("cp1252")
        return True
    except UnicodeEncodeError:
        return False


def unicode_fonts():
    """Register the Noto fonts once per process (first use only)."""
    if not _COVERAGE:
        for key, (reg, reg_file, bold, bold_file) in UNI_FONTS.items():
            regular = TTFont(reg, os.path.join(FONT_DIR, reg_file))
            pdfmetrics.registerFont(regular)
            pdfmetrics.registerFont(TTFont(bold, os.path.join(FONT_DIR, bold_file)))
            registerFontFamily(reg, normal=reg, bold=bold, italic=reg, boldItalic=bold)
            _COVERAGE[key] = set(regular.face.charToGlyph)
    return _COVERAGE


def _is_hebrew(cp):
    return 0x0590 <= cp <= 0x05FF or 0xFB1D <= cp <= 0xFB4F


def _is_arabic(cp):
    return (0x0600 <= cp <= 0x06FF or 0x0750 <= cp <= 0x077F or 0x0870 <= cp <= 0x08FF
            or 0xFB50 <= cp <= 0xFDFF or 0xFE70 <= cp <= 0xFEFF)


def _is_rtl_char(ch):
    return unicodedata.bidirectional(ch) in ("R", "AL")


def _is_emoji(cp):
    return (0x1F000 <= cp <= 0x1FAFF or 0x2600 <= cp <= 0x27BF or 0x2B00 <= cp <= 0x2BFF
            or 0x1F1E6 <= cp <= 0x1F1FF or 0x2190 <= cp <= 0x21FF or 0x2300 <= cp <= 0x23FF)


def _extends_cluster(ch):
    """Combining marks, ZWJ, variation selectors and skin tones join the previous char."""
    cp = ord(ch)
    return (unicodedata.category(ch) in ("Mn", "Mc", "Me") or cp == 0x200D
            or 0xFE00 <= cp <= 0xFE0F or 0x1F3FB <= cp <= 0x1F3FF or 0xE0020 <= cp <= 0xE007F)


def _clusters(text):
    out = []
    for ch in text:
        if out and (_extends_cluster(ch) or out[-1].endswith("‍")):
            out[-1] += ch
        else:
            out.append(ch)
    return out


def _cluster_font(cluster):
    """'helv', a UNI_FONTS key, 'skip' (invisible format char) or 'emoji'/'other'."""
    if helvetica_can_draw(cluster):
        return "helv"
    cov = unicode_fonts()
    base = ord(cluster[0])
    if len(cluster) == 1 and unicodedata.category(cluster) == "Cf" and base not in cov["noto"]:
        return "skip"  # LRM/RLM/ZWNJ etc. have no glyph to draw
    first = "hebrew" if _is_hebrew(base) else "arabic" if _is_arabic(base) else "noto"
    for key in (first, "noto", "hebrew", "arabic"):
        if all(ord(c) in cov[key] for c in cluster):
            return key
    return "emoji" if _is_emoji(base) or unicodedata.category(cluster[0]) == "So" else "other"


def _runs(text):
    """Split (already visual-order) text into [(font key, text)] runs."""
    runs = []
    for cl in _clusters(text):
        key = _cluster_font(cl)
        if key == "skip":
            continue
        # Spaces between two runs of the same Noto font stay in that font.
        if key == "helv" and cl.isspace() and runs and runs[-1][0] in UNI_FONTS:
            key = runs[-1][0]
        if runs and runs[-1][0] == key:
            runs[-1] = (key, runs[-1][1] + cl)
        else:
            runs.append((key, cl))
    return runs


def _run_font(key, bold):
    if key == "helv":
        return FONT_BOLD if bold else FONT
    reg, _, b, _ = UNI_FONTS[key]
    return b if bold else reg


def _runs_markup(runs, bold):
    out = []
    for key, txt in runs:
        if key == "helv":
            out.append(escape(txt))
        elif key in UNI_FONTS:
            out.append("<font name='%s'>%s</font>" % (_run_font(key, bold), escape(txt)))
        else:  # one grey placeholder per run of undrawable characters
            out.append("<font name='%s' color='#686868'>%s</font>"
                       % (_run_font("helv", bold), PLACEHOLDER[key]))
    return "".join(out)


def _runs_width(runs, bold, size):
    w = 0
    for key, txt in runs:
        if key in ("emoji", "other"):
            txt, key = PLACEHOLDER[key], "helv"
        w += stringWidth(txt, _run_font(key, bold), size)
    return w


def base_is_rtl(text):
    """Paragraph direction from the first strong character (UBA rules P2/P3)."""
    for ch in text:
        d = unicodedata.bidirectional(ch)
        if d in ("R", "AL"):
            return True
        if d == "L":
            return False
    return False


def shape_arabic(text):
    """Join Arabic letters into their contextual forms (logical order kept)."""
    if any(_is_arabic(ord(c)) for c in text):
        return _RESHAPER.reshape(text)
    return text


def visual_order(line, rtl):
    """One display line in left-to-right drawing order (UBA levels, L2 reorder,
    L4 mirroring of brackets).

    Combining marks in reversed RTL runs end up just before their base letter.
    That is deliberate: the Noto Hebrew/Arabic marks have zero advance and are
    drawn to the right of the pen, so drawn first they land on the base letter
    (reportlab applies no GPOS mark positioning, so placement is approximate).
    """
    storage = bidi_algorithm.get_empty_storage()
    storage["base_level"] = 1 if rtl else 0
    storage["base_dir"] = "R" if rtl else "L"
    bidi_algorithm.get_embedding_levels(line, storage)
    bidi_algorithm.explicit_embed_and_overrides(storage)
    bidi_algorithm.resolve_weak_types(storage, False)
    bidi_algorithm.resolve_neutral_types(storage, False)
    bidi_algorithm.resolve_implicit_levels(storage, False)
    bidi_algorithm.reorder_resolved_levels(storage, False)
    bidi_algorithm.apply_mirroring(storage, False)
    return "".join(c["ch"] for c in storage["chars"])


def _prepare(text):
    """Drawing copy of respondent text: NFC (so é is one glyph), unified line breaks."""
    return unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n"))


def inline_markup(text, bold=False):
    """Markup for a short respondent value that is drawn on one line."""
    if helvetica_can_draw(text):
        return esc(text)
    t = _prepare(text)
    if any(_is_rtl_char(c) for c in t):
        rtl = base_is_rtl(t)
        t = "\n".join(visual_order(shape_arabic(line), rtl) for line in t.split("\n"))
    return "<br/>".join(_runs_markup(_runs(line), bold) for line in t.split("\n"))


class BidiParagraph(Flowable):
    """Paragraph for respondent text containing Hebrew/Arabic.

    Bidi reordering has to happen per *display line*, so this wraps the
    (shaped, logical-order) text itself at the width it is given, reorders each
    line, and hands the lines to an ordinary Paragraph joined by <br/>. Right
    aligned when the text's own direction is RTL.
    """

    def __init__(self, text, style, bulletText=None):
        super().__init__()
        self.logical = shape_arabic(_prepare(text))
        self.rtl = base_is_rtl(self.logical)
        self.style, self.bulletText = style, bulletText
        self.bold = style.fontName == FONT_BOLD
        self.spaceBefore, self.spaceAfter = style.spaceBefore, style.spaceAfter
        self._para = None

    def _build(self, aw):
        avail = aw - self.style.leftIndent - self.style.rightIndent - 1  # 1pt slack
        size, lines = self.style.fontSize, []
        for hard in self.logical.split("\n"):
            current, width = "", 0
            for tok in re.findall(r"\S+|\s+", hard):
                tw = _runs_width(_runs(tok), self.bold, size)
                if current and not tok.isspace() and width + tw > avail:
                    lines.append(current.rstrip())
                    current, width = "", 0
                if tok.isspace() and not current:
                    continue
                current += tok
                width += tw
            lines.append(current.rstrip())
        markup = "<br/>".join(_runs_markup(_runs(visual_order(line, self.rtl)), self.bold)
                              for line in lines)
        if not self.rtl:
            return Paragraph(markup, self.style, bulletText=self.bulletText)
        # RTL: right-aligned with indents (and the bullet) mirrored to the right.
        style = ParagraphStyle(self.style.name + "_rtl", parent=self.style, alignment=TA_RIGHT,
                               leftIndent=self.style.rightIndent,
                               rightIndent=self.style.leftIndent)
        return _RightBullet(Paragraph(markup, style), self.bulletText, style)

    def wrap(self, aw, ah):
        self._para = self._build(aw)
        self.width, self.height = self._para.wrap(aw, ah)
        return self.width, self.height

    def draw(self):
        self._para.drawOn(self.canv, 0, 0)

    def split(self, aw, ah):
        return self._build(aw).split(aw, ah)


class _RightBullet(Flowable):
    """Paragraph whose bullet sits at the right edge of its first line (RTL lists)."""

    def __init__(self, para, bullet, style):
        super().__init__()
        self.para, self.bullet, self.style = para, bullet, style
        self.spaceBefore, self.spaceAfter = style.spaceBefore, style.spaceAfter

    def wrap(self, aw, ah):
        self.width, self.height = self.para.wrap(aw, ah)
        return self.width, self.height

    def draw(self):
        self.para.drawOn(self.canv, 0, 0)
        if self.bullet:
            st = self.style
            y = self.height - getattr(self.para.blPara, "ascent", st.fontSize)
            self.canv.setFont(st.bulletFontName, st.bulletFontSize)
            self.canv.setFillColor(st.textColor)
            self.canv.drawRightString(self.width - st.bulletIndent, y, self.bullet)

    def split(self, aw, ah):
        parts = self.para.split(aw, ah)
        return [_RightBullet(p, self.bullet if i == 0 else None, self.style)
                for i, p in enumerate(parts)]


def respondent_para(text, style, bulletText=None):
    """Flowable for text a respondent typed (or a summary quoting them)."""
    if helvetica_can_draw(text):
        return Paragraph(esc(text), style, bulletText=bulletText)
    if any(_is_rtl_char(c) for c in text):
        return BidiParagraph(text, style, bulletText)
    return Paragraph(inline_markup(text, style.fontName == FONT_BOLD), style,
                     bulletText=bulletText)


def undrawable_kinds(text):
    """Set of placeholder kinds ('emoji', 'other') this text would need."""
    if helvetica_can_draw(text):
        return set()
    return {k for k, _ in _runs(_prepare(text)) if k in PLACEHOLDER}


class ReportInputError(ValueError):
    """Bad request body or unusable CSV; the endpoint maps this to a 400."""


# ============================================================================
# Public entry point
# ============================================================================

def build_report(payload, now=None):
    """Validate the request body and return (filename, pdf_bytes)."""
    if not isinstance(payload, dict):
        raise ReportInputError("Body must be a JSON object.")

    ett_key = normalize_ett_key(payload.get("ett_key"))
    csv_text = payload.get("csv")
    if not isinstance(csv_text, str) or not csv_text.strip():
        raise ReportInputError("csv is required (the full Qualtrics CSV text).")

    summaries = payload.get("summaries") or []
    if not isinstance(summaries, list):
        raise ReportInputError("summaries must be a list.")
    flags = payload.get("flags") or []
    if not isinstance(flags, list) or not all(isinstance(f, str) for f in flags):
        raise ReportInputError("flags must be a list of strings.")
    tz_name = payload.get("timezone") or "UTC"
    if not isinstance(tz_name, str):
        raise ReportInputError("timezone must be a string such as America/Los_Angeles.")

    survey = parse_survey(csv_text)
    groups = group_rows(survey, summaries)
    generated = format_generated(tz_name, now)

    pdf = render_pdf(ett_key, survey, groups, [f.strip() for f in flags if f.strip()], generated)
    return "%s Survey Report.pdf" % ett_key, pdf


def normalize_ett_key(value):
    """'ett-684', 'ETT-684' and '684' all become 'ETT-684'."""
    s = str(value).strip() if isinstance(value, (str, int)) else ""
    m = re.fullmatch(r"(?i)(?:ett-?)?(\d{1,7})", s)
    if not m:
        raise ReportInputError("ett_key is required, e.g. ETT-684.")
    return "ETT-%s" % m.group(1)


# ============================================================================
# Parsing
# ============================================================================

def parse_survey(csv_text):
    """Row 1 codes, row 2 question text, row 3 import metadata, data from row 4.

    Rows whose column count differs from the header are skipped and counted
    (the upstream recipe currently splits multi-line answers into broken rows).
    """
    text = csv_text.lstrip("﻿")
    rows = list(csv.reader(io.StringIO(text, newline="")))
    if len(rows) < 3:
        raise ReportInputError("CSV needs the 3 Qualtrics header rows plus data.")

    codes = [c.strip() for c in rows[0]]
    texts = rows[1] + [""] * (len(codes) - len(rows[1]))
    col = {c: i for i, c in enumerate(codes) if c}
    for required in ("session_name", "session_date", "training_name"):
        if required not in col:
            raise ReportInputError("CSV is missing the %s column." % required)

    malformed = 0
    data = []
    for r in rows[3:]:
        if not any(cell.strip() for cell in r):
            continue  # blank line, not a response
        if len(r) != len(codes):
            malformed += 1
            continue
        data.append(r)
    if not data:
        raise ReportInputError("CSV has no usable response rows.")

    def qtext(code):
        t = texts[col[code]].strip()
        return t or code

    rating = [(c, qtext(c)) for c in RATING_CODES if c in col]
    categorical = [(c, qtext(c)) for c in CATEGORICAL_CODES if c in col]
    free_text = [(c, qtext(c)) for c in FREE_TEXT_CODES if c in col]
    topics = []
    topic_stem = ""
    for c in sorted((c for c in col if c.startswith(TOPIC_PREFIX)),
                    key=lambda c: int(c[len(TOPIC_PREFIX):]) if c[len(TOPIC_PREFIX):].isdigit() else 999):
        full = texts[col[c]].strip()
        stem, sep, label = full.rpartition(" - ")
        topics.append((c, label.strip() if sep else (full or c)))
        if sep and not topic_stem:
            topic_stem = stem.strip()

    # Keep only allow-listed fields per response.
    wanted = [c for c, _ in rating + categorical + free_text + topics]
    responses = []
    for r in data:
        resp = {c: r[col[c]] for c in wanted}
        resp["_session_name"] = r[col["session_name"]].strip()
        resp["_training_name"] = r[col["training_name"]].strip()
        resp["_session_date"] = r[col["session_date"]].strip()
        responses.append(resp)

    return {
        "responses": responses,
        "malformed": malformed,
        "rating": rating,
        "categorical": categorical,
        "free_text": free_text,
        "topics": topics,
        "topic_stem": topic_stem or "Topics for deeper coverage",
    }


# ============================================================================
# Grouping (contract: endpoint and Genie must agree)
# ============================================================================

def split_curriculum(session_name, training_name):
    """Return (curriculum, session_label).

    curriculum = session_name, unless session_name contains " | ": then the row
    predates the 19 Oct 2026 swap and the two fields are swapped.
    """
    if " | " in session_name:
        return training_name, session_name
    return session_name, training_name


def parse_date(raw):
    for fmt in ("%m-%d-%Y", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            pass
    return None


def date_key(raw):
    d = parse_date(raw or "")
    return d.strftime("%m-%d-%Y") if d else (raw or "").strip()


def long_date(d):
    return "%s %d, %d" % (d.strftime("%B"), d.day, d.year)


def group_rows(survey, summaries):
    summary_by_key = {}
    for s in summaries:
        if not isinstance(s, dict):
            raise ReportInputError("Each summaries item must be an object.")
        text = s.get("summary")
        if isinstance(text, str) and text.strip():
            key = (str(s.get("curriculum") or "").strip().lower(),
                   date_key(str(s.get("session_date") or "")))
            summary_by_key[key] = text.strip()

    groups = {}
    for resp in survey["responses"]:
        curriculum, label = split_curriculum(resp["_session_name"], resp["_training_name"])
        key = (curriculum.strip().lower(), date_key(resp["_session_date"]))
        g = groups.get(key)
        if g is None:
            d = parse_date(resp["_session_date"])
            g = groups[key] = {
                "key": key,
                "curriculum": curriculum.strip(),
                "date": d,
                "date_label": long_date(d) if d else (resp["_session_date"] or "No date"),
                "session_labels": [],
                "rows": [],
            }
        if label and label not in g["session_labels"]:
            g["session_labels"].append(label)
        g["rows"].append(resp)

    out = sorted(groups.values(),
                 key=lambda g: (g["date"] is None, g["date"] or datetime.min.date(), g["key"][0]))
    for g in out:
        code = g["curriculum"].upper() or "NO CURRICULUM"
        g["label"] = "%s · %s" % (code, g["date_label"])
        g["summary"] = summary_by_key.get(g["key"], "")

    total = sum(len(g["rows"]) for g in out)
    if total != len(survey["responses"]):  # Rule: group counts sum to the total.
        raise RuntimeError("Group counts do not add up to the total response count.")
    return out


# ============================================================================
# Scoring
# ============================================================================

def score(value):
    v = (value or "").strip().lower()
    if v in SCALE_LOOKUP:
        return SCALE_LOOKUP[v]
    if v in ("1", "2", "3", "4", "5"):  # numeric exports
        return int(v)
    return None


def scores_for(rows, code):
    return [s for s in (score(r.get(code)) for r in rows) if s is not None]


def modes(values):
    if not values:
        return []
    counts = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    top = max(counts.values())
    tied = [v for v, n in counts.items() if n == top]
    try:
        return sorted(tied, reverse=True)
    except TypeError:
        return tied


def fmt_num(x):
    if x is None:
        return "–"
    if float(x).is_integer():
        return "%d" % x
    return "%.2f" % x


def mean_or_none(values):
    return statistics.mean(values) if values else None


def overall_mean(rows, codes):
    """Average of the per-question means (questions with data only)."""
    means = [m for m in (mean_or_none(scores_for(rows, c)) for c in codes) if m is not None]
    return statistics.mean(means) if means else None


def answered(rows, code):
    return [r[code] for r in rows if (r.get(code) or "").strip()]


def format_generated(tz_name, now=None):
    tz = dt_timezone.utc
    if ZoneInfo is not None and tz_name.upper() != "UTC":
        try:
            tz = ZoneInfo(tz_name)
        except (ZoneInfoNotFoundError, ValueError, KeyError, OSError):
            tz = dt_timezone.utc  # unknown zone or no tzdata on the host
    t = (now or datetime.now(dt_timezone.utc)).astimezone(tz)
    clock = t.strftime("%I:%M %p").lstrip("0")
    return "%s, %s %s" % (long_date(t), clock, t.tzname() or "UTC")


# ============================================================================
# Rendering helpers
# ============================================================================

def P(text, style):
    return Paragraph(text, style)


def esc(text):
    """Escape for reportlab Paragraph markup; wording itself is unchanged."""
    return escape(text).replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br/>")


STYLES = {
    "body": ParagraphStyle("body", fontName=FONT, fontSize=9.5, leading=13, textColor=INK),
    "meta": ParagraphStyle("meta", fontName=FONT, fontSize=9.5, leading=14, textColor=INK),
    "muted": ParagraphStyle("muted", fontName=FONT, fontSize=8, leading=11, textColor=MUTED),
    "title": ParagraphStyle("title", fontName=FONT_BOLD, fontSize=22, leading=26, textColor=INK),
    "h2": ParagraphStyle("h2", fontName=FONT_BOLD, fontSize=15, leading=19, textColor=INK),
    "h3": ParagraphStyle("h3", fontName=FONT_BOLD, fontSize=10.5, leading=14, textColor=INK,
                         spaceAfter=4),
    "count": ParagraphStyle("count", fontName=FONT, fontSize=8, leading=11, textColor=MUTED,
                            spaceAfter=6),
    "question": ParagraphStyle("question", fontName=FONT_BOLD, fontSize=10, leading=13.5,
                               textColor=INK, spaceBefore=8, spaceAfter=4),
    "answer": ParagraphStyle("answer", fontName=FONT, fontSize=9.5, leading=13, textColor=INK,
                             leftIndent=12, bulletIndent=2, spaceAfter=3),
    "th": ParagraphStyle("th", fontName=FONT_BOLD, fontSize=7.5, leading=9, textColor=INK),
    "th_c": ParagraphStyle("th_c", fontName=FONT_BOLD, fontSize=7.5, leading=9, textColor=INK,
                           alignment=1),
    "td": ParagraphStyle("td", fontName=FONT, fontSize=8, leading=10, textColor=INK),
    "td_c": ParagraphStyle("td_c", fontName=FONT, fontSize=8, leading=10, textColor=INK,
                           alignment=1),
    "td_b": ParagraphStyle("td_b", fontName=FONT_BOLD, fontSize=8, leading=10, textColor=INK),
    "td_bc": ParagraphStyle("td_bc", fontName=FONT_BOLD, fontSize=8, leading=10, textColor=INK,
                            alignment=1),
    "card_label": ParagraphStyle("card_label", fontName=FONT, fontSize=7.5, leading=9.5,
                                 textColor=MUTED),
    "card_value": ParagraphStyle("card_value", fontName=FONT_BOLD, fontSize=15, leading=18,
                                 textColor=INK),
}


class Heading(Flowable):
    """Sentence-case heading in ink with a teal accent rule beneath (skill)."""

    def __init__(self, text, style, rule_w=56, rule_h=3.5, gap=5, space_before=0):
        super().__init__()
        self.para = Paragraph(esc(text), style)
        self.rule_w, self.rule_h, self.gap = rule_w, rule_h, gap
        self.spaceBefore = space_before
        self.spaceAfter = 10
        self.keepWithNext = True

    def wrap(self, aw, ah):
        _, self.ph = self.para.wrap(aw, ah)
        self.width = aw
        self.height = self.ph + self.gap + self.rule_h
        return aw, self.height

    def draw(self):
        self.para.drawOn(self.canv, 0, self.rule_h + self.gap)
        self.canv.setFillColor(TEAL)
        self.canv.rect(0, 0, self.rule_w, self.rule_h, stroke=0, fill=1)


class PreHeader(Flowable):
    """UPPERCASE, letter-spaced group label in #3EA2A8 (skill)."""

    def __init__(self, text, size=9, char_space=1.2, space_before=6, space_after=6):
        super().__init__()
        self.text = text.upper()
        self.size, self.char_space = size, char_space
        self.spaceBefore, self.spaceAfter = space_before, space_after
        self.keepWithNext = True

    def wrap(self, aw, ah):
        self.width, self.height = aw, self.size + 3
        return aw, self.height

    def draw(self):
        t = self.canv.beginText(0, 3)
        t.setFont(FONT_BOLD, self.size)
        t.setFillColor(TEAL_DARK)
        t.setCharSpace(self.char_space)
        t.textOut(self.text)
        self.canv.drawText(t)


def keep_next(flowable):
    flowable.keepWithNext = True
    return flowable


def min_col_width(strings, font, size):
    """Narrowest column that fits the longest single word (no mid-word breaks)."""
    widest = 0
    for s in strings:
        for word in re.split(r"\s+|<br/>", s):
            widest = max(widest, stringWidth(word, font, size))
    return widest + 2 * CELL_PAD + 2


def fit_widths(fixed, flex_index, total=CONTENT_W, flex_min=110):
    """fixed: list of min widths (None at flex_index). The flex column takes the rest."""
    used = sum(w for i, w in enumerate(fixed) if i != flex_index)
    out = list(fixed)
    out[flex_index] = max(flex_min, total - used)
    return out


def table_style(n_rows, header_rows=1, extra=None):
    cmds = [
        ("BACKGROUND", (0, 0), (-1, header_rows - 1), TEAL),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, GRID),
        ("LEFTPADDING", (0, 0), (-1, -1), CELL_PAD),
        ("RIGHTPADDING", (0, 0), (-1, -1), CELL_PAD),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for i in range(header_rows, n_rows):
        cmds.append(("BACKGROUND", (0, i), (-1, i),
                     WHITE if (i - header_rows) % 2 == 0 else ROW_ALT))
    return TableStyle(cmds + (extra or []))


def metric_cards(items):
    """White cards, 1pt #DADADA border, 4pt #22DBC8 left border, bold value."""
    gap = 8
    n = len(items)
    card_w = (CONTENT_W - gap * (n - 1)) / n
    row, widths, cmds = [], [], []
    for i, (label, value) in enumerate(items):
        if i:
            row.append("")
            widths.append(gap)
        c = len(row)
        row.append([P(esc(label), STYLES["card_label"]), P(esc(value), STYLES["card_value"])])
        widths.append(card_w)
        cmds += [
            ("BOX", (c, 0), (c, 0), 1, GRID),
            ("LINEBEFORE", (c, 0), (c, 0), 4, TEAL_CARD),
            ("BACKGROUND", (c, 0), (c, 0), WHITE),
            ("LEFTPADDING", (c, 0), (c, 0), 9),
            ("TOPPADDING", (c, 0), (c, 0), 6),
            ("BOTTOMPADDING", (c, 0), (c, 0), 7),
        ]
    t = Table([row], colWidths=widths)
    t.setStyle(TableStyle(cmds + [("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return t


class FooterCanvas(rl_canvas.Canvas):
    """Defers page output so the footer can say 'Page X of Y'."""

    def __init__(self, *args, footer_text="", **kwargs):
        super().__init__(*args, **kwargs)
        self._pages = []
        self._footer_text = footer_text

    def showPage(self):
        self._pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._pages)
        for state in self._pages:
            self.__dict__.update(state)
            self._draw_footer(total)
            super().showPage()
        super().save()

    def _draw_footer(self, total):
        y = 0.38 * inch
        self.saveState()
        self.setStrokeColor(GRID)
        self.setLineWidth(0.5)
        self.line(MARGIN, y + 16, PAGE_W - MARGIN, y + 16)
        icon_h = 10
        icon_w = icon_h * 272 / 163
        self.drawImage(LOGO_ICON, MARGIN, y - 1.5, width=icon_w, height=icon_h, mask="auto")
        self.setFont(FONT, 7.5)
        self.setFillColor(MUTED)
        self.drawString(MARGIN + icon_w + 6, y, self._footer_text)
        self.drawRightString(PAGE_W - MARGIN, y, "Page %d of %d" % (self._pageNumber, total))
        self.restoreState()


def white_background(canv, _doc):
    canv.saveState()
    canv.setFillColor(WHITE)
    canv.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    canv.restoreState()


# ============================================================================
# Report
# ============================================================================

def render_pdf(ett_key, survey, groups, flags, generated):
    responses = survey["responses"]
    total = len(responses)
    rating = survey["rating"]
    rating_codes = [c for c, _ in rating]
    multi = len(groups) > 1

    # Questions with zero responses anywhere are omitted (and listed in Notes).
    rating_live = [(c, t) for c, t in rating if scores_for(responses, c)]
    cat_live = [(c, t) for c, t in survey["categorical"] if answered(responses, c)]
    free_live = [(c, t) for c, t in survey["free_text"] if answered(responses, c)]
    topics_live = any(answered(responses, c) for c, _ in survey["topics"])
    omitted = [c for c in rating_codes if c not in dict(rating_live)]
    omitted += [c for c, _ in survey["categorical"] if c not in dict(cat_live)]
    if survey["topics"] and not topics_live:
        omitted.append("Q29")
    omitted += [c for c, _ in survey["free_text"] if c not in dict(free_live)]
    live_codes = [c for c, _ in rating_live]

    story = []

    # ---- Header -----------------------------------------------------------
    logo_w = 1.45 * inch
    story.append(Image(LOGO_LINE, width=logo_w, height=logo_w * 163 / 1002, hAlign="LEFT"))
    story.append(Spacer(1, 16))
    story.append(Heading("%s Survey Report" % ett_key, STYLES["title"], rule_w=72, rule_h=4))

    labels = []
    for g in groups:
        for lbl in g["session_labels"]:
            if lbl not in labels:
                labels.append(lbl)
    dates = []
    for g in groups:
        if g["date_label"] not in dates:
            dates.append(g["date_label"])
    meta = [
        ("Training name", "; ".join(labels) or "Not recorded"),
        ("Sessions", str(len(groups))),
        ("Session date%s" % ("s" if len(dates) > 1 else ""), "; ".join(dates)),
        ("Total responses", str(total)),
        ("Report generated", generated),
    ]
    for k, v in meta:
        story.append(P("<font name='%s'>%s:</font> %s" % (FONT_BOLD, esc(k), inline_markup(v)),
                       STYLES["meta"]))
    story.append(Spacer(1, 6))
    story.append(P("<font name='%s'>Rating scale:</font> %s. Blank answers are ignored."
                   % (FONT_BOLD, ", ".join("%s = %d" % (lbl, s) for s, lbl in SCALE)),
                   STYLES["muted"]))
    story.append(Spacer(1, 14))

    overall = overall_mean(responses, live_codes)
    cards = [("Total responses", str(total)), ("Overall average", fmt_avg(overall))]
    if "Q3" in live_codes:
        cards.append(("Satisfied (Q3, CSAT-style)", fmt_avg(mean_or_none(scores_for(responses, "Q3")))))
    if "Q5" in live_codes:
        cards.append(("Would recommend (Q5)", fmt_avg(mean_or_none(scores_for(responses, "Q5")))))
    story.append(metric_cards(cards))
    story.append(Spacer(1, 18))

    # ---- Section 1: Overview ---------------------------------------------
    story.append(Heading("Section 1: Overview", STYLES["h2"]))
    story.append(overview_table(groups, responses, rating_live, multi))
    story.append(Spacer(1, 6))
    story.append(P("Averages on the 1–5 scale. Overall = mean of the question averages. "
                   + "; ".join("<font name='%s'>%s</font> (%s): %s"
                               % (FONT_BOLD, esc(SHORT.get(c, c)), c, esc(t))
                               for c, t in rating_live),
                   STYLES["muted"]))

    summaries = [g for g in groups if g["summary"]]
    if summaries:
        story.append(Spacer(1, 12))
        story.append(keep_next(P("Summary of themes", STYLES["h3"])))
        for g in groups:
            if not g["summary"]:
                continue
            if multi:
                story.append(PreHeader(g["label"], size=8, space_before=4, space_after=3))
            story.append(respondent_para(g["summary"], STYLES["body"]))
            story.append(Spacer(1, 4))

    story.append(Spacer(1, 12))
    story.append(P(notes_line(survey, groups, omitted, flags), STYLES["muted"]))

    # ---- Section 2: Quantitative (per group) ------------------------------
    story.append(PageBreak())
    story.append(Heading("Section 2: Quantitative", STYLES["h2"]))
    for i, g in enumerate(groups):
        story += quantitative_group(g, survey, rating_live, cat_live, topics_live, first=(i == 0))

    # ---- Section 3: Qualitative (per group) -------------------------------
    story.append(PageBreak())
    story.append(Heading("Section 3: Qualitative", STYLES["h2"]))
    story.append(P("Answers appear exactly as submitted, without respondent identity.",
                   STYLES["muted"]))
    for i, g in enumerate(groups):
        story += qualitative_group(g, free_live, first=(i == 0))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter, leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=0.55 * inch, bottomMargin=0.85 * inch,
        title="%s Survey Report" % ett_key, author="Workato Academy",
        subject="Post-training survey report",
    )
    doc.build(story, onFirstPage=white_background, onLaterPages=white_background,
              canvasmaker=lambda *a, **k: FooterCanvas(
                  *a, footer_text="%s Survey Report" % ett_key, **k))
    return buf.getvalue()


def fmt_avg(x):
    return "–" if x is None else "%.2f" % x


def overview_table(groups, responses, rating_live, multi):
    codes = [c for c, _ in rating_live]
    head = ["Session", "Responses"] + [SHORT.get(c, c) for c in codes] + ["Overall", "Future training: Yes"]
    has_future = bool(answered(responses, "Q7"))
    if not has_future:
        head.pop()

    def row_for(label, rows, bold=False):
        td = STYLES["td_bc" if bold else "td_c"]
        cells = [P(label, STYLES["td_b" if bold else "td"]), P(str(len(rows)), td)]
        for c in codes:
            cells.append(P(fmt_avg(mean_or_none(scores_for(rows, c))), td))
        cells.append(P(fmt_avg(overall_mean(rows, codes)), STYLES["td_bc"]))
        if has_future:
            yes = sum(1 for r in rows if (r.get("Q7") or "").strip().lower() == "yes")
            cells.append(P("%d of %d" % (yes, len(rows)), td))
        return cells

    data = [[P(esc(h), STYLES["th" if i == 0 else "th_c"]) for i, h in enumerate(head)]]
    for g in groups:
        code = esc(g["curriculum"].upper() or "NO CURRICULUM")
        data.append(row_for("%s<br/>%s" % (code, esc(g["date_label"])), g["rows"]))
    if multi:
        data.append(row_for("Combined", responses, bold=True))

    mins = [None] + [min_col_width([h, "Responses" if i == 0 else "0.00"], FONT_BOLD, 7.5)
                     for i, h in enumerate(head[1:])]
    if has_future:
        mins[-1] = min_col_width(["training:", "00 of 00"], FONT_BOLD, 7.5)
    widths = fit_widths(mins, 0, flex_min=80)
    extra = []
    if multi:
        extra.append(("LINEABOVE", (0, len(data) - 1), (-1, len(data) - 1), 1, TEAL_DARK))
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(table_style(len(data), extra=extra))
    return t


def quantitative_group(g, survey, rating_live, cat_live, topics_live, first):
    rows = g["rows"]
    out = [PreHeader(g["label"], space_before=0 if first else 16),
           keep_next(P("%d response%s" % (len(rows), "" if len(rows) == 1 else "s"),
                       STYLES["count"]))]

    # Rating table: one row per rating question with data in this group.
    q_rows = [(c, t, scores_for(rows, c)) for c, t in rating_live]
    q_rows = [x for x in q_rows if x[2]]
    if q_rows:
        head = ["Question"] + [lbl for _, lbl in SCALE] + ["Mean", "Median", "Mode", "Min", "Max", "Count"]
        data = [[P(esc(h), STYLES["th" if i == 0 else "th_c"]) for i, h in enumerate(head)]]
        for c, text, vals in q_rows:
            n = len(vals)
            cells = [P(esc(text), STYLES["td"])]
            for s, _ in SCALE:
                k = vals.count(s)
                cells.append(P("%d<br/><font color='#686868'>%d%%</font>" % (k, round(100.0 * k / n)),
                               STYLES["td_c"]))
            cells += [
                P("%.2f" % statistics.mean(vals), STYLES["td_bc"]),
                P(fmt_num(statistics.median(vals)), STYLES["td_c"]),
                P(", ".join(str(m) for m in modes(vals)), STYLES["td_c"]),
                P(str(min(vals)), STYLES["td_c"]),
                P(str(max(vals)), STYLES["td_c"]),
                P(str(n), STYLES["td_c"]),
            ]
            data.append(cells)
        mins = [None] + [min_col_width([h, "100%", "5, 4, 3"], FONT_BOLD, 7.5) if h == "Mode"
                         else min_col_width([h, "100%"], FONT_BOLD, 7.5) for h in head[1:]]
        t = Table(data, colWidths=fit_widths(mins, 0), repeatRows=1)
        t.setStyle(table_style(len(data)))
        out += [keep_next(P("Rating questions", STYLES["h3"])), t, Spacer(1, 12)]

    # Yes/no and categorical: count, percentage, mode.
    cat_data = [[P(esc(h), STYLES["th" if i < 2 else "th_c"])
                 for i, h in enumerate(["Question", "Response", "Count", "%", "Mode"])]]
    spans = []
    for c, text in cat_live:
        vals = [v.strip() for v in answered(rows, c)]
        if not vals:
            continue
        counts = {}
        for v in vals:
            counts[v] = counts.get(v, 0) + 1
        ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        start = len(cat_data)
        mode_txt = ", ".join(inline_markup(m) for m in modes(vals))
        for j, (v, k) in enumerate(ordered):
            cat_data.append([
                P(esc(text), STYLES["td"]) if j == 0 else "",
                respondent_para(v, STYLES["td"]),
                P(str(k), STYLES["td_c"]),
                P("%d%%" % round(100.0 * k / len(vals)), STYLES["td_c"]),
                P(mode_txt, STYLES["td_c"]) if j == 0 else "",
            ])
        if len(ordered) > 1:
            end = len(cat_data) - 1
            spans += [("SPAN", (0, start), (0, end)), ("SPAN", (4, start), (4, end))]
    if len(cat_data) > 1:
        fixed = [1.6 * inch, 0.55 * inch, 0.55 * inch, 1.0 * inch]
        widths = [CONTENT_W - sum(fixed)] + fixed
        t = Table(cat_data, colWidths=widths, repeatRows=1)
        t.setStyle(table_style(len(cat_data), extra=spans))
        out += [keep_next(P("Yes/no and categorical questions", STYLES["h3"])),
                t, Spacer(1, 12)]

    # Multi-select topics: count per option.
    if topics_live:
        topic_rows = [(label, len(answered(rows, c))) for c, label in survey["topics"]]
        if any(k for _, k in topic_rows):
            data = [[P("Topic", STYLES["th"]), P("Count", STYLES["th_c"])]]
            for label, k in topic_rows:
                data.append([P(esc(label), STYLES["td"]), P(str(k), STYLES["td_c"])])
            t = Table(data, colWidths=[3.2 * inch, 0.7 * inch], repeatRows=1, hAlign="LEFT")
            t.setStyle(table_style(len(data)))
            out += [keep_next(P(esc(survey["topic_stem"]), STYLES["h3"])), t,
                    Spacer(1, 12)]
    return out


def qualitative_group(g, free_live, first):
    out = [PreHeader(g["label"], space_before=8 if first else 18)]
    any_answers = False
    for c, text in free_live:
        answers = [a for a in (r.get(c) or "" for r in g["rows"]) if a.strip()]
        if not answers:
            continue
        any_answers = True
        out.append(keep_next(P("%s <font name='%s' color='#686868'>(%d)</font>"
                               % (esc(text), FONT, len(answers)), STYLES["question"])))
        for a in answers:
            out.append(respondent_para(a, STYLES["answer"], bulletText="•"))
    if not any_answers:
        out.append(P("No written answers for this session.", STYLES["muted"]))
    return out


def notes_line(survey, groups, omitted, flags):
    parts = []
    if omitted:
        parts.append("Questions omitted for no responses: " + ", ".join(
            "%s (%s)" % (c, SHORT.get(c, c)) for c in omitted) + ".")
    else:
        parts.append("No questions were omitted.")
    n = survey["malformed"]
    if n:
        parts.append("%d malformed row%s skipped: the column count did not match the header "
                     "(usually a multi-line answer split upstream), so %s answers are not "
                     "included." % (n, " was" if n == 1 else "s were", "its" if n == 1 else "their"))

    tests = [esc(f) for f in flags]
    responses = survey["responses"]
    if len(responses) > 1:
        by_curriculum = {}
        for g in groups:
            by_curriculum.setdefault(g["key"][0], []).extend(g["rows"])
        for g in groups:
            rows = by_curriculum.get(g["key"][0], [])
            if len(rows) == 1 and len(g["rows"]) == 1:
                vals = [score(rows[0].get(c)) for c, _ in survey["rating"]]
                vals = [v for v in vals if v is not None]
                if vals and all(v == 5 for v in vals):
                    tests.append("possible test response in %s (single response, all top "
                                 "scores; not excluded)" % esc(g["label"]))
    if tests:
        parts.append("Flagged: " + "; ".join(tests) + ".")
    else:
        parts.append("No test responses were detected.")

    # Only emoji and scripts none of the bundled fonts cover (e.g. Chinese,
    # Japanese, Korean) can't be drawn; Hebrew, Arabic, Greek, Cyrillic and
    # extended Latin all render in the Noto fonts.
    kinds = {"emoji": 0, "other": 0}
    for r in responses:
        for c, _ in survey["free_text"] + survey["categorical"]:
            for k in undrawable_kinds(r.get(c) or ""):
                kinds[k] += 1
    for g in groups:
        for k in undrawable_kinds(g["summary"]):
            kinds[k] += 1
    shown = []
    if kinds["emoji"]:
        shown.append("%d with emoji, shown as %s" % (kinds["emoji"], PLACEHOLDER["emoji"]))
    if kinds["other"]:
        shown.append("%d with characters from a script the report fonts don't include (such "
                     "as Chinese, Japanese or Korean), shown as %s"
                     % (kinds["other"], PLACEHOLDER["other"]))
    if shown:
        parts.append("Some answers include characters that can't be drawn: %s. See the source "
                     "CSV for the original characters." % "; ".join(shown))

    parts.append("Respondent emails, names, IP addresses and locations are excluded.")
    return "<font name='%s' color='#111010'>Notes:</font> %s" % (FONT_BOLD, " ".join(parts))
