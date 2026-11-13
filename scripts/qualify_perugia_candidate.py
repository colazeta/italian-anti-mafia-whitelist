"""Full-document exact-source Perugia qualification; aggregate output only."""
from pathlib import Path
import json
import tempfile
from white_list_archive.parsers.perugia_tables_november import PARSERS
from white_list_archive.publishing.public_national_registry import _download, _adapt_perugia_public_fields
from white_list_archive.publishing.public_contract import public_record


def main():
    config = json.loads(Path("data/publication/multi_prefecture_pilot.json").read_text())
    results = []
    with tempfile.TemporaryDirectory(prefix="perugia-november-qa-") as td:
        for cfg in config["sources"]:
            if cfg["authority_key"] != "perugia":
                continue
            path = Path(td) / (cfg["source_key"] + ".pdf")
            if _download(cfg["resource_url"], path) != cfg["sha256"]:
                raise RuntimeError("Perugia independent original SHA mismatch")
            batch = PARSERS[cfg["parser"]](path, cfg)
            public = _adapt_perugia_public_fields(batch, cfg["parser"].removesuffix("_2026_11"))
            for row in public.records:
                public_record(row)
            results.append({"source_key": cfg["source_key"], "original_sha_verified": True,
                            "public_projection_validated": True, **batch.diagnostics})
    if len(results) != 2:
        raise RuntimeError("Perugia requires both source populations")
    print(json.dumps({"source_qualification": results, "publication_performed": False}, sort_keys=True))


if __name__ == "__main__":
    main()
