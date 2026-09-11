from __future__ import annotations

import os
import urllib.request
from collections import defaultdict
from pathlib import Path

import pdfplumber


def clean(value: str) -> str:
    return " ".join(value.split())


def main() -> None:
    path = Path("/tmp/brindisi-applicants.pdf")
    req = urllib.request.Request(os.environ["APPLICANT_URL"], headers={"User-Agent": "Mozilla/5.0 white-list-archive-source-audit"})
    with urllib.request.urlopen(req, timeout=60) as response:
        path.write_bytes(response.read())
    with pdfplumber.open(path) as pdf:
        for pno, page in enumerate(pdf.pages, 1):
            print(f"GEOMETRY_PAGE {pno} width={page.width:.1f} height={page.height:.1f}")
            words = page.extract_words(x_tolerance=1, y_tolerance=2, keep_blank_chars=False, use_text_flow=False)
            lines: dict[float, list[dict]] = defaultdict(list)
            for word in words:
                key = round(float(word["top"]), 0)
                lines[key].append(word)
            for top in sorted(lines):
                items = sorted(lines[top], key=lambda w: float(w["x0"]))
                text = clean(" ".join(str(w["text"]) for w in items))
                if not text:
                    continue
                coords = " | ".join(f"{float(w['x0']):.0f}:{w['text']}" for w in items)
                print(f"L {top:04.0f} {coords}")


if __name__ == "__main__":
    main()
