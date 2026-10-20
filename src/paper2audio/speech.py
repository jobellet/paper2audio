"""Make cleaned text pleasant for a TTS engine (abbreviations, symbols, units)."""

from __future__ import annotations

import re

from .cleaning import Rule, rule

SPEECH_RULES: list[Rule] = [
    rule("eg", r"\be\.\s?g\.,?", "for example,"),
    rule("ie", r"\bi\.\s?e\.,?", "that is,"),
    rule("cf", r"\bcf\.", "compare"),
    rule("etc", r"\betc\.(?=\s+[a-z])", "etcetera"),
    rule("et_al", r"\bet al\.", "et al"),
    rule("vs", r"\bvs?\.", "versus"),
    rule("approx", r"\bapprox\.", "approximately"),
    rule("resp", r"\bresp\.", "respectively"),
    rule("fig", r"\bFigs?\.\s?", "Figure "),
    rule("eq", r"\bEqs?\.\s?", "Equation "),
    rule("sec", r"\bSect?\.\s?", "Section "),
    rule("ref", r"\bRefs?\.\s?", "reference "),
    rule("no", r"\bNo\.\s?(?=\d)", "number "),
    rule("exponent", r"10\^\s?[-−–](\d+)", r"10 to the minus \1"),
    rule("exponent_pos", r"10\^\s?(\d+)", r"10 to the \1"),
    rule("per_second", r"\bs\^[-−–]1\b", "per second"),
    rule("per_unit", r"\b([A-Za-z]+)\^[-−–]1\b", r"per \1"),
    rule("squared", r"\^2\b", " squared"),
    rule("cubed", r"\^3\b", " cubed"),
    rule("plus_minus", r"\s?±\s?", " plus or minus "),
    rule("approx_sym", r"\s?[~≈∼]\s?(?=\d)", " approximately "),
    rule("leq", r"\s?≤\s?", " less than or equal to "),
    rule("geq", r"\s?≥\s?", " greater than or equal to "),
    rule("lt", r"(?<=\s)<\s?(?=\d)", "less than "),
    rule("gt", r"(?<=\s)>\s?(?=\d)", "greater than "),
    rule("times", r"(?<=\d)\s?[×]\s?(?=\d)", " by "),
    # "2–5", "1st–99th"; not product codes like "GS3-U3-41C6"
    rule("range", r"(?<![A-Za-z\-])(\d+(?:\.\d+)?(?:st|nd|rd|th)?)\s?[-–]\s?(?=\d+(?:\.\d+)?(?:st|nd|rd|th)?(?![\w-]))",
         r"\1 to "),
    rule("minus", r"(?<![\w)])[−–]\s?(?=\d)", "minus "),
    rule("deg_per_s", r"(?<=\d)\s?(?:°|deg)\s?/\s?s\b", " degrees per second"),
    rule("degrees", r"(?<=\d)\s?(?:°|deg\b)", " degrees"),
    rule("percent", r"(?<=\d)\s?%", " percent"),
    rule("ms", r"(?<=\d)\s?ms\b", " milliseconds"),
    rule("hz", r"(?<=\d)\s?Hz\b", " hertz"),
    rule("khz", r"(?<=\d)\s?kHz\b", " kilohertz"),
    rule("cdm2", r"(?<=\d)\s?cd\s?/\s?m\s?2\b", " candela per square meter"),
    rule("mm", r"(?<=\d)\s?mm\b", " millimeters"),
    rule("cm", r"(?<=\d)\s?cm\b", " centimeters"),
    rule("mus", r"(?<=\d)\s?[μµ]s\b", " microseconds"),
    rule("mum", r"(?<=\d)\s?[μµ]m\b", " micrometers"),
    rule("ampersand", r"\s&\s", " and "),
    rule("small_caps_sections", r"\b(INTRODUCTION|METHODS|RESULTS|DISCUSSION|APPENDIX)\b", lambda m: m.group(1).capitalize()),
    rule("bullets", r"[•▪■◆►]", ", "),
]


def to_speech(text: str, rules: list[Rule] = SPEECH_RULES) -> str:
    for r in rules:
        text = r.apply(text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()
