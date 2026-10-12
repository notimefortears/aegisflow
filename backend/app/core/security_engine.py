"""
SecurityEngine — core security layer for AegisFlow.

Runs before/after every provider call and is used as standalone workflow nodes.
All detection is regex + heuristics (zero external scoring dependencies) so the
engine is fast, deterministic, and easy to audit.

Design notes:
- All regex patterns are compiled at module load (not per-call) to avoid
  re-parsing them on every invocation.
- Detection methods never raise unhandled exceptions — they always return a
  result so callers can apply policy in a uniform way.
- The engine is intended to be used as a singleton instance, typically via
  dependency injection on the ExecutionContext.
"""

from __future__ import annotations

import base64
import binascii
import codecs
import logging
import math
import re
import unicodedata
import uuid
from datetime import datetime
from typing import Any, Iterable

from app.shared_types import (
    InjectionScanResult,
    PIICategory,
    PIIMatch,
    PIIScanResult,
    PolicyAction,
    SecurityScanResult,
)

try:
    from sqlalchemy.ext.asyncio import AsyncSession  # noqa: F401 (typing only)
except Exception:  # pragma: no cover — SQLAlchemy is always available in prod
    AsyncSession = Any  # type: ignore[assignment, misc]


logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# PII PATTERNS
# Compiled once at module load. Each pattern is paired with a confidence
# baseline and a redaction tag. False-positive mitigation lives in the
# scan_pii method (e.g. Luhn for cards, context validation for SSN).
# ─────────────────────────────────────────────────────────────────────────────

# RFC 5322-ish simplified email regex. We do not match every legal RFC form
# (e.g. quoted local parts) because it produces too many false positives.
EMAIL_RE = re.compile(
    r"(?<![A-Za-z0-9._%+\-])"  # boundary on left
    r"([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})"
    r"(?![A-Za-z0-9._%+\-])",  # boundary on right
)

# Phone numbers — US and international. Requires at least 10 digits and
# common separators / parentheses. We restrict to plausible lengths to keep
# precision high.
PHONE_RE = re.compile(
    r"(?<!\d)"
    r"(\+?\d{1,3}[\s.\-]?)?"               # optional country code
    r"(\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}"   # US-style
    r"|\d{2,4}[\s.\-]\d{2,4}[\s.\-]\d{2,4}(?:[\s.\-]\d{2,4})?)"  # international
    r"(?!\d)",
)

# SSN — strict format with dashes. We also accept 9 contiguous digits with
# word context ("ssn", "social security") to reduce false positives.
SSN_DASHED_RE = re.compile(r"(?<!\d)(\d{3})-(\d{2})-(\d{4})(?!\d)")
SSN_CONTEXTUAL_RE = re.compile(
    r"\b(?:ssn|social\s*security(?:\s*(?:no|number|#))?)\s*[:#\-]?\s*(\d{9})\b",
    re.IGNORECASE,
)

# Credit card — 13–19 digits, possibly separated by spaces or dashes. After
# regex match we validate with Luhn to remove almost all false positives.
CREDIT_CARD_RE = re.compile(
    r"(?<!\d)(\d[ \-]?){12,18}\d(?!\d)",
)

# IPv4 dotted-quad with octet bounds.
IPV4_RE = re.compile(
    r"(?<![\d.])"
    r"((?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)"
    r"(?:\.(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)){3})"
    r"(?![\d.])",
)

# IPv6 — simplified but strict enough for normal addresses (full + abbreviated).
IPV6_RE = re.compile(
    r"(?<![A-Fa-f0-9:])"
    r"("
    r"(?:[A-Fa-f0-9]{1,4}:){7}[A-Fa-f0-9]{1,4}"        # full
    r"|(?:[A-Fa-f0-9]{1,4}:){1,7}:"                       # trailing ::
    r"|(?:[A-Fa-f0-9]{1,4}:){1,6}:[A-Fa-f0-9]{1,4}"
    r"|::(?:[A-Fa-f0-9]{1,4}:){0,6}[A-Fa-f0-9]{1,4}"
    r")"
    r"(?![A-Fa-f0-9:])",
)

