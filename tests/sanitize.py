import os
from pathlib import Path
import re

for p in Path("evidence").glob("*"):
    text = p.read_text(errors="replace")
    for value in sorted(
        [
            v
            for k, v in os.environ.items()
            if k in ["APP_TOKEN", "OPENROUTER_API_KEY"] and v
        ],
        key=len,
        reverse=True,
    ):
        text = text.replace(value, "[REDACTED]")
    text = re.sub(
        r"(?:gh[psu]_[A-Za-z0-9_]+|ghs_[A-Za-z0-9_]+|sk-or-v1-[A-Za-z0-9]+)",
        "[REDACTED]",
        text,
    )
    p.write_text(text[: 2 * 1024 * 1024])
