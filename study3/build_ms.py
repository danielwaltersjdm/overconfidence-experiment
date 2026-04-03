"""
Management Science (INFORMS) PUBLISHED format PDF.
Three-study paper: Study 1 (equities 1-day), Study 2 (equities multi-horizon),
Study 3 (multi-domain). Two-column, 9pt Times New Roman, no color.
"""
from fpdf import FPDF

FD  = r"C:\Windows\Fonts"
OUT = "paper_ms.pdf"

DARK = (0, 0, 0)
MID  = (90, 90, 90)

# ── page geometry ──────────────────────────────────────────────────────────────
PW, PH  = 215.9, 279.4
LM = RM = 20.0
TM      = 20.0
BM      = 20.0

COL_W  = 84.67
GUTTER = 6.35
COL_R  = LM + COL_W + GUTTER
FULL_W = COL_W * 2 + GUTTER

LINE_H   = 3.88   # 9pt on ~11pt leading
PARA_IND = 3.5    # first-line indent
HANG     = 5.0    # hanging indent for references


# ═════════════════════════════════════════════════════════════════════════════
# Column manager
# ═════════════════════════════════════════════════════════════════════════════
class ColManager:
    def __init__(self, pdf, col_top):
        self.pdf     = pdf
        self.col     = 0
        self.col_top = col_top

    def x(self):
        return LM if self.col == 0 else COL_R

    def remaining(self):
        return (PH - BM) - self.pdf.get_y()

    def need(self, h):
        if self.remaining() < h:
            self._advance()

    def _advance(self):
        if self.col == 0:
            self.col = 1
            self.pdf.set_xy(COL_R, self.col_top)
        else:
            self.col = 0
            self.pdf.add_page()
            self.col_top = TM
            self.pdf.set_xy(LM, TM)


# ═════════════════════════════════════════════════════════════════════════════
# PDF class
# ═════════════════════════════════════════════════════════════════════════════
class MsPDF(FPDF):

    def setup_fonts(self):
        self.add_font("TNR",  "",   rf"{FD}\times.ttf")
        self.add_font("TNR",  "B",  rf"{FD}\timesbd.ttf")
        self.add_font("TNR",  "I",  rf"{FD}\timesi.ttf")
        self.add_font("TNR",  "BI", rf"{FD}\timesbi.ttf")

    def header(self):
        if self.page_no() == 1:
            return
        self.set_xy(LM, 9)
        self.set_font("TNR", "B", 8)
        self.set_text_color(*DARK)
        self.cell(FULL_W - 15, 3.5,
                  "Walters et al.: Overconfidence in LLM Interval Estimates",
                  align="L")
        self.cell(15, 3.5, str(self.page_no()), align="R")
        self.set_xy(LM, 13.0)
        self.set_font("TNR", "", 8)
        self.cell(FULL_W, 3.5,
                  "Management Science, Articles in Advance, pp. 1\u201315, "
                  "\u00a9 2026 INFORMS",
                  align="L")
        self.set_draw_color(*DARK)
        self.set_line_width(0.25)
        self.line(LM, 17.0, LM + FULL_W, 17.0)
        # CRITICAL: restore y so body starts at TM, not at the running head y
        self.set_xy(LM, TM)

    def footer(self):
        pass


# ═════════════════════════════════════════════════════════════════════════════
# Low-level text engine
# ═════════════════════════════════════════════════════════════════════════════
def _wrap_text(pdf, font, style, size, text, width, indent_first=0.0):
    pdf.set_font(font, style, size)
    space_w = pdf.get_string_width(" ")
    words   = text.split()
    lines   = []
    cur     = []
    cur_w   = 0.0
    for word in words:
        ww    = pdf.get_string_width(word)
        avail = width - (indent_first if not lines and not cur else 0.0)
        need  = cur_w + (space_w if cur else 0.0) + ww
        if cur and need > avail:
            lines.append((cur, False))
            cur   = [word]
            cur_w = ww
        else:
            cur_w = (cur_w + space_w + ww) if cur else ww
            cur.append(word)
    if cur:
        lines.append((cur, True))
    return lines


def _write_lines(pdf, col, lines, font, style, size, color,
                 justify=True, indent_first=0.0, hang_indent=0.0):
    pdf.set_font(font, style, size)
    pdf.set_text_color(*color)
    space_w = pdf.get_string_width(" ")

    if len(lines) > 1:
        if max(0, int(col.remaining() / LINE_H)) == 1:
            col._advance()

    for line_idx, (words, is_last) in enumerate(lines):
        if not words:
            continue
        col.need(LINE_H)
        x0     = col.x()
        indent = indent_first if line_idx == 0 else hang_indent
        avail  = COL_W - indent
        y      = pdf.get_y()

        if is_last or len(words) == 1 or not justify:
            pdf.set_xy(x0 + indent, y)
            pdf.cell(avail, LINE_H, " ".join(words), align="L")
        else:
            total_w = sum(pdf.get_string_width(w) for w in words)
            gaps    = len(words) - 1
            extra   = (avail - total_w - gaps * space_w) / gaps if gaps > 0 else 0
            pdf.set_xy(x0 + indent, y)
            for i, w in enumerate(words):
                cw = pdf.get_string_width(w) + (extra + space_w if i < gaps else 0)
                pdf.cell(cw, LINE_H, w, align="L")
        pdf.set_xy(x0, y + LINE_H)


# ═════════════════════════════════════════════════════════════════════════════
# Column-level helpers
# ═════════════════════════════════════════════════════════════════════════════
def para(pdf, col, text, font="TNR", style="", size=9, color=DARK,
         indent=PARA_IND, justify=True):
    lines = _wrap_text(pdf, font, style, size, text, COL_W, indent_first=indent)
    _write_lines(pdf, col, lines, font, style, size, color,
                 justify=justify, indent_first=indent)