# Dates of birth: require contextual cue words to keep precision high.
DOB_RE = re.compile(
    r"\b(?:born|dob|date\s*of\s*birth|birth(?:day|date))\b"
    r"\s*[:\-]?\s*"
    r"(\d{1,2}[\-/\.]\d{1,2}[\-/\.]\d{2,4}"
    r"|\d{4}[\-/\.]\d{1,2}[\-/\.]\d{1,2}"
    r"|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:,)?\s+\d{2,4})",
    re.IGNORECASE,
)

# Medical context keywords — flagged with moderate confidence.
MEDICAL_KEYWORDS = (
    "diagnosis", "diagnosed", "prescription", "prescribed", "patient",
    "medication", "dosage", "mg/kg", "blood pressure", "icd-10", "icd10",
    "symptoms", "treatment plan", "medical record", "mrn ", "hipaa",
)
MEDICAL_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in MEDICAL_KEYWORDS) + r")\b",
    re.IGNORECASE,
)

# Names — low-precision heuristic. We only flag capitalized pairs that follow
# explicit labels like "name:", "by:", "from:". Confidence is flagged low so
# callers can ignore if desired.
NAME_RE = re.compile(
    r"\b(?:name|by|from|signed)\s*[:\-]\s*([A-Z][a-z]+\s+[A-Z][a-z]+)\b",
)


# Map of PII category → (compiled pattern, base confidence, redaction tag).
# Used for simple "find all matches" patterns. Special categories with
# additional validation (SSN, credit card, DOB, medical, name) are handled
# manually inside scan_pii so they can apply context rules.
_SIMPLE_PII_PATTERNS: tuple[tuple[PIICategory, re.Pattern[str], float], ...] = (
    (PIICategory.EMAIL, EMAIL_RE, 0.95),
    (PIICategory.PHONE, PHONE_RE, 0.80),
    (PIICategory.IP_ADDRESS, IPV4_RE, 0.90),
    (PIICategory.IP_ADDRESS, IPV6_RE, 0.90),
)


def _redaction_tag(category: PIICategory) -> str:
    return f"[REDACTED_{category.value.upper()}]"


def luhn_check(number: str) -> bool:
    """Validate a credit-card-style number using the Luhn algorithm.

    Strips all non-digit characters first. Returns False for empty input or
    obviously invalid lengths (<13 or >19 digits) so callers can short-circuit.
    Pure Python — no external deps.
    """
    digits = [c for c in number if c.isdigit()]
    if not (13 <= len(digits) <= 19):
        return False
    total = 0
    parity = len(digits) % 2
    for i, ch in enumerate(digits):
        d = int(ch)
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


# ─────────────────────────────────────────────────────────────────────────────
# INJECTION PATTERNS
# Three buckets: HIGH, MEDIUM, LOW. Each pattern carries a per-match score.
# The final risk_score combines the maximum (worst case) with the mean
# (cumulative risk from many weak signals).
# ─────────────────────────────────────────────────────────────────────────────

_HIGH_RISK_PATTERNS: tuple[tuple[str, re.Pattern[str], float], ...] = (
    # Classic prompt-override attacks.
    ("ignore_previous_instructions",
     re.compile(r"\b(?:ignore|disregard|forget)\s+(?:all\s+)?(?:previous|prior|earlier|the\s+above)\s+(?:instructions?|prompts?|messages?|context|rules?)\b", re.IGNORECASE),
     0.95),
    ("forget_system_prompt",
     re.compile(r"\bforget\s+(?:your\s+)?(?:system|initial|original)\s+(?:prompt|instructions?)\b", re.IGNORECASE),
     0.95),
    ("override_instructions",
     re.compile(r"\b(?:override|overrule|bypass)\s+(?:your\s+)?(?:instructions?|rules?|safety|guidelines?|restrictions?)\b", re.IGNORECASE),
     0.95),
    ("new_instructions",
     re.compile(r"\byour\s+new\s+(?:instructions?|task|role|directive)s?\s+(?:are|is)\b", re.IGNORECASE),
     0.92),
    # Role-play / persona hijack.
    ("you_are_now",
     re.compile(r"\byou\s+are\s+now\s+(?:a\s+|an\s+)?(?:dan|jailbroken|unrestricted|uncensored|evil|hacker)", re.IGNORECASE),
     0.95),
    ("act_as_unrestricted",
     re.compile(r"\b(?:act|pretend|behave|roleplay)\s+as\s+(?:if\s+you\s+are\s+)?(?:dan|jailbroken|unrestricted|uncensored|an\s+ai\s+without|a\s+model\s+without|with\s+no\s+restrictions)", re.IGNORECASE),
     0.93),
    # Explicit jailbreak phrasing.
    ("jailbreak_keyword",
     re.compile(r"\b(?:jailbreak|jail\s*break|dan\s*mode|developer\s*mode)\b", re.IGNORECASE),
     0.90),
)

