"""Bounded read-only verification of every official link in a public build.

The report stays outside Pages. An inaccessible URL is recorded, never interpreted
as evidence of an absent list, a successful source check, or a new edition.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def check(url: str) -> dict:
    result = {"url": url, "attempted_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    try:
        with urlopen(Request(url, headers={"User-Agent": "italian-anti-mafia-whitelist/public-link-audit"}), timeout=25) as response:
            result.update(status=response.status, final_url=response.url, content_type=response.headers.get("Content-Type", ""))
            response.read(4096)
    except HTTPError as exc:
        result.update(status=exc.code, error=str(exc))
    except (URLError, TimeoutError, OSError) as exc:
        result.update(status=None, error=str(exc))
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("public_root", type=Path)
    p.add_argument("output", type=Path)
    args = p.parse_args()
    root = args.public_root / "data"
    site, reg, pref = [json.loads((root / name).read_text()) for name in ("site.json", "registry.json", "prefectures.json")]
    urls = {pref["meta"]["national_index_url"]}
    urls.update(h["page_url"] for h in site["history"])
    for row in reg["records"]:
        urls.update([row["source_page_url"], row["resource_url"]])
    for row in pref["prefectures"]:
        url = row["verified_primary_page"] or next(iter(row["official_white_list_urls"]), "")
        if url:
            urls.add(url)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(check, sorted(urls)))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
    failures = [r for r in results if r.get("status") != 200]
    print(json.dumps({"checked": len(results), "http_200": len(results) - len(failures), "unavailable": failures}))


if __name__ == "__main__":
    main()