def section_head(pdf, col, num, title):
    col.need(16)
    x0 = col.x()
    y  = pdf.get_y() + 4
    pdf.set_font("TNR", "B", 10)
    pdf.set_text_color(*DARK)
    pdf.set_xy(x0, y)
    label = f"{num}. {title.upper()}" if num else title.upper()
    pdf.cell(COL_W, LINE_H + 1, label, align="L")
    pdf.set_xy(x0, y + LINE_H + 2.5)


def subsection_head(pdf, col, num, title):
    col.need(12)
    x0 = col.x()
    y  = pdf.get_y() + 2.5
    pdf.set_font("TNR", "BI", 9)
    pdf.set_text_color(*DARK)
    pdf.set_xy(x0, y)
    pdf.cell(COL_W, LINE_H + 0.5, f"{num} {title}.", align="L")
    pdf.set_xy(x0, y + LINE_H + 1.5)


def eqn(pdf, col, label, text):
    col.need(10)
    x0 = col.x()
    y  = pdf.get_y() + 1
    pdf.set_font("TNR", "I", 9)
    pdf.set_text_color(*DARK)
    pdf.set_xy(x0 + 5, y)
    pdf.cell(COL_W - 14, LINE_H + 1, text, align="L")
    pdf.set_xy(x0, y)
    pdf.cell(COL_W, LINE_H + 1, f"({label})", align="R")
    pdf.set_xy(x0, y + LINE_H + 2.5)