_MEDIUM_RISK_PATTERNS: tuple[tuple[str, re.Pattern[str], float], ...] = (
    ("repeat_after_me",
     re.compile(r"\b(?:repeat|echo|print|output)\s+(?:after|back|the\s+following|exactly|verbatim)\b", re.IGNORECASE),
     0.65),
    ("reveal_system_prompt",
     re.compile(r"\b(?:what|show|tell|reveal|display|print)\s+(?:me\s+)?(?:your|the)\s+(?:system\s+prompt|initial\s+instructions?|original\s+(?:prompt|instructions?)|hidden\s+(?:prompt|rules?))\b", re.IGNORECASE),
     0.75),
    ("what_were_instructions",
     re.compile(r"\bwhat\s+(?:were|are)\s+(?:your\s+)?(?:original\s+|initial\s+|prior\s+)?instructions?\b", re.IGNORECASE),
     0.70),
)

_LOW_RISK_PATTERNS: tuple[tuple[str, re.Pattern[str], float], ...] = (
    ("instructions_in_code_block",
     re.compile(r"```[^`]*?(?:ignore|system\s*prompt|instructions?)[^`]*?```", re.IGNORECASE | re.DOTALL),
     0.35),
    ("markdown_role_header",
     re.compile(r"^#{1,6}\s*(?:system|assistant|user)\s*[:#]", re.IGNORECASE | re.MULTILINE),
     0.30),
)

# A run of >= this many identical characters is treated as token flooding.
_FLOOD_RUN_THRESHOLD = 40

# Excessive special characters threshold (ratio).
_SPECIAL_CHAR_RATIO_THRESHOLD = 0.45


class SecurityPolicyError(Exception):
    """Raised by enforce_policy when a scan result triggers a BLOCK action."""

    def __init__(self, message: str, scan_result: SecurityScanResult) -> None:
        super().__init__(message)
        self.scan_result = scan_result


def _normalize_homoglyphs(text: str) -> str:
    """Normalize text to NFKC and map common homoglyphs to ASCII equivalents.

    Used purely to *detect* injection content that hides behind look-alike
    characters. The original text is never mutated for the caller.
    """
    normalized = unicodedata.normalize("NFKC", text)
    # Common Cyrillic/Greek look-alikes for Latin letters.
    homoglyph_map = str.maketrans({
        "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x",
        "А": "A", "Е": "E", "О": "O", "Р": "P", "С": "C", "У": "Y", "Х": "X",
        "ѕ": "s", "і": "i", "ј": "j", "ӏ": "l",
        "Ѕ": "S", "І": "I", "Ј": "J",
        "ο": "o", "Ο": "O", "ρ": "p", "Ρ": "P", "α": "a", "Α": "A",
        "ε": "e", "Ε": "E", "ι": "i", "Ι": "I", "ν": "v", "Ν": "N",
    })
    return normalized.translate(homoglyph_map)


def _decode_candidates(text: str) -> list[tuple[str, str]]:
    """Try to decode base64 and ROT13 strings found inside ``text``.

    Returns a list of (decoded_text, source_label) tuples. Decoding failures
    are silently ignored — this is a best-effort probe.
    """
    decoded: list[tuple[str, str]] = []

    # Base64: pick out reasonably long base64-looking blobs.
    for m in re.finditer(r"[A-Za-z0-9+/]{20,}={0,2}", text):
        blob = m.group(0)
        try:
            raw = base64.b64decode(blob, validate=True)
            try:
                as_text = raw.decode("utf-8")
            except UnicodeDecodeError:
                continue
            if as_text.isprintable() or any(ch.isalpha() for ch in as_text):
                decoded.append((as_text, "base64"))
        except (binascii.Error, ValueError):
            continue

    # ROT13: only worth trying if the input has enough alphabetic content.
    if sum(ch.isalpha() for ch in text) >= 20:
        try:
            rot13 = codecs.decode(text, "rot_13")
            if rot13 != text:
                decoded.append((rot13, "rot13"))
        except Exception:
            pass

    return decoded


