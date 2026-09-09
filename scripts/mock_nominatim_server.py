from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


def _version(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip() or "mock-v1"


def _candidate(query: str, country: str) -> dict:
    folded = query.casefold()
    if "parigi" in folded or country.lower() == "fr":
        locality, state, country_name, code, lon, lat = (
            "Paris", "Île-de-France", "France", "fr", 2.3522, 48.8566
        )
    elif "pistoia" in folded:
        locality, state, country_name, code, lon, lat = (
            "Pistoia", "Toscana", "Italia", "it", 10.9177, 43.9335
        )
    elif "firenze" in folded:
        locality, state, country_name, code, lon, lat = (
            "Firenze", "Toscana", "Italia", "it", 11.2558, 43.7696
        )
    else:
        locality, state, country_name, code, lon, lat = (
            "Cosenza", "Calabria", "Italia", "it", 16.2518, 39.2983
        )
    return {
        "type": "Feature",
        "properties": {
            "geocoding": {
                "type": "house",
                "label": f"{query} [{code.upper()}]",
                "housenumber": "1",
                "street": query,
                "city": locality,
                "state": state,
                "country": country_name,
                "country_code": code,
                "osm_type": "way",
                "osm_id": str(abs(hash(query)) % 10000000),
            }
        },
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--version-file", type=Path, required=True)
    parser.add_argument("--log-file", type=Path, required=True)
    args = parser.parse_args()
    args.log_file.parent.mkdir(parents=True, exist_ok=True)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, _format: str, *_args) -> None:
            return

        def _send(self, payload: dict) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            version = _version(args.version_file)
            if parsed.path == "/status":
                self._send(
                    {
                        "status": 0,
                        "software_version": version,
                        "data_updated": (
                            "2026-09-10T00:00:00Z" if version == "mock-v2"
                            else "2026-09-09T00:00:00Z"
                        ),
                    }
                )
                return
            if parsed.path != "/search":
                self.send_error(404)
                return
            query = params.get("q", [""])[0]
            country = params.get("countrycodes", [""])[0]
            event = {
                "path": "search",
                "query": query,
                "countrycodes": country or None,
                "provider_version": version,
            }
            with args.log_file.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")
            features = [] if "MYSTERY" in query.upper() else [_candidate(query, country)]
            self._send(
                {
                    "type": "FeatureCollection",
                    "geocoding": {
                        "version": "0.1.0",
                        "attribution": "Deterministic CI mock",
                        "licence": "test-only",
                        "query": query,
                    },
                    "features": features,
                }
            )

    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
