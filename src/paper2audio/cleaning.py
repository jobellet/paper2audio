"""Text-level clean-up: remove things nobody wants read aloud.

Each rule has a name so that journal profiles can disable or add rules.
Rules run in list order.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Callable, Union

Repl = Union[str, Callable[[re.Match], str]]


@dataclass(frozen=True)
class Rule:
    name: str
    pattern: re.Pattern
    repl: Repl = ""

    def apply(self, text: str) -> str:
        return self.pattern.sub(self.repl, text)


def rule(name: str, pattern: str, repl: Repl = "", flags: int = 0) -> Rule:
    return Rule(name, re.compile(pattern, flags), repl)


# --------------------------------------------------------------------------- statistics

_STAT_NAME = r"(?:p|P|t|F|r|R2|R²|z|Z|U|W|H|d|g|b|B|β|η2|η²|ηp2|η²p|ω2|ω²|χ2|χ²|BF(?:01|10)?|OR|RR|HR|CI|SD|SEM|SE|M|Mdn|df|N|n|k|τ|ρ|κ|Q|T|V|X2|AIC|BIC|LL)"
_NUM_VAL = r"[-−–]?\s?(?:\d+(?:[.,]\d+)?|\.\d+)(?:\s?(?:[×x]|e)\s?10\^?[-−]?\d+|e[-−]?\d+)?\s?%?"
_STAT = (
    rf"(?<![A-Za-z]){_STAT_NAME}"
    r"(?:\s?\(\s?[\d.,\s]+\))?"  # degrees of freedom: t(23), F(1, 40)
    rf"\s?(?:[=<>≤≥≈]|&lt;|&gt;)\s?{_NUM_VAL}"
    r"(?:\s?(?:\[[^\]]{0,40}\]|\([^()]{0,40}\)))?"  # CI [0.1, 0.4]
)
_STAT_RE = re.compile(_STAT)
_CI_RE = re.compile(r"\d{2}\s?%\s?(?:CI|confidence interval)s?\s?[:=]?\s?[\[(][^\])]{0,50}[\])]", re.I)


_ASSIGNMENT = re.compile(r"(?:[=<>≤≥≈]|&lt;|&gt;)\s?[-−–]?\s?\.?\d")
_KEEP_SEGMENT = re.compile(r"^\s*[nN]\s?=\s?\d[\d,]*\s*$")  # "(n = 12; 7 female)"
_FIG_SEGMENT = re.compile(
    r"^\s*(?:see,? |cf\. |e\.g\.,? |compare )?(?:(?:Supplementary|Suppl\.|Extended Data|Supporting)\s)?"
    r"(?:Fig(?:ure)?s?\.?|Tables?|Movies?|Videos?|Eqs?\.?|Equations?|Box(?:es)?|Appendix)\s?[S]?\d", re.I)


def _strip_stat_parentheticals(m: re.Match) -> str:
    """Drop the statistical and figure-pointer parts of a parenthetical.

    '(mean: r = 0.01, z = 0.59; Fig. 1D)' -> ''
    '(alpha = 0.05)' -> ''          '(n = 12; 7 female)' -> unchanged
    """
    whole = m.group(0)
    opener, closer = whole[0], whole[-1]
    segments = whole[1:-1].split(";")
    kept = [seg for seg in segments
            if _KEEP_SEGMENT.match(seg)
            or not (_ASSIGNMENT.search(seg) or _CI_RE.search(seg) or _FIG_SEGMENT.match(seg))]
    if len(kept) == len(segments):
        return whole
    return f"{opener}{';'.join(kept).strip()}{closer}" if kept else ""


# Outside parentheses we only remove unambiguous statistics: p values, Bayes
# factors, and test statistics that carry degrees of freedom ("t(23) = 2.1").
# A bare "t = 0" or "n = 12" may be ordinary prose and is kept.
_INLINE_STAT = (
    r"(?<![A-Za-z])(?:"
    rf"(?:p|P|BF(?:01|10)?)\s?(?:[=<>≤≥]|&lt;|&gt;)\s?{_NUM_VAL}"
    rf"|(?:t|F|z|χ2|χ²|U|W|H|r)\s?\(\s?[\d.,\s]+\)\s?=\s?{_NUM_VAL}"
    r")"
)

# --------------------------------------------------------------------------- citations

_NAME = r"(?:(?:[A-Z]\.\s?)?(?:[Vv]an |[Vv]on |[Dd]e |[Dd]er |[Dd]en |[Ll]a |[Ll]e |[Dd]i |[Dd]a |[Dd]u |dos |[Dd]el |Mc|Mac|O['’])*[A-Z][\w'’\-]+(?:- [A-Z][\w'’\-]+)?)"  # "Perez- Nieves": a name split at a line end
_AUTHORS = rf"{_NAME}(?:(?: et al\.?)|(?:,? (?:and|&) {_NAME})|(?:, {_NAME})*(?:,? (?:and|&) {_NAME})?)?"
_YEARS = r"(?:\d{4}[a-z]?|in press|submitted|n\.d\.)(?:\s?[,;]\s?(?:\d{4}[a-z]?|in press))*"
_CITE = rf"(?:(?:see|e\.g\.|i\.e\.|cf\.|but see|see also|reviewed in|for (?:a )?review(?:s)?,? see)[,:]?\s+)?{_AUTHORS},?\s+{_YEARS}(?:,\s?(?:p|pp)\.\s?\d+(?:[-–]\d+)?)?"
_CITE_PAREN = rf"\(\s?{_CITE}(?:\s?;\s?{_CITE})*\s?\)"
_CITE_ONLY = re.compile(rf"^\s*{_CITE}\s*$")


def _strip_citation_segments(m: re.Match) -> str:
    """'(vlPFC; Romanski and Diehl, 2011)' -> '(vlPFC)'; all-citation groups vanish."""
    segments = m.group(1).split(";")
    kept = [s.strip() for s in segments if not _CITE_ONLY.match(s)]
    if len(kept) == len(segments):
        return m.group(0)
    return f" ({'; '.join(kept)})" if kept else ""


_BRACKET_NUMBERS = re.compile(r"(?:(?<=[,;\s])|^)\d{1,3}(?:\s*[,–-]\s*\d{1,3})*(?=\s*[,;]|\s*$)")
_BRACKET_LEAD = re.compile(
    r"^(?:see|cf\.?|e\.g\.|i\.e\.|for (?:example|instance)|similar to|discussed in|but see|see also|reviewed in)"
    r"(?:[,\s]+(?:e\.g\.|for (?:example|instance)))?$", re.I)
_BRACKET_FIGURE = re.compile(r"^(?:see\s+)?(?:Supp(?:lementary|\.)?\s+)?(?:Figs?\.?|Figure|Table|Equation)s?\s*\S*\d", re.I)


_PANEL_PLACE = re.compile(r"^(?:top|bottom|middle|upper|lower|left|right|centre|center)(?:[- ](?:left|right|middle|centre|center))?$", re.I)


def _bracket_citation(m: re.Match) -> str:
    """'[DSA, 47]' -> ' (DSA)'; '[similar to 47]' and '[see, 47, for the details]' lose the numbers.

    Brackets that carry no reference number ("[x0, y0] = [0, 1]") are left alone.
    """
    content = m.group(1)
    if len(re.findall(r"[A-Za-z]", content)) < 2:
        return m.group(0)  # a range or a vector ("[10^-6, 10]"); plain numeric citations go in numeric_citation
    cleaned = _BRACKET_NUMBERS.sub("", content)
    if cleaned == content:
        return m.group(0)
    segments = [seg.strip() for seg in re.split(r"[,;]", cleaned)]
    segments = [seg for seg in segments if seg and not _BRACKET_FIGURE.match(seg) and not _PANEL_PLACE.match(seg)]
    cleaned = ", ".join(segments)
    cleaned = re.sub(r"\s+(?:of|and|or)$", "", cleaned)
    cleaned = re.sub(r"^(?:see|cf\.)[, ]+(?=for\b)", "", cleaned, flags=re.I)
    cleaned = re.sub(r"^(see|cf\.),\s*(?=section\b)", r"\1 ", cleaned, flags=re.I)
    if not re.search(r"[A-Za-z]{2,}", cleaned) or _BRACKET_LEAD.match(cleaned):
        return ""
    return f" ({cleaned})"


_MATH_WORD_LIST = {"log", "exp", "sin", "cos", "tan", "tanh", "max", "min", "argmax", "argmin", "softmax", "sign", "diag",
                   "arg", "lim", "sup", "inf", "det", "var", "cov", "mod", "deg", "minus", "plus", "times", "equals"}


def _equation_like(text: str) -> bool:
    """A formula: it has a relation sign and no word of its own."""
    return (re.search(r"[=∼≈∈≥≤<>]", text) is not None
            and not any(w.lower() not in _MATH_WORD_LIST for w in re.findall(r"[A-Za-z]{6,}", text)))


def _strip_leading_equation(m: re.Match) -> str:
    """'τ∗ = ω(β) ⋅ xmed, where xmed is ...' -> 'Where xmed is ...' (the display equation, run into its sentence)."""
    if not _equation_like(m.group("eq")):
        return m.group(0)
    return "Where"


GENERIC_RULES: list[Rule] = [
    # --- identifiers & links
    rule("doi", r"(?:https?://(?:dx\.)?doi\.org/|\bdoi:\s?|\bDOI:?\s?)?\b10\.\d{4,9}/[^\s,;)\]—]*[^\s,;)\].—]"),
    rule("url", r"(?:\bhttps?://|\bwww\.)[^\s,;)\]]*[^\s,;)\].]"),
    rule("email", r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    rule("orcid", r"\b(?:ORCID:?\s?)?\d{4}-\d{4}-\d{4}-\d{3}[\dX]\b"),
    rule("arxiv_id", r"\barXiv:\s?\d{4}\.\d{4,5}(?:v\d+)?(?:\s?\[[\w.-]+\])?", flags=re.I),
    # --- citations
    rule("numeric_citation", r"\s?\[\s?\d+(?:\s?[-–,]\s?\d+)*\s?\]",
         lambda m: m.group(0) if re.search(r"[∈=∼≈]\s*$", m.string[:m.start()]) else ""),  # "n ∈ [100, 250]" stays
    rule("bracket_citation_with_text", r"\s?\[([^\[\]]{1,300})\]", _bracket_citation),
    # what is left of "(for example, [12])", "(but see [94])", "(see [3] for a review)" once the numbers are gone
    rule("dangling_citation_lead", r"\s?\((?:for (?:example|instance)|e\.g\.|i\.e\.|see(?: also)?|but see|though see|cf\.|reviewed in)[,;:]?\s*\)",
         flags=re.I),
    rule("dangling_see_for", r"(?:\s?[;,]\s?|\s?\()(?:see|reviewed in)(?: also)? for (?:an? )?(?:[a-z]+ )?(?:review|overview|summary|details|discussion)s?\)",
         lambda m: ")" if not m.group(0).lstrip().startswith("(") else "", flags=re.I),
    rule("glossary_reference", r"\s?\((?:see )?Glossary\)"),
    rule("refs_parenthetical", r"\s?\((?:see |cf\. )?refs?\.\s?\d+(?:\s?(?:[-–,]|and)\s?\d+)*\)", flags=re.I),
    rule("author_year_citation", _CITE_PAREN),
    rule("mixed_citation_parenthetical", r"\s?\(([^()]{0,600})\)", _strip_citation_segments),
    rule("author_year_in_brackets", rf"\[\s?{_CITE}(?:\s?;\s?{_CITE})*\s?\]"),
    rule("narrative_citation_year", rf"(et al\.?|{_NAME})\s?\(\s?(?:\d{{4}}[a-z]?|in press)(?:\s?[,;]\s?\d{{4}}[a-z]?)*\s?\)", r"\1"),
    # --- statistics
    rule("confidence_interval", rf",?\s?{_CI_RE.pattern}", flags=re.I),
    # one level of nesting allowed: "(Kruskal-Wallis, H(2) = 11.4, ε² = 0.12)"
    rule("stat_parenthetical", r"[(\[](?:[^()\[\]]|\([^()]{0,40}\)|\[[^\[\]]{0,40}\]){0,300}[)\]]",
         _strip_stat_parentheticals),
    rule("inline_stats", rf"[,;]?\s?{_INLINE_STAT}(?:\s?[,;]\s?(?:{_STAT}))*"),
    # --- references to figures, tables, equations, supplements
    rule(
        "figure_reference",
        r"\s?\((?:also,? )?(?:see,? |cf\. |e\.g\.,? )?(?:(?:Supplementary|Supp?l?\.|Extended Data|Supporting)\s)?(?:Fig(?:ure)?s?\.?|Tables?|Movies?|Videos?|Eqs?\.?|Equations?|Box|Appendix|Note|Data|Information|Section|Sect?\.|§)\s?[S]?[\dA-Z][^()]{0,60}\)",
    ),
    rule("supplementary_reference", r"\s?\((?:see )?(?:Supplementary|Suppl\.|Supporting) (?:Information|Material|Materials|Text|Methods|Note|Notes)[^()]{0,30}\)"),
    rule("equation_number", r"\s+\(\d{1,3}[a-z]?\)\s*$"),
    # --- typographic leftovers
    rule("footnote_marks", r"(?<=\w)[*†‡§¶]+"),
    # "See (Fig. S10) for N-DMS results." once the reference is gone
    rule("dangling_see_sentence", r"(?:(?<=[.!?]\s)|^)See\s+(?:also\s+)?for\s[^.]{0,80}\.\s?"),
    rule("leading_equation", r"^(?P<eq>\S{1,30}(?:\s+\S{1,30}){1,9}?),?\s+where\b", _strip_leading_equation),
    # "... parameters set as σ = 10, ρ = 28, and β =." : the last formula was a display equation
    rule("trailing_equation", r",?\s+(?:and\s+)?[^\W\d_]\w?\s?[=∈]\s?(?=\.(?:\s|$))"),
    rule("empty_brackets", r"\s?[(\[]\s*[,;]?\s*[)\]]"),
]

TIDY_RULES: list[Rule] = [
    rule("space_before_punct", r"\s+([,.;:!?)])", r"\1"),
    rule("space_after_open", r"([(\[])\s+", r"\1"),
    rule("double_punct", r"([,;:])\s*([,;:.])", r"\2"),
    rule("comma_period", r",\s*\.", "."),
    rule("multi_space", r"[ \t]{2,}", " "),
]


def normalize_unicode(text: str) -> str:
    # NFKC turns ligatures (ﬁ, ﬂ) and full-width chars into plain letters
    # but would also flatten super/subscripts; that is fine for speech.
    text = unicodedata.normalize("NFKC", text)
    text = re.sub("(?<=\\d)\\s?[\u030a\u02da]", "°", text)  # "10 ̊" (a ring accent after a number) is 10°
    # accents that did not compose with a letter (r̂, σ̂, μˆ) land on the wrong neighbour: "estimatê σ"
    text = re.sub("[\u0300-\u036f\u02c6]", "", text)
    # control characters and private-use glyphs (symbol fonts without a Unicode mapping)
    text = "".join(c for c in text if c in "\n\t" or unicodedata.category(c) not in ("Cc", "Co"))
    text = text.replace("­", "").replace("​", "")
    return text


def apply_rules(text: str, rules: list[Rule]) -> str:
    for r in rules:
        text = r.apply(text)
    for r in TIDY_RULES:
        text = r.apply(text)
    return text.strip()