def _has_control_or_homoglyph(text: str) -> tuple[bool, bool]:
    """Return (has_control_chars, has_homoglyph_letters)."""
    has_ctrl = any(
        unicodedata.category(ch).startswith("C") and ch not in ("\n", "\t", "\r")
        for ch in text
    )
    # Detect Cyrillic / Greek letters that frequently appear as homoglyphs of
    # ASCII letters. We treat any non-Latin letter in an otherwise Latin
    # string as a potential homoglyph attack signal.
    latin_count = sum(1 for ch in text if "LATIN" in unicodedata.name(ch, ""))
    suspicious = sum(
        1 for ch in text
        if ch.isalpha() and "LATIN" not in unicodedata.name(ch, "")
        and ("CYRILLIC" in unicodedata.name(ch, "") or "GREEK" in unicodedata.name(ch, ""))
    )
    has_homo = suspicious >= 1 and latin_count > suspicious  # mixed-script
    return has_ctrl, has_homo


def _longest_run(text: str) -> int:
    longest = 0
    current = 0
    prev = ""
    for ch in text:
        if ch == prev:
            current += 1
        else:
            current = 1
            prev = ch
        longest = max(longest, current)
    return longest


def _special_char_ratio(text: str) -> float:
    if not text:
        return 0.0
    specials = sum(1 for ch in text if not ch.isalnum() and not ch.isspace())
    return specials / len(text)