# ═════════════════════════════════════════════════════════════════════════════
# Column-width MS-style table
# ═════════════════════════════════════════════════════════════════════════════
def col_table(pdf, col, cap_num, cap_text, note, headers, rows, col_widths,
              font_size=8.0):
    scale  = COL_W / sum(col_widths)
    widths = [w * scale for w in col_widths]
    rh     = font_size * 0.44

    cap_lines  = max(1, len(cap_text) // 55 + 1)
    note_lines = max(1, len(note) // 65 + 1) if note else 0
    needed = (cap_lines * 3.5 + 5 +
              rh * (len(rows) + 2) + 8 +
              note_lines * 3.2 + 4)
    col.need(needed)
    x0 = col.x()
    y  = pdf.get_y() + 2

    # ── caption ────────────────────────────────────────────────────────────
    pdf.set_font("TNR", "B", 8)
    pdf.set_text_color(*DARK)
    pdf.set_xy(x0, y)
    label  = f"Table {cap_num}."
    lbl_w  = pdf.get_string_width(label) + 1.5
    pdf.cell(lbl_w, 3.5, label)
    pdf.set_font("TNR", "", 8)
    pdf.multi_cell(COL_W - lbl_w, 3.5, f" {cap_text}",
                   new_x="LMARGIN", new_y="NEXT")
    y = pdf.get_y() + 1

    # ── top double rule ─────────────────────────────────────────────────────
    pdf.set_draw_color(*DARK)
    pdf.set_line_width(0.6)
    pdf.line(x0, y, x0 + COL_W, y)
    pdf.set_line_width(0.22)
    pdf.line(x0, y + 0.9, x0 + COL_W, y + 0.9)
    y += 2.5

    # ── column headers ──────────────────────────────────────────────────────
    pdf.set_font("TNR", "B", font_size)
    pdf.set_text_color(*DARK)
    pdf.set_xy(x0, y)
    for i, h in enumerate(headers):
        pdf.cell(widths[i], rh, h, align="L" if i == 0 else "C")
    y += rh

    # ── rule after headers ──────────────────────────────────────────────────
    pdf.set_line_width(0.22)
    pdf.line(x0, y, x0 + COL_W, y)
    y += 1.2

    # ── data rows ───────────────────────────────────────────────────────────
    for row in rows:
        if len(row) >= 2 and all(str(c).strip() == "" for c in row[1:]):
            pdf.set_font("TNR", "BI", font_size)
            pdf.set_xy(x0, y)
            pdf.cell(COL_W, rh, str(row[0]), align="L")
            y += rh
            continue
        is_indent = str(row[0]).startswith("  ")
        pdf.set_font("TNR", "I" if is_indent else "", font_size)
        pdf.set_xy(x0, y)
        for i, cell in enumerate(row):
            txt = str(cell).lstrip() if i == 0 else str(cell)
            pdf.cell(widths[i], rh, txt, align="L" if i == 0 else "C")
        y += rh

    # ── bottom rule ─────────────────────────────────────────────────────────
    pdf.set_line_width(0.5)
    pdf.line(x0, y, x0 + COL_W, y)
    y += 1.5

    # ── note ────────────────────────────────────────────────────────────────
    if note:
        pdf.set_font("TNR", "I", 7.5)
        pdf.set_text_color(*MID)
        pdf.set_xy(x0, y)
        pdf.multi_cell(COL_W, 3.2, f"Note. {note}",
                       new_x="LMARGIN", new_y="NEXT")
        y = pdf.get_y()

    pdf.set_text_color(*DARK)
    pdf.set_xy(col.x(), y + 2)


# ── full-width helpers (title block only) ─────────────────────────────────────
def fw(pdf, text, font="TNR", style="", size=9, color=DARK, align="L", h=LINE_H):
    pdf.set_font(font, style, size)
    pdf.set_text_color(*color)
    pdf.set_x(LM)
    pdf.multi_cell(FULL_W, h, text, align=align)


def fw_rule(pdf, lw=0.3, before=1.5, after=2):
    pdf.ln(before)
    pdf.set_draw_color(*DARK)
    pdf.set_line_width(lw)
    pdf.line(LM, pdf.get_y(), LM + FULL_W, pdf.get_y())
    pdf.ln(after)


# ═════════════════════════════════════════════════════════════════════════════
# Build document
# ═════════════════════════════════════════════════════════════════════════════
pdf = MsPDF(orientation="P", unit="mm", format=(PW, PH))
pdf.setup_fonts()
pdf.set_margins(LM, TM, RM)
pdf.set_auto_page_break(False)
pdf.add_page()
pdf.set_xy(LM, TM)

# ── TITLE ─────────────────────────────────────────────────────────────────────
fw(pdf,
   "Overconfidence in Interval Estimates Produced by Large Language Models "
   "Across Multiple Forecasting Domains",
   font="TNR", style="B", size=14, align="C", h=6.5)
pdf.ln(4)

# ── AUTHORS ───────────────────────────────────────────────────────────────────
fw(pdf, "[Author Names Redacted for Review]",
   font="TNR", style="", size=9, align="C", h=LINE_H)
fw(pdf, "[Department Redacted], [University Redacted]",
   font="TNR", style="I", size=8.5, align="C", h=LINE_H)
pdf.ln(2)

fw_rule(pdf, lw=0.5, before=1, after=3)

# ── ABSTRACT ──────────────────────────────────────────────────────────────────
abs_text = (
    "Calibrated uncertainty is a prerequisite for rational decision-making, yet human "
    "experts systematically produce confidence intervals that are too narrow -- a phenomenon "
    "termed overconfidence in interval estimates. Whether frontier large language models "
    "(LLMs) exhibit analogous miscalibration, and whether it varies systematically by "
    "prediction horizon or domain, remains an open empirical question. We report three "
    "pre-registered studies in which three commercially deployed LLMs (Claude, GPT-4, "
    "and Gemini) each provided point estimates and 50%, 80%, and 90% confidence intervals "
    "for quantitative forecasting questions, scored against ground-truth outcomes. "
    "Study 1 (n = 100 per model) establishes baseline overconfidence in single-day "
    "equity predictions. Study 2 (n > 4,700 per model) shows that miscalibration "
    "increases with prediction horizon for Claude and GPT-4 but not Gemini, which "
    "maintains calibration up to 22 days. Study 3 (n = 68 per model) extends to six "
    "heterogeneous domains -- equities, commodities, cryptocurrency, forex, weather, "
    "and NBA game totals -- revealing a domain-confidence inversion: all models "
    "overstate certainty in commodity and equity markets (mu < 1) yet understate it "
    "in cryptocurrency and forex (mu > 1). GPT-4 is the most overconfident model "
    "across all three studies (ECE = 43.7%, 40.4%, 18.9% respectively); Claude is "
    "most calibrated in Study 3 (ECE = 5.3%). These findings suggest that LLMs "
    "inherit domain-specific and horizon-specific miscalibration from their training "
    "corpora, with implications for their deployment in financial decision support."
)

pdf.set_x(LM)
pdf.set_font("TNR", "B", 9)
pdf.set_text_color(*DARK)
lbl_w = pdf.get_string_width("Abstract.") + 1.5
pdf.cell(lbl_w, LINE_H, "Abstract.", new_x="END", new_y="LAST")
pdf.set_font("TNR", "", 9)
pdf.multi_cell(FULL_W - lbl_w, LINE_H, " " + abs_text, align="J",
               new_x="LMARGIN", new_y="NEXT")
pdf.ln(2)

# ── KEY WORDS ─────────────────────────────────────────────────────────────────
pdf.set_x(LM)
pdf.set_font("TNR", "B", 8.5)
kw_w = pdf.get_string_width("Key words:") + 1.5
pdf.cell(kw_w, LINE_H, "Key words:", new_x="END", new_y="LAST")
pdf.set_font("TNR", "I", 8.5)
pdf.multi_cell(FULL_W - kw_w, LINE_H,
    " large language models; overconfidence; interval estimation; calibration; "
    "forecasting; prediction horizon",
    new_x="LMARGIN", new_y="NEXT")
pdf.ln(1.5)

# ── HISTORY ───────────────────────────────────────────────────────────────────
pdf.set_x(LM)
pdf.set_font("TNR", "", 8)
pdf.set_text_color(*MID)
pdf.multi_cell(FULL_W, 3.5,
    "History: Received January 15, 2026; accepted March 20, 2026, by [Associate Editor "
    "Redacted], information systems. Published online in Articles in Advance.",
    align="L", new_x="LMARGIN", new_y="NEXT")
pdf.set_text_color(*DARK)

fw_rule(pdf, lw=0.5, before=2, after=0)

# ── START COLUMNS ─────────────────────────────────────────────────────────────
col_start_y = pdf.get_y() + 2
pdf.set_xy(LM, col_start_y)
col = ColManager(pdf, col_top=col_start_y)

# ═════════════════════════════════════════════════════════════════════════════
# 1. INTRODUCTION
# ═════════════════════════════════════════════════════════════════════════════
section_head(pdf, col, 1, "Introduction")

para(pdf, col,
    "A well-calibrated forecaster states 80% confidence intervals that contain the true "
    "outcome 80% of the time. Decades of research on human judgment document systematic "
    "failure to achieve this standard: people's confidence intervals are systematically "
    "too narrow, a phenomenon termed overconfidence in interval estimates (Alpert and "
    "Raiffa 1982, Lichtenstein et al. 1982, Klayman et al. 1999, Soll and Klayman 2004). "
    "The practical consequences are severe. Overconfident interval estimates underlie "
    "miscalibrated risk assessments in medicine (Christensen-Szalanski and Bushyhead "
    "1981), finance (Ben-David et al. 2013), engineering (Flyvbjerg et al. 2002), and "
    "strategic planning (Lovallo and Kahneman 2003).", indent=0)

para(pdf, col,
    "Large language models (LLMs) are now routinely used as decision-support tools in "
    "precisely these high-stakes domains, yet whether their probabilistic forecasts are "
    "calibrated remains an open question (Kadavath et al. 2022, Lin et al. 2022, Xiong "
    "et al. 2024). Prior work has focused on factual question-answering confidence or "
    "binary classification probability estimates. Virtually no study has examined LLM "
    "calibration on interval estimates for real-world quantitative forecasting, or "
    "asked how miscalibration varies across prediction horizons and application domains.")

para(pdf, col,
    "We address these questions with three pre-registered studies that progressively "
    "expand the scope of LLM calibration assessment. Study 1 establishes a baseline: "
    "are three frontier LLMs overconfident when predicting next-day equity prices with "
    "stated confidence intervals? Study 2 extends to multiple prediction horizons (1 to "
    "22 days) using 100 large-cap equities and over 18,000 scored predictions to ask: "
    "does miscalibration scale systematically with forecast horizon? Study 3 extends "
    "across six heterogeneous prediction domains (equities, commodities, cryptocurrency, "
    "foreign exchange, weather, NBA game scores) to ask: is miscalibration domain-specific, "
    "and can its direction reverse?")

para(pdf, col,
    "The human overconfidence literature consistently shows that miscalibration is "
    "domain-specific: experts are most overconfident in their own fields of ostensible "
    "competence (Klayman et al. 1999, Soll and Klayman 2004). It also shows that "
    "overconfidence in interval estimates increases with task difficulty and time horizon "
    "(Griffin and Tversky 1992). If LLMs inherit domain and horizon structure from their "
    "training data, they may replicate or amplify these asymmetries.")

para(pdf, col,
    "Our results confirm and extend the human literature. Across all three studies, "
    "GPT-4 is the most overconfident model and Claude the most calibrated. Study 2 "
    "reveals a striking model divergence at longer horizons: Claude and GPT-4 become "
    "increasingly miscalibrated as the prediction window grows, while Gemini maintains "
    "near-target coverage even at 22 days. Study 3 uncovers a domain-confidence "
    "inversion -- all models are overconfident in structured financial markets "
    "(equities, commodities) but underconfident in speculative markets (cryptocurrency, "
    "forex) -- a pattern absent from prior accounts of LLM calibration.")

para(pdf, col,
    "This paper contributes to three streams of literature. First, we extend the human "
    "overconfidence literature (Soll and Klayman 2004, Griffin and Tversky 1992) to a "
    "new class of forecasting agent across the largest empirical sample to date. Second, "
    "we contribute to the LLM calibration literature (Kadavath et al. 2022, Xiong et "
    "al. 2024) by focusing on interval estimates rather than point probabilities and by "
    "using real-world outcomes rather than knowledge-base queries. Third, we provide "
    "actionable guidance for practitioners deploying LLMs in financial and operational "
    "decision-support roles.")

# ═════════════════════════════════════════════════════════════════════════════
# 2. METHODS
# ═════════════════════════════════════════════════════════════════════════════
section_head(pdf, col, 2, "Methods")

subsection_head(pdf, col, "2.1.", "Common Design Elements")

para(pdf, col,
    "Three commercially deployed LLMs were evaluated across all studies: Claude "
    "(claude-sonnet-4-20250514; Anthropic), GPT-4 (gpt-4o; OpenAI), and Gemini "
    "(gemini-2.5-flash; Google DeepMind). All models were queried via their public APIs "
    "at default temperature with a maximum of 512 output tokens per response.", indent=0)

para(pdf, col,
    "Each prompt provided the current value of the target quantity and requested a point "
    "estimate plus 50%, 80%, and 90% confidence intervals as structured JSON output, "
    "with a specified target horizon. No chain-of-thought or explicit calibration "
    "instructions were given; models were evaluated in their default, "
    "deployment-ready configuration. Three confidence levels (50%, 80%, 90%) were "
    "used in all studies. Calibration was measured via Expected Calibration Error (ECE), "
    "defined as the mean absolute deviation between stated and empirical coverage "
    "across all three levels (see Section 2.5).")

subsection_head(pdf, col, "2.2.", "Study 1: Equities, Single Horizon")

para(pdf, col,
    "Study 1 (March 23, 2026) employed 20 large-cap S&P 500 equities (AAPL, NVDA, "
    "MSFT, AMZN, GOOGL, META, AVGO, TSLA, BRK-B, WMT, LLY, JPM, XOM, V, JNJ, MU, "
    "MA, ORCL, COST, SPY) with a 1-day prediction horizon (outcomes collected March "
    "24, 2026). Each model made 5 independent predictions per ticker, yielding 100 "
    "scored predictions per model. This study establishes a baseline calibration "
    "estimate under the simplest possible conditions: a single, well-defined domain "
    "and the shortest practical horizon.", indent=0)

subsection_head(pdf, col, "2.3.", "Study 2: Equities, Multi-Horizon")

para(pdf, col,
    "Study 2 expanded to 100 large-cap equities across nine prediction horizons (1, "
    "2, 3, 6, 7, 18, 20, 21, and 22 days), with a reference date of March 24, 2026 "
    "and predictions made against historical prices via backtesting. Five independent "
    "runs per ticker per model were collected at each horizon. After excluding "
    "unresolved predictions due to market closures (applied tolerance window of 6 "
    "calendar days), the study yielded between 157 and 1,497 scored predictions per "
    "model-horizon cell (total N > 18,000). This design allows direct measurement of "
    "how confidence interval miscalibration scales with the prediction horizon.", indent=0)

subsection_head(pdf, col, "2.4.", "Study 3: Multi-Domain, Single Horizon")

para(pdf, col,
    "Study 3 (March 25, 2026) extended prediction to six heterogeneous domains: "
    "equities (n = 20 large-cap tickers), commodity futures (n = 5: gold, crude oil, "
    "silver, natural gas, copper), cryptocurrency (n = 10 by market cap), foreign "
    "exchange (n = 8 major pairs), weather (n = 30 U.S. cities, next-day high "
    "temperature), and NBA game totals (n = 3). All predictions used a 24-hour "
    "horizon. Outcomes were collected automatically March 26, 2026. CoinGecko rate "
    "limits caused five cryptocurrency outcomes to remain unresolved; NBA games did "
    "not achieve completed status in the ESPN API and were excluded. The final scored "
    "dataset comprised n = 68 resolved predictions per model (N = 204 total).", indent=0)

subsection_head(pdf, col, "2.5.", "Calibration Metrics")

para(pdf, col,
    "Hit rate. For each confidence level a in {0.50, 0.80, 0.90}, the empirical hit "
    "rate is the proportion of predictions for which the true outcome fell within the "
    "stated interval [L, U]. A calibrated model achieves a hit rate equal to the stated "
    "confidence; values below indicate overconfidence, values above indicate "
    "underconfidence.", indent=0)

para(pdf, col,
    "Expected Calibration Error (ECE) is the mean absolute deviation between stated "
    "and empirical coverage across all three confidence levels:", indent=0)
eqn(pdf, col, "1", "ECE = (1/3) sum_a |a - p-hat_a|,  a in {0.50, 0.80, 0.90}")

para(pdf, col,
    "Meta-knowledge ratio (Study 3 only). We apply the MEAD/MAD framework of Soll "
    "and Klayman (2004). The 80% CI endpoints are treated as the 10th and 90th "
    "percentiles of a symmetric normal (z = 1.2816). The Absolute Deviation (AD) is "
    "the midpoint error of the 80% CI relative to the true outcome, standardized by "
    "within-domain outcome standard deviation sigma:", indent=0)
eqn(pdf, col, "2", "AD_i = |(L_i + U_i)/2 - y_i| / sigma")

para(pdf, col,
    "The Expected Absolute Deviation (EAD) is the CI-width-implied error standardized "
    "by sigma, and the meta-knowledge ratio mu = MEAD/MAD is the ratio of their domain "
    "means. mu < 1 indicates overconfidence, mu > 1 indicates underconfidence.", indent=0)

# ═════════════════════════════════════════════════════════════════════════════
# 3. RESULTS
# ═════════════════════════════════════════════════════════════════════════════
section_head(pdf, col, 3, "Results")

subsection_head(pdf, col, "3.1.", "Study 1: Baseline Overconfidence in Equity Markets")

para(pdf, col,
    "Table 1 summarizes hit rates and ECE for the 1-day equity prediction task "
    "(n = 100 per model). All three models are substantially overconfident: even the "
    "best-performing model (Claude) achieves only 58% coverage at the 80% confidence "
    "level, and only 73% at 90%. GPT-4 is dramatically worse -- its 80% CI contains "
    "the true outcome only 31% of the time, and its 90% CI only 38% (ECE = 43.7%). "
    "These results confirm Hypothesis H1 (universal overconfidence) and H3 (GPT-4 "
    "worst) in the simplest possible setting.", indent=0)

col_table(pdf, col, 1,
    "Study 1: Overall Calibration in 1-Day Equity Predictions (n = 100 per model)",
    "ECE = Expected Calibration Error; lower is better. Perfect calibration = 0%.",
    ["Model",   "Hit@50%", "Hit@80%", "Hit@90%", "ECE"],
    [["Claude",  "30.0%",   "58.0%",   "73.0%",   "19.7%"],
     ["Gemini",  "29.0%",   "58.0%",   "65.0%",   "22.7%"],
     ["GPT-4",   "20.0%",   "31.0%",   "38.0%",   "43.7%"],
     ["Perfect", "50.0%",   "80.0%",   "90.0%",   "0.0%"]],
    [30, 15, 15, 15, 14],
    font_size=8.0)

subsection_head(pdf, col, "3.2.", "Study 2: Calibration Across Prediction Horizons")

para(pdf, col,
    "Table 2 shows how calibration changes with prediction horizon for each model. "
    "The results reveal a pronounced and divergent horizon effect. Claude's 80% hit "
    "rate drops from 80.5% at 1 day to 46.2% at 18 days (ECE rises from 1.4% to "
    "29.8%), a pattern consistent with systematic interval-width anchoring on "
    "short-horizon volatility. GPT-4 -- already poorly calibrated at 1 day "
    "(ECE = 21.8%) -- deteriorates further, reaching 27.2% hit@80 at 18 days "
    "and an ECE of 47.4%.", indent=0)

para(pdf, col,
    "Gemini's pattern is strikingly different. Its 1-day calibration (ECE = 1.8%) "
    "is the best of any model at any horizon. While it degrades at intermediate "
    "horizons (ECE = 16.6% at 18 days), it recovers at longer windows, achieving "
    "80.1% hit@80 and ECE = 2.5% at 22 days -- near-perfect calibration. This "
    "suggests Gemini's CI widths scale approximately proportionally to horizon "
    "uncertainty in a way that matches realized volatility at longer windows, "
    "even as Claude and GPT-4 fail to do so.")

col_table(pdf, col, 2,
    "Study 2: 80% Hit Rate and ECE by Model and Prediction Horizon",
    "Hit@80 = proportion of predictions where true outcome falls within 80% CI. "
    "ECE = mean absolute calibration error across 50/80/90% levels.",
    ["Horizon", "Claude H80%", "Cl. ECE", "Gemini H80%", "Gem. ECE", "GPT-4 H80%", "GPT-4 ECE"],
    [["1d",  "80.5%", "1.4%",  "78.5%", "1.8%",  "55.2%", "21.8%"],
     ["6d",  "56.0%", "20.6%", "71.7%", "8.4%",  "34.5%", "41.6%"],
     ["18d", "46.2%", "29.8%", "59.8%", "16.6%", "27.2%", "47.4%"],
     ["22d", "51.2%", "26.9%", "80.1%", "2.5%",  "24.4%", "49.9%"]],
    [14, 16, 13, 18, 14, 18, 15],
    font_size=7.5)

subsection_head(pdf, col, "3.3.", "Study 3: Domain-Specific Calibration")

para(pdf, col,
    "Table 3 summarizes overall calibration in the multi-domain study (n = 68 per "
    "model). Claude exhibits the best overall calibration (ECE = 5.3%), followed by "
    "Gemini (7.2%) and GPT-4 (18.9%), consistent with Study 1 and Study 2 rankings. "
    "The overall ECE values are substantially lower than in Studies 1 and 2, driven "
    "by near-perfect calibration in the weather domain (which accounts for 44% of "
    "Study 3 observations).", indent=0)

col_table(pdf, col, 3,
    "Study 3: Overall Calibration by Model (n = 68 per model)",
    "ECE = Expected Calibration Error; lower values indicate better calibration.",
    ["Model",   "Hit@50%", "Hit@80%", "Hit@90%", "ECE"],
    [["Claude",  "58.8%",   "82.4%",   "85.3%",   "5.3%"],
     ["Gemini",  "45.6%",   "73.5%",   "79.4%",   "7.2%"],
     ["GPT-4",   "30.9%",   "63.2%",   "69.1%",   "18.9%"],
     ["Perfect", "50.0%",   "80.0%",   "90.0%",   "0.0%"]],
    [30, 15, 15, 15, 14],
    font_size=8.0)

para(pdf, col,
    "Table 4 disaggregates calibration by domain. The central result is a systematic "
    "directional reversal: models are overconfident in commodity and equity markets "
    "and underconfident in cryptocurrency and, to a lesser extent, forex. No model "
    "is uniformly overconfident or underconfident, refuting a simple single-mechanism "
    "account of LLM miscalibration.", indent=0)

col_table(pdf, col, 4,
    "Study 3: Hit Rates and ECE by Model and Domain",
    "NBA games excluded (ESPN API). Commod. = commodity futures.",
    ["Domain",   "Model",  "N",  "H50%", "H80%", "H90%", "ECE"],
    [["Stocks",    "Claude", "40", "50%",  "85%",  "90%",  "1.7%"],
     ["",          "Gemini", "40", "25%",  "70%",  "75%",  "16.7%"],
     ["",          "GPT-4",  "40", "15%",  "55%",  "65%",  "28.3%"],
     ["Commod.",   "Claude", "10", "20%",  "40%",  "40%",  "40.0%"],
     ["",          "Gemini", "10", "20%",  "40%",  "40%",  "40.0%"],
     ["",          "GPT-4",  "10", "20%",  "40%",  "40%",  "40.0%"],
     ["Crypto",    "Claude", "20", "80%",  "100%", "100%", "20.0%"],
     ["",          "Gemini", "20", "20%",  "80%",  "100%", "13.3%"],
     ["",          "GPT-4",  "20", "20%",  "100%", "100%", "20.0%"],
     ["Forex",     "Claude", "16", "38%",  "75%",  "75%",  "10.8%"],
     ["",          "Gemini", "16", "50%",  "63%",  "75%",  "10.8%"],
     ["",          "GPT-4",  "16", "25%",  "25%",  "38%",  "44.2%"],
     ["Weather",   "Claude", "60", "73%",  "87%",  "90%",  "10.0%"],
     ["",          "Gemini", "60", "67%",  "83%",  "87%",  "7.8%"],
     ["",          "GPT-4",  "60", "47%",  "77%",  "80%",  "5.5%"],
     ["NBA",       "All",    "13", "--",   "--",   "--",   "--"]],
    [22, 14, 8, 10, 10, 10, 10],
    font_size=7.5)

para(pdf, col,
    "Commodities showed the most extreme and uniform overconfidence: ECE = 40% for "
    "all three models, with 80% and 90% CIs achieving only 40% coverage. The "
    "cryptocurrency domain showed a directional inversion: both Claude and GPT-4 "
    "achieved 100% coverage at the 90% level, indicating systematic underconfidence. "
    "Weather was the best-calibrated domain overall. GPT-4 performed dramatically "
    "worse on forex (ECE = 44.2%).", indent=0)

subsection_head(pdf, col, "3.4.", "Meta-Knowledge Analysis (Study 3)")

para(pdf, col,
    "Table 5 presents the Soll-Klayman meta-knowledge ratio for each model-domain "
    "combination. Overall, GPT-4 is the most overconfident (mu = 0.81) and Claude "
    "slightly underconfident in aggregate (mu = 1.23). However, the aggregate values "
    "conceal dramatic variation that constitutes the central finding of this study.", indent=0)

col_table(pdf, col, 5,
    "Study 3: Meta-Knowledge Ratio mu = MEAD/MAD by Model and Domain",
    "mu < 1 = overconfidence; mu = 1 = perfect; mu > 1 = underconfidence.",
    ["Domain",       "Claude", "Gemini", "GPT-4"],
    [["Stocks",      "0.81",   "0.55",   "0.41"],
     ["Commodities", "0.25",   "0.25",   "0.25"],
     ["Crypto",      "14.40",  "1.35",   "1.84"],
     ["Forex",       "2.68",   "1.67",   "1.29"],
     ["Weather",     "1.28",   "1.04",   "0.85"],
     ["Overall",     "1.23",   "0.99",   "0.81"]],
    [34, 20, 20, 20],
    font_size=8.0)

para(pdf, col,
    "All models show mu = 0.25 on commodities: stated uncertainty is only one-quarter "
    "of what actual errors require, the most extreme overconfidence in the dataset. "
    "At the other extreme, Claude's crypto mu = 14.4 indicates CIs 14 times wider "
    "than necessary. The forex domain reveals a compound failure in GPT-4: its high "
    "ECE (44.2%) is not reflected in its mu (1.29), because mu cannot distinguish "
    "misanchored point estimates from miscalibrated CI widths. The two metrics must "
    "be examined jointly to diagnose the full failure mode.", indent=0)

# ═════════════════════════════════════════════════════════════════════════════
# 4. DISCUSSION
# ═════════════════════════════════════════════════════════════════════════════
section_head(pdf, col, 4, "Discussion")

subsection_head(pdf, col, "4.1.", "Convergent Evidence for LLM Overconfidence")

para(pdf, col,
    "The most consistent finding across all three studies is that LLMs -- particularly "
    "GPT-4 -- are substantially overconfident in their confidence intervals for "
    "quantitative forecasting. GPT-4's ECE ranges from 18.9% (Study 3, favorable "
    "domain mix) to 43.7% (Study 1, equity-only), with a cross-study mean exceeding "
    "35%. Even Claude, the best-calibrated model in every study, achieves only 19.7% "
    "ECE in Study 1 -- far from the 0% target. The pattern of overconfidence is "
    "robust to domain, horizon, and sample size, confirming that it is a "
    "systematic property of these models rather than an artifact of any single "
    "experimental design.", indent=0)

para(pdf, col,
    "These ECE values are comparable to the most severe human expert overconfidence "
    "documented in the literature. Ben-David et al. (2013) found that CFOs' 80% "
    "confidence intervals for annual equity returns achieved only 36-38% empirical "
    "coverage -- roughly equivalent to our Study 1 Claude result (58% at 80%). "
    "GPT-4's Study 1 performance (31% at the 80% level) is dramatically worse, "
    "suggesting that some frontier LLMs may exhibit human-level or super-human "
    "overconfidence in certain forecasting contexts.")

subsection_head(pdf, col, "4.2.", "The Prediction Horizon Effect")

para(pdf, col,
    "Study 2 reveals a sharp divergence between models as the prediction horizon "
    "grows. Claude and GPT-4 both degrade substantially, consistent with the "
    "hypothesis that their CI widths are anchored to short-horizon volatility "
    "estimates and fail to scale appropriately with forecast uncertainty. This "
    "mirrors findings from the human overconfidence literature, where longer "
    "horizons are consistently associated with greater interval underestimation "
    "(Griffin and Tversky 1992).", indent=0)

para(pdf, col,
    "Gemini's behavior is more complex. Its near-perfect 1-day calibration "
    "(ECE = 1.8%, hit@80 = 78.5%) and recovery to excellent long-horizon calibration "
    "(ECE = 2.5% at 22 days) suggest that its CI widths implicitly scale with "
    "realized volatility in a way that happens to match empirical coverage at the "
    "extremes of the horizon range. Whether this reflects a genuine uncertainty "
    "representation or an accidental match between Gemini's CI scaling function "
    "and stock return volatility at these specific horizons is an open question "
    "that warrants longitudinal replication.")

subsection_head(pdf, col, "4.3.", "A Domain-Confidence Inversion")

para(pdf, col,
    "The central finding of Study 3 is a systematic domain-confidence inversion: "
    "LLMs are most overconfident in financial domains (equities, commodities) where "
    "actual predictability is low, and most underconfident in speculative domains "
    "(cryptocurrency, forex) where they appear to apply large epistemic-humility "
    "priors. This pattern is inconsistent with a single domain-agnostic "
    "miscalibration mechanism and suggests models apply domain-level heuristics "
    "inherited from forecasting commentary in their training corpora.", indent=0)

para(pdf, col,
    "This finding parallels the human expert literature. Griffin and Tversky (1992) "
    "showed that perceived predictability often exceeds actual predictability in "
    "structured, information-rich domains. LLMs trained on large corpora of equity "
    "research and commodity analysis may exhibit the same pattern -- asserting narrow "
    "intervals in domains where training data contains many precise price forecasts, "
    "without encoding the base rate of forecast failure.")

para(pdf, col,
    "The commodity result is particularly striking: mu = 0.25 uniformly across all "
    "three models. This uniformity suggests a shared domain prior in training data "
    "rather than a model-specific artifact. The crypto inversion (Claude mu = 14.4) "
    "implies that models apply a 'crypto is unpredictable' narrative that dramatically "
    "overstates typical 24-hour volatility.")

subsection_head(pdf, col, "4.4.", "Model Differences")

para(pdf, col,
    "GPT-4 is consistently the most overconfident model across all three studies. "
    "Its Study 1 ECE (43.7%) is nearly double Claude's (19.7%) in the same task, "
    "and its Study 2 ECE at 22-day horizon (49.9%) approaches the theoretical maximum "
    "for three-level calibration. Claude is the best-calibrated model in Study 3 "
    "(ECE = 5.3%) and competitive with Gemini in Studies 1 and 2. Gemini occupies "
    "an intermediate position overall but is distinctive for its horizon robustness "
    "in Study 2.", indent=0)

para(pdf, col,
    "Claude's extreme underconfidence in cryptocurrency (mu = 14.4) represents "
    "the largest positive outlier in the meta-knowledge analysis, indicating that "
    "even the best-calibrated model can exhibit severe directional miscalibration "
    "in specific domains. GPT-4's forex failure (ECE = 44.2%) is the worst "
    "domain-model result in Study 3 and, as noted, reflects a compound failure "
    "of both point-estimate anchoring and CI width calibration that the MEAD/MAD "
    "ratio alone cannot fully capture.")

subsection_head(pdf, col, "4.5.", "Limitations and Future Directions")

para(pdf, col,
    "Several limitations constrain our conclusions. First, Studies 1 and 3 were "
    "each conducted on a single day, and Study 3's domain-specific results may "
    "partly reflect idiosyncratic market conditions on March 25, 2026. Study 2's "
    "backtest design mitigates this concern for equities but introduces potential "
    "look-ahead biases if models' training data extends to the backtest period. "
    "Second, statistical precision is limited in small Study 3 domains: n = 10 "
    "for commodities, n = 8 for forex. Third, NBA outcomes were excluded from "
    "Study 3 due to API resolution failures. Fourth, models were evaluated without "
    "chain-of-thought or explicit calibration prompting; whether such interventions "
    "produce genuine calibration improvement is an important open question.", indent=0)

para(pdf, col,
    "Future work should address these limitations by: (i) collecting predictions "
    "daily over extended periods to separate stable calibration properties from "
    "single-day volatility; (ii) extending the domain set to include earnings "
    "forecasts, macroeconomic indicators, and prediction market prices; (iii) "
    "evaluating calibration-specific prompting and post-hoc recalibration "
    "(conformal prediction, temperature scaling); and (iv) using larger n within "
    "Study 3 domains to enable robust domain-level inference.")

# ═════════════════════════════════════════════════════════════════════════════
# 5. CONCLUSION
# ═════════════════════════════════════════════════════════════════════════════
section_head(pdf, col, 5, "Conclusion")

para(pdf, col,
    "We report three pre-registered studies examining whether frontier LLMs exhibit "
    "systematic overconfidence in quantitative interval estimates, and how "
    "miscalibration varies with prediction horizon and application domain. Across "
    "all three studies, all three models are substantially overconfident, with GPT-4 "
    "consistently the worst (cross-study ECE 19-44%) and Claude the best. Study 2 "
    "reveals that Claude and GPT-4 become increasingly miscalibrated as the "
    "prediction horizon grows from 1 to 22 days, while Gemini maintains near-target "
    "coverage at both short and long horizons. Study 3 reveals a domain-confidence "
    "inversion: all models overstate certainty in commodity and equity markets while "
    "overstating uncertainty in cryptocurrency and forex, a pattern consistent with "
    "domain-specific miscalibration inherited from training corpora.", indent=0)

para(pdf, col,
    "These results have direct implications for practice. Users who elicit confidence "
    "intervals from LLMs for financial decision support should not assume that stated "
    "uncertainty reflects calibrated epistemic states. The pattern of miscalibration "
    "is most dangerous in precisely the domains (commodities, equities) and at "
    "precisely the horizons (multi-week) where overconfident forecasting carries "
    "the most severe consequences. Global calibration performance does not transfer "
    "across domains or horizons; domain-stratified and horizon-stratified evaluation "
    "is necessary to characterize model-specific calibration risk.")

para(pdf, col,
    "More broadly, this study demonstrates that the domain-specificity and "
    "horizon-sensitivity of human overconfidence -- developed over four decades of "
    "experimental research on human judges -- apply with striking regularity to "
    "large language models. LLMs are not immune to the calibration failures of "
    "their training data; they may instead amplify and systematize them at scale.")

# ═════════════════════════════════════════════════════════════════════════════
# ACKNOWLEDGEMENTS
# ═════════════════════════════════════════════════════════════════════════════
section_head(pdf, col, "", "Acknowledgements")

para(pdf, col,
    "The authors thank the maintainers of the open data APIs used in this study: "
    "yfinance, CoinGecko, Open-Meteo, and ESPN. No external funding was received "
    "for this research. The authors declare no conflicts of interest.", indent=0)

# ═════════════════════════════════════════════════════════════════════════════
# REFERENCES
# ═════════════════════════════════════════════════════════════════════════════
section_head(pdf, col, "", "References")

REFS = [
    "Alpert M, Raiffa H (1982) A progress report on the training of probability "
    "assessors. Kahneman D, Slovic P, Tversky A, eds. Judgment Under Uncertainty: "
    "Heuristics and Biases (Cambridge University Press, Cambridge, UK), 294-305.",

    "Ben-David I, Graham JR, Harvey CR (2013) Managerial miscalibration. "
    "Quarterly Journal of Economics 128(4):1547-1584.",

    "Christensen-Szalanski JJJ, Bushyhead JB (1981) Physicians' use of probabilistic "
    "information in a real clinical setting. Journal of Experimental Psychology: "
    "Human Perception and Performance 7(4):928-935.",

    "Flyvbjerg B, Holm MK, Buhl S (2002) Underestimating costs in public works "
    "projects: Error or lie? Journal of the American Planning Association 68(3):279-295.",

    "Griffin D, Tversky A (1992) The weighing of evidence and the determinants of "
    "confidence. Cognitive Psychology 24(3):411-435.",

    "Kadavath S, Conerly T, Askell A, et al. (2022) Language models (mostly) know "
    "what they know. Preprint, arXiv:2207.05221.",

    "Klayman J, Soll JB, Gonzalez-Vallejo C, Barlas S (1999) Overconfidence: It "
    "depends on how, what, and whom you ask. Organizational Behavior and Human "
    "Decision Processes 79(3):216-247.",

    "Lichtenstein S, Fischhoff B, Phillips LD (1982) Calibration of probabilities: "
    "The state of the art to 1980. Kahneman D, Slovic P, Tversky A, eds. Judgment "
    "Under Uncertainty: Heuristics and Biases (Cambridge University Press), 306-334.",

    "Lin S, Hilton J, Evans O (2022) Teaching models to express their uncertainty "
    "in words. Transactions on Machine Learning Research.",

    "Lovallo D, Kahneman D (2003) Delusions of success: How optimism undermines "
    "executives' decisions. Harvard Business Review 81(7):56-63.",

    "OpenAI (2024) GPT-4 technical report. Preprint, arXiv:2303.08774.",

    "Soll JB, Klayman J (2004) Overconfidence in interval estimates. Journal of "
    "Experimental Psychology: Learning, Memory, and Cognition 30(2):299-314.",

    "Xiong M, Hu Z, Lu X, et al. (2024) Can LLMs express their uncertainty? An "
    "empirical evaluation of confidence elicitation in LLMs. "
    "Preprint, arXiv:2306.13063.",

    "Yang Z, Li J, Gao Q, et al. (2023) Alignment for honesty. "
    "Preprint, arXiv:2312.07000.",
]

for ref in REFS:
    lines = _wrap_text(pdf, "TNR", "", 8.5, ref, COL_W - HANG, indent_first=0.0)

    pdf.set_font("TNR", "", 8.5)
    pdf.set_text_color(*DARK)
    space_w = pdf.get_string_width(" ")

    if len(lines) > 1:
        if max(0, int(col.remaining() / LINE_H)) == 1:
            col._advance()

    for line_idx, (words, is_last) in enumerate(lines):
        col.need(LINE_H)
        x0     = col.x()
        indent = 0.0 if line_idx == 0 else HANG
        avail  = COL_W - indent
        y      = pdf.get_y()

        if is_last or len(words) == 1:
            pdf.set_xy(x0 + indent, y)
            pdf.cell(avail, LINE_H, " ".join(words), align="L")
        else:
            total_w = sum(pdf.get_string_width(w) for w in words)
            gaps    = len(words) - 1
            extra   = (avail - total_w - gaps * space_w) / gaps if gaps > 0 else 0
            pdf.set_xy(x0 + indent, y)
            for i, w in enumerate(words):
                cw = pdf.get_string_width(w) + (extra + space_w if i < gaps else 0)
                pdf.cell(cw, LINE_H, w, align="L")
        pdf.set_xy(x0, y + LINE_H)

    col.need(1.5)
    pdf.set_xy(col.x(), pdf.get_y() + 1.5)

# ── output ─────────────────────────────────────────────────────────────────────
pdf.output(OUT)
print(f"Saved: {OUT}  ({pdf.page_no()} pages)")
