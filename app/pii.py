import re
from dataclasses import dataclass

@dataclass
class PIIMatch:
    kind: str
    start: int
    end: int

PATTERNS = [
    ("EMAIL", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
    ("PAN", re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.I)),
    ("AADHAAR_LIKE", re.compile(r"(?<!\d)(?:\d[\s-]?){11}\d(?!\d)")),
    ("CARD_LIKE", re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")),
    ("INDIAN_PHONE", re.compile(r"(?<!\d)(?:\+91[\s-]?)?[6-9]\d{9}(?!\d)")),
]

def detect_pii(text: str) -> list:
    candidates = []
    for kind, pattern in PATTERNS:
        for match in pattern.finditer(text):
            digits = re.sub(r"\D", "", match.group())
            if kind == "AADHAAR_LIKE" and len(digits) != 12:
                continue
            if kind == "CARD_LIKE" and len(digits) < 13:
                continue
            if kind == "INDIAN_PHONE" and len(digits) not in (10, 12):
                continue
            candidates.append(PIIMatch(kind, match.start(), match.end()))
    candidates.sort(key=lambda m: (-(m.end - m.start), m.start))
    selected = []
    for item in candidates:
        if not any(item.start < other.end and other.start < item.end for other in selected):
            selected.append(item)
    return sorted(selected, key=lambda m: m.start)

def redact_pii(text: str):
    matches = detect_pii(text)
    result = text
    for match in reversed(matches):
        result = result[:match.start] + f"[{match.kind}_REDACTED]" + result[match.end:]
    return result, [match.kind for match in matches]
