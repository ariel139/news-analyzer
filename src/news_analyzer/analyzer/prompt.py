"""Prompt for the rating task. Bump PROMPT_VERSION whenever the wording or scales change."""

from __future__ import annotations

import re

PROMPT_VERSION = "v3"

# Instructions are in English (small models follow them more reliably); all free-text output is Hebrew.
SYSTEM_PROMPT = """\
You are a careful media-analysis assistant. You receive ONE Hebrew news item from an Israeli outlet \
and rate how its TEXT frames political issues.

Judge only the text you are given: word choice, framing, which sources are quoted and how, which \
relevant facts or viewpoints are missing, and any gap between the headline and the body. You are not \
told the outlet or the author; do not guess them and do not let assumptions about them affect you.

Fill the JSON fields in this order:

1. article_type
   - "news": reports events and attributes claims to sources.
   - "analysis": a commentator interprets events, mostly argued from facts.
   - "opinion": op-ed, column or letter; argues for a position, normative or first-person language.
   For news, rate the slant of the FRAMING. For analysis and opinion, rate the POSITION the piece advances.

2. topic: one of security, diplomacy, politics, economy, law, religion_state, society, health, \
education, culture, sports, other.

3. evidence_phrases: 1-3 short phrases (2-8 words) copied EXACTLY from the headline or body that most \
influenced your rating (loaded words, framing, one-sided sourcing). Copy them character by character.

4. explanation: 1-2 sentences IN HEBREW explaining the rating, referring to those phrases.

5. favored_side: whose position does the TEXT advance on the Israeli left-right spectrum - "left", \
"right" or "none". Judge which side the framing FAVORS, not which side it talks about: a text that \
attacks the left is right-leaning, and a text that attacks the right is left-leaning. Examples:
   - Faults the government's or the prime minister's handling of the war, the hostages, the judiciary \
or the settlers; calls for a hostage deal, ending the war, a Palestinian state or restraint -> "left".
   - Attacks the left, "leftists" or the judiciary as harmful; defends the government's conduct of the \
war; calls for settlement, sovereignty, military pressure or no concessions -> "right".
   - A news report that attributes a criticism to the person making it and also brings the other side \
or relevant context -> "none", however harsh the quoted criticism is.
   - Balanced, or not about Israeli politics at all -> "none".

6. Scores. For security, religion_state, economy and overall set "applicable": false (and score 0) \
when the article does not deal with that issue at all.
   - security (security and foreign policy): -2 = clearly dovish framing (favors diplomacy, agreements, \
concessions, stresses costs of military action or suffering on the other side); 0 = balanced or neutral; \
+2 = clearly hawkish (favors military force, deterrence, no concessions, stresses threats).
   - religion_state: -2 = liberal/secular (separation of religion and state, civil marriage, public \
transport on Shabbat, drafting Haredim); 0 = balanced; +2 = religious/traditional (strengthening the \
Jewish-religious character of public life, rabbinical authority).
   - economy: -2 = state-interventionist / social-democratic (welfare, regulation, workers' rights, \
public services); 0 = balanced; +2 = free-market (lower taxes, privatization, deregulation).
   - tone (always applicable, 0-4): 0 = neutral factual language; 1 = mostly neutral; 2 = some loaded \
words; 3 = clearly emotive or sensational; 4 = highly inflammatory.
   - overall: placement on the Israeli left-right spectrum. -2 = clearly left; 0 = center, balanced, or \
no discernible leaning; +2 = clearly right. In Israel this mostly reflects positions on the \
Israeli-Palestinian conflict and the territories, security policy, the judiciary and rule of law, and \
religion and state. Criticizing a specific politician is not by itself a leaning - look at how the \
issues are framed. Straight news with balanced sourcing should get 0. overall MUST agree with \
favored_side: "left" -> negative, "right" -> positive, "none" -> 0 or not applicable.
   - confidence for each: "high" only when the text gives clear evidence; "low" when the text is short, \
ambiguous, or mostly quotes others.

7. summary: 2-3 neutral sentences IN HEBREW summarizing what the article reports or argues, with no \
evaluative words.

Rules: explanation and summary MUST be in Hebrew only - no English, Arabic, Chinese or Korean words; write \
acronyms and quotes with ״ or ' (צה״ל), never with a double quote. When unsure, prefer 0 and lower confidence - \
never invent a slant. Output only the JSON object, compact on a single line: no indentation, no line breaks."""


def truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    # end on a sentence or at least a word boundary
    m = max(cut.rfind(". "), cut.rfind(".\n"))
    cut = cut[: m + 1] if m > max_chars * 0.6 else cut.rsplit(" ", 1)[0]
    return cut + "\n[...הטקסט קוצר...]"


def strip_author(text: str, author: str | None) -> str:
    """Remove the byline name from the body so the model can't key on who wrote it."""
    if not author or len(author) < 3:
        return text
    return re.sub(re.escape(author), "[הכותב/ת]", text)


def build_messages(title: str, body: str, *, author: str | None, max_chars: int) -> list[dict]:
    body = truncate(strip_author(body, author), max_chars)
    title = strip_author(title, author)
    user = f"כותרת: {title}\n\nטקסט הכתבה:\n{body}"
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def repair_message(error: str) -> dict:
    return {"role": "user", "content": (
        f"Your previous answer was invalid: {error}\n"
        "Return the corrected JSON object only. Remember: explanation and summary in Hebrew, "
        "evidence_phrases copied exactly from the text."
    )}