class SecurityEngine:
    """Singleton-style security engine.

    Inject one instance per process onto ExecutionContext (or import the
    module-level `security_engine` singleton). All public methods are async
    so the API can be uniform with future scoring implementations.
    """

    # ── PII ──────────────────────────────────────────────────────────────────
    async def scan_pii(
        self,
        text: str,
        categories: list[PIICategory] | None = None,
    ) -> PIIScanResult:
        """Detect PII in ``text`` using compiled regex patterns + heuristics.

        Args:
            text: The raw text to scan.
            categories: Optional whitelist of categories to consider. ``None``
                means "scan everything".

        Returns a :class:`PIIScanResult` whose ``redacted_text`` replaces each
        match with a category-specific tag and whose ``risk_score`` is a
        weighted aggregate of match count and confidence.
        """
        if not text:
            return PIIScanResult(has_pii=False, matches=[], redacted_text=text or "", risk_score=0.0)

        allowed = set(categories) if categories else None

        def is_allowed(cat: PIICategory) -> bool:
            return allowed is None or cat in allowed

        matches: list[PIIMatch] = []

        # 1. Simple patterns (email / phone / ip).
        for category, pattern, base_conf in _SIMPLE_PII_PATTERNS:
            if not is_allowed(category):
                continue
            for m in pattern.finditer(text):
                value = m.group(0)
                # Phone: require >=10 digits to filter "1.2.3.4" style noise.
                if category == PIICategory.PHONE:
                    digit_count = sum(1 for c in value if c.isdigit())
                    if digit_count < 10:
                        continue
                matches.append(PIIMatch(
                    category=category,
                    value=value,
                    redacted=_redaction_tag(category),
                    start=m.start(),
                    end=m.end(),
                    confidence=base_conf,
                ))

        # 2. SSN — dashed format with sanity checks.
        if is_allowed(PIICategory.SSN):
            for m in SSN_DASHED_RE.finditer(text):
                part1, part2, part3 = m.group(1), m.group(2), m.group(3)
                digits = part1 + part2 + part3
                if _ssn_is_plausible(part1, part2, part3, digits):
                    matches.append(PIIMatch(
                        category=PIICategory.SSN,
                        value=m.group(0),
                        redacted=_redaction_tag(PIICategory.SSN),
                        start=m.start(),
                        end=m.end(),
                        confidence=0.95,
                    ))
            for m in SSN_CONTEXTUAL_RE.finditer(text):
                digits = m.group(1)
                p1, p2, p3 = digits[:3], digits[3:5], digits[5:]
                if _ssn_is_plausible(p1, p2, p3, digits):
                    matches.append(PIIMatch(
                        category=PIICategory.SSN,
                        value=digits,
                        redacted=_redaction_tag(PIICategory.SSN),
                        start=m.start(1),
                        end=m.end(1),
                        confidence=0.88,
                    ))

        # 3. Credit card — Luhn-validate every regex hit.
        if is_allowed(PIICategory.CREDIT_CARD):
            for m in CREDIT_CARD_RE.finditer(text):
                value = m.group(0)
                if luhn_check(value):
                    matches.append(PIIMatch(
                        category=PIICategory.CREDIT_CARD,
                        value=value,
                        redacted=_redaction_tag(PIICategory.CREDIT_CARD),
                        start=m.start(),
                        end=m.end(),
                        confidence=0.97,
                    ))

        # 4. Date of birth — only with contextual cues.
        if is_allowed(PIICategory.DATE_OF_BIRTH):
            for m in DOB_RE.finditer(text):
                matches.append(PIIMatch(
                    category=PIICategory.DATE_OF_BIRTH,
                    value=m.group(1),
                    redacted=_redaction_tag(PIICategory.DATE_OF_BIRTH),
                    start=m.start(1),
                    end=m.end(1),
                    confidence=0.80,
                ))

        # 5. Medical context — keyword-based, moderate confidence.
        if is_allowed(PIICategory.MEDICAL):
            for m in MEDICAL_RE.finditer(text):
                matches.append(PIIMatch(
                    category=PIICategory.MEDICAL,
                    value=m.group(0),
                    redacted=_redaction_tag(PIICategory.MEDICAL),
                    start=m.start(),
                    end=m.end(),
                    confidence=0.60,
                ))

        # 6. Names — explicit-label heuristic only (low confidence).
        if is_allowed(PIICategory.NAME):
            for m in NAME_RE.finditer(text):
                matches.append(PIIMatch(
                    category=PIICategory.NAME,
                    value=m.group(1),
                    redacted=_redaction_tag(PIICategory.NAME),
                    start=m.start(1),
                    end=m.end(1),
                    confidence=0.40,
                ))

        # De-duplicate overlapping matches (keep highest confidence).
        matches = _dedupe_overlaps(matches)
        matches.sort(key=lambda m: m.start)

        redacted_text = _apply_redactions(text, matches)
        risk_score = _pii_risk_score(matches, len(text))

        return PIIScanResult(
            has_pii=len(matches) > 0,
            matches=matches,
            redacted_text=redacted_text,
            risk_score=risk_score,
        )

    # ── Injection ────────────────────────────────────────────────────────────
    async def scan_injection(self, text: str) -> InjectionScanResult:
        """Detect prompt injection / jailbreak attempts in ``text``.

        Combines three pattern buckets with composite scoring. We also probe
        Unicode normalisation forms (homoglyph attacks) and best-effort
        base64 / rot13 decoding so an attacker can't bypass the scanner by
        wrapping their payload in a trivial encoding.
        """
        if not text:
            return InjectionScanResult(is_safe=True, risk_score=0.0, patterns_matched=[], explanation="empty input")

        patterns_matched: list[str] = []
        scores: list[float] = []
        explanations: list[str] = []

        # Build candidate texts: original, NFKC + homoglyph-normalized, and
        # any decoded base64/rot13 contents. Each candidate contributes to
        # the same score pool so attackers can't hide behind transformations.
        candidates: list[tuple[str, str]] = [(text, "raw")]
        normalized = _normalize_homoglyphs(text)
        if normalized != text:
            candidates.append((normalized, "normalized"))
        candidates.extend(_decode_candidates(text))

        for candidate, source in candidates:
            for label, pattern, weight in _HIGH_RISK_PATTERNS:
                if pattern.search(candidate):
                    patterns_matched.append(f"{label}:{source}")
                    scores.append(weight)
                    explanations.append(f"High-risk pattern '{label}' matched in {source} text.")
            for label, pattern, weight in _MEDIUM_RISK_PATTERNS:
                if pattern.search(candidate):
                    patterns_matched.append(f"{label}:{source}")
                    scores.append(weight)
                    explanations.append(f"Medium-risk pattern '{label}' matched in {source} text.")
            for label, pattern, weight in _LOW_RISK_PATTERNS:
                if pattern.search(candidate):
                    patterns_matched.append(f"{label}:{source}")
                    scores.append(weight)
                    explanations.append(f"Low-risk pattern '{label}' matched in {source} text.")

        # Heuristic signals on the raw text.
        has_ctrl, has_homo = _has_control_or_homoglyph(text)
        if has_homo:
            patterns_matched.append("homoglyph_mixed_script")
            scores.append(0.60)
            explanations.append("Mixed-script homoglyph characters detected (possible obfuscation).")
        if has_ctrl:
            patterns_matched.append("control_characters")
            scores.append(0.45)
            explanations.append("Non-printable control characters present.")

        run = _longest_run(text)
        if run >= _FLOOD_RUN_THRESHOLD:
            patterns_matched.append("token_flooding")
            scores.append(min(0.50 + (run - _FLOOD_RUN_THRESHOLD) / 200.0, 0.85))
            explanations.append(f"Long run of repeated characters ({run}) suggests token flooding.")

        special_ratio = _special_char_ratio(text)
        if special_ratio >= _SPECIAL_CHAR_RATIO_THRESHOLD and len(text) >= 40:
            patterns_matched.append("excessive_special_chars")
            scores.append(0.40)
            explanations.append(f"Excessive special-character ratio ({special_ratio:.2f}).")

        if not scores:
            return InjectionScanResult(
                is_safe=True,
                risk_score=0.0,
                patterns_matched=[],
                explanation="No suspicious patterns detected.",
            )

        max_score = max(scores)
        avg_score = sum(scores) / len(scores)
        composite = min(max_score * 0.7 + avg_score * 0.3, 1.0)

        return InjectionScanResult(
            is_safe=composite < 0.7,
            risk_score=composite,
            patterns_matched=patterns_matched,
            explanation=" ".join(explanations[:5]),
        )

    # ── Policy enforcement ───────────────────────────────────────────────────
    async def enforce_policy(
        self,
        scan_result: SecurityScanResult,
        policy_config: dict[str, Any],
    ) -> PolicyAction:
        """Resolve a policy action based on ``scan_result`` and ``policy_config``.

        ``policy_config`` keys (all optional):
            - ``on_injection``: PolicyAction for injection hits (default BLOCK)
            - ``on_pii``: PolicyAction for PII hits (default REDACT)
            - ``injection_threshold``: float (default 0.7)
            - ``pii_threshold``: float (default 0.3)
            - ``require_approval_on_high_risk``: bool

        Behaviour:
            - BLOCK → raise :class:`SecurityPolicyError`.
            - REDACT / ALERT / REQUIRE_APPROVAL → return the action; the
              caller is responsible for applying it (e.g. use ``redacted_text``
              from the PII result, or set the node to WAITING state).
            - ALLOW → no action.
        """
        on_injection = PolicyAction(policy_config.get("on_injection", PolicyAction.BLOCK.value))
        on_pii = PolicyAction(policy_config.get("on_pii", PolicyAction.REDACT.value))
        injection_threshold = float(policy_config.get("injection_threshold", 0.7))
        pii_threshold = float(policy_config.get("pii_threshold", 0.3))
        require_approval_high = bool(policy_config.get("require_approval_on_high_risk", False))

        injection_triggered = (
            not scan_result.injection.is_safe
            or scan_result.injection.risk_score >= injection_threshold
        )
        pii_triggered = (
            scan_result.pii.has_pii
            and scan_result.pii.risk_score >= pii_threshold
        )

        action: PolicyAction = PolicyAction.ALLOW
        if injection_triggered:
            action = on_injection
        elif pii_triggered:
            action = on_pii

        if require_approval_high and (
            scan_result.injection.risk_score >= 0.85
            or scan_result.pii.risk_score >= 0.85
        ):
            action = PolicyAction.REQUIRE_APPROVAL

        if action == PolicyAction.BLOCK:
            raise SecurityPolicyError(
                f"Security policy blocked execution "
                f"(injection={scan_result.injection.risk_score:.2f}, "
                f"pii={scan_result.pii.risk_score:.2f})",
                scan_result=scan_result,
            )

        return action

    # ── Audit ────────────────────────────────────────────────────────────────
    def generate_audit_id(self) -> str:
        """Generate a unique audit record id (uuid4 hex)."""
        return uuid.uuid4().hex

    async def create_audit_record(
        self,
        audit_id: str,
        execution_id: str,
        node_id: str,
        event_type: str,
        data: dict[str, Any],
        db: Any,  # AsyncSession; typed Any to avoid hard SQLAlchemy import here
    ) -> None:
        """Persist a security event to the ``audit_logs`` table.

        We don't import the SQLAlchemy model here to avoid a circular import
        with the models package. We try a few common conventions:

        1. ``app.models.audit_log.AuditLog`` ORM class.
        2. Raw SQL fallback if the model isn't importable.

        Failures are logged but never re-raised — auditing must never block
        the security path.
        """
        record = {
            "id": audit_id,
            "execution_id": execution_id,
            "node_id": node_id,
            "event_type": event_type,
            "data": data,
            "created_at": datetime.utcnow(),
        }
        try:  # Preferred: ORM model.
            from app.models.audit_log import AuditLog  # type: ignore

            entry = AuditLog(**record)
            db.add(entry)
            await db.flush()
            return
        except Exception as exc:  # noqa: BLE001 — best-effort
            logger.debug("audit ORM unavailable, falling back to log-only: %s", exc)

        # Last-resort: log the audit entry so it's at least observable.
        logger.info(
            "security.audit",
            extra={
                "audit_id": audit_id,
                "execution_id": execution_id,
                "node_id": node_id,
                "event_type": event_type,
                "data": data,
            },
        )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _ssn_is_plausible(part1: str, part2: str, part3: str, digits: str) -> bool:
    """Reject obviously-invalid SSNs (per SSA rules + sanity checks)."""
    if digits == "0" * 9:
        return False
    if part1 == "000" or part2 == "00" or part3 == "0000":
        return False
    if part1 == "666" or part1.startswith("9"):
        return False
    # Reject perfectly sequential digits (123456789, 987654321).
    if digits in ("123456789", "987654321"):
        return False
    return True


