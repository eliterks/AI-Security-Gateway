import re

COMPLEX_PATTERNS = [
    r"\b(write|debug|implement|optimize|prove|derive|analy[sz]e|compare|design)\b",
    r"\b(architecture|step by step|trade[- ]off|multiple constraints)\b",
    r"\b(python|javascript|typescript|sql|code|function|algorithm|recursion|bug)\b",
]

def choose_model(prompt: str, requested: str = "auto") -> str:
    if requested in ("slm", "llm"):
        return requested
    words = prompt.split()
    complexity_hits = sum(bool(re.search(p, prompt, re.I)) for p in COMPLEX_PATTERNS)
    return "llm" if len(words) > 70 or complexity_hits else "slm"