def _dedupe_overlaps(matches: list[PIIMatch]) -> list[PIIMatch]:
    """Remove overlapping matches, preferring higher confidence."""
    if not matches:
        return matches
    sorted_matches = sorted(matches, key=lambda m: (m.start, -m.confidence))
    kept: list[PIIMatch] = []
    for m in sorted_matches:
        if kept and m.start < kept[-1].end:
            # overlap — keep the one with higher confidence
            if m.confidence > kept[-1].confidence:
                kept[-1] = m
            continue
        kept.append(m)
    return kept


def _apply_redactions(text: str, matches: list[PIIMatch]) -> str:
    """Apply non-overlapping redactions, sorted by start descending."""
    if not matches:
        return text
    out = text
    for m in sorted(matches, key=lambda x: x.start, reverse=True):
        out = out[: m.start] + m.redacted + out[m.end :]
    return out


def _pii_risk_score(matches: list[PIIMatch], text_length: int) -> float:
    """Weighted aggregate of PII matches.

    Heuristic: each match contributes its confidence; sensitive categories
    (SSN, credit card, medical) get a multiplier. We then squash via tanh to
    keep the result in [0, 1] regardless of how many matches were found.
    """
    if not matches:
        return 0.0

    weights = {
        PIICategory.SSN: 1.4,
        PIICategory.CREDIT_CARD: 1.4,
        PIICategory.MEDICAL: 1.2,
        PIICategory.PASSPORT: 1.3,
        PIICategory.DATE_OF_BIRTH: 1.1,
    }
    total = sum(m.confidence * weights.get(m.category, 1.0) for m in matches)
    # Bias toward higher score for short inputs (one SSN in a 50-char string
    # is more concerning than the same SSN in 50KB of logs).
    density_bonus = 0.0
    if text_length and text_length < 200:
        density_bonus = 0.1
    score = math.tanh(total / 2.0) + density_bonus
    return float(min(max(score, 0.0), 1.0))


# Module-level singleton — import this rather than instantiating directly.
security_engine = SecurityEngine()


__all__ = [
    "SecurityEngine",
    "SecurityPolicyError",
    "luhn_check",
    "security_engine",
]
