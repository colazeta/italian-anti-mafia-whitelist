from __future__ import annotations

import hashlib
import json
from pathlib import Path

REGISTRY_PATH = Path("src/white_list_archive/publishing/public_national_registry.py")
CONFIG_PATH = Path("data/publication/multi_prefecture_pilot.json")
INVENTORY_PATH = Path("data/source_registry/source_series_inventory.csv")
DOC_PATH = Path("docs/sources/ferrara-operational-check-2026-09-20.md")
TEST_PATH = Path("tests/test_ferrara_public_bundle.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label} anchor cardinality drift: {count}")
    return text.replace(old, new, 1)


def patch_registry() -> None:
    text = REGISTRY_PATH.read_text(encoding="utf-8")

    text = replace_once(
        text,
        "from white_list_archive.parsers.siracusa_tables import PARSERS as SIRACUSA_PARSERS\n"
        "from white_list_archive.parsers.macerata_tables import PARSERS as MACERATA_PARSERS\n",
        "from white_list_archive.parsers.siracusa_tables import PARSERS as SIRACUSA_PARSERS\n"
        "from white_list_archive.parsers.macerata_tables import PARSERS as MACERATA_PARSERS\n"
        "from white_list_archive.parsers.ferrara_tables import (\n"
        "    PARSERS as FERRARA_PARSERS,\n"
        "    parse_ferrara_reconstruction_bundle,\n"
        ")\n",
        "Ferrara import",
    )

    text = replace_once(
        text,
        'FIRENZE_PARSERS = {\n'
        '    "firenze_listed": parse_firenze_listed,\n'
        '    "firenze_applicants": parse_firenze_applicants,\n'
        '}\n\n\n',
        'FIRENZE_PARSERS = {\n'
        '    "firenze_listed": parse_firenze_listed,\n'
        '    "firenze_applicants": parse_firenze_applicants,\n'
        '}\n'
        'FERRARA_RECONSTRUCTION_PARSER = "ferrara-reconstruction-listed"\n\n\n',
        "Ferrara parser constant",
    )

    adapter = "\n".join([
        "",
        "def _adapt_ferrara_public_fields(batch: ParsedBatch, parser_name: str) -> ParsedBatch:",
        "    adapted: list[dict[str, Any]] = []",
        "    for source_record in batch.records:",
        "        record = dict(source_record)",
        '        fields = record.get("source_fields")',
        "        if not isinstance(fields, dict):",
        '            raise RuntimeError("Ferrara source_fields must be a mapping")',
        "",
        '        if parser_name == "ferrara-provincial-listed":',
        '            expected = {"listing_date_raw", "expiry_date_raw", "notes", "physical_locators"}',
        "            if set(fields) != expected:",
        '                raise RuntimeError(f"Ferrara ordinary source-field drift: {sorted(fields)!r}")',
        '            if not isinstance(fields["notes"], list) or any(not isinstance(value, str) for value in fields["notes"]):',
        '                raise RuntimeError("Ferrara ordinary notes type drift")',
        '            if not isinstance(fields["physical_locators"], list) or not fields["physical_locators"] or any(not isinstance(value, str) for value in fields["physical_locators"]):',
        '                raise RuntimeError("Ferrara ordinary physical-locator type/cardinality drift")',
        '            if any(not isinstance(fields[key], str) for key in ("listing_date_raw", "expiry_date_raw")):',
        '                raise RuntimeError("Ferrara ordinary raw-date type drift")',
        '            record["source_fields"] = {',
        '                "physical_locators": list(fields["physical_locators"]),',
        '                "notes": list(fields["notes"]),',
        '                "listing_date_raw_variants": [fields["listing_date_raw"]] if fields["listing_date_raw"] else [],',
        '                "expiry_date_raw_variants": [fields["expiry_date_raw"]] if fields["expiry_date_raw"] else [],',
        "            }",
        "",
        '        elif parser_name == "ferrara-provincial-applicants":',
        "            expected = {",
        '                "application_date_raw", "requested_activities_source", "physical_locators",',
        '                "shared_publication_no_duplicate_ingest", "logical_series",',
        "            }",
        "            if set(fields) != expected:",
        '                raise RuntimeError(f"Ferrara applicant source-field drift: {sorted(fields)!r}")',
        '            if fields["shared_publication_no_duplicate_ingest"] is not True:',
        '                raise RuntimeError("Ferrara shared-publication flag drift")',
        '            if fields["logical_series"] != ["ferrara-provincial-applicants", "ferrara-reconstruction-applicants"]:',
        '                raise RuntimeError("Ferrara logical applicant-series binding drift")',
        '            if not isinstance(fields["physical_locators"], list) or len(fields["physical_locators"]) != 1 or any(not isinstance(value, str) for value in fields["physical_locators"]):',
        '                raise RuntimeError("Ferrara applicant physical-locator type/cardinality drift")',
        '            if any(not isinstance(fields[key], str) for key in ("application_date_raw", "requested_activities_source")):',
        '                raise RuntimeError("Ferrara applicant source-field scalar drift")',
        '            record["source_fields"] = {',
        '                "physical_locators": list(fields["physical_locators"]),',
        '                "requested_activities_source": fields["requested_activities_source"],',
        '                "application_date_raw_variants": [fields["application_date_raw"]] if fields["application_date_raw"] else [],',
        "            }",
        "",
        "        elif parser_name == FERRARA_RECONSTRUCTION_PARSER:",
        "            expected = {",
        '                "listing_date_raw", "expiry_date_raw", "sectors", "name_variants",',
        '                "office_variants", "notes", "physical_locators", "physical_sector_observations",',
        "            }",
        "            if set(fields) != expected:",
        '                raise RuntimeError(f"Ferrara reconstruction source-field drift: {sorted(fields)!r}")',
        '            for key in ("sectors", "name_variants", "office_variants", "notes", "physical_locators"):',
        "                if not isinstance(fields[key], list) or any(not isinstance(value, str) for value in fields[key]):",
        '                    raise RuntimeError(f"Ferrara reconstruction source-list type drift: {key}")',
        '            if not fields["sectors"] or not fields["physical_locators"]:',
        '                raise RuntimeError("Ferrara reconstruction empty sector/provenance evidence")',
        '            if type(fields["physical_sector_observations"]) is not int or fields["physical_sector_observations"] < len(fields["sectors"]):',
        '                raise RuntimeError("Ferrara reconstruction physical-sector denominator drift")',
        '            if any(not isinstance(fields[key], str) for key in ("listing_date_raw", "expiry_date_raw")):',
        '                raise RuntimeError("Ferrara reconstruction raw-date type drift")',
        '            record["source_fields"] = {',
        '                "sections": list(fields["sectors"]),',
        '                "physical_locators": list(fields["physical_locators"]),',
        '                "notes": list(fields["notes"]),',
        '                "registered_office_variants": list(fields["office_variants"]),',
        '                "listing_date_raw_variants": [fields["listing_date_raw"]] if fields["listing_date_raw"] else [],',
        '                "expiry_date_raw_variants": [fields["expiry_date_raw"]] if fields["expiry_date_raw"] else [],',
        "            }",
        "        else:",
        '            raise RuntimeError(f"Unexpected Ferrara parser: {parser_name!r}")',
        "        adapted.append(record)",
        "    return ParsedBatch(records=adapted, diagnostics=batch.diagnostics)",
        "",
    ])
    text = replace_once(
        text,
        "\ndef _parse_source(path: Path, cfg: dict[str, Any]) -> ParsedBatch:\n",
        adapter + "\ndef _parse_source(path: Path | dict[str, Path], cfg: dict[str, Any]) -> ParsedBatch:\n",
        "Ferrara adapter insertion",
    )
    text = replace_once(
        text,
        'def _parse_source(path: Path | dict[str, Path], cfg: dict[str, Any]) -> ParsedBatch:\n'
        '    if cfg["parser"] == "cosenza_combined_v2":\n',
        'def _parse_source(path: Path | dict[str, Path], cfg: dict[str, Any]) -> ParsedBatch:\n'
        '    if cfg["parser"] == FERRARA_RECONSTRUCTION_PARSER:\n'
        '        if not isinstance(path, dict):\n'
        '            raise RuntimeError("Ferrara reconstruction requires an explicitly acquired source bundle")\n'
        '        batch = _adapt_ferrara_public_fields(parse_ferrara_reconstruction_bundle(path, cfg), cfg["parser"])\n'
        '        for record in batch.records:\n'
        '            record["parser_name"] = cfg["parser"]\n'
        '            record["parser_version"] = "1"\n'
        '        return batch\n'
        '    if not isinstance(path, Path):\n'
        '        raise RuntimeError(f"Scalar parser received a source bundle: {cfg[\'parser\']!r}")\n'
        '    if cfg["parser"] == "cosenza_combined_v2":\n',
        "Ferrara bundle dispatch",
    )
    text = replace_once(
        text,
        '        or SIRACUSA_PARSERS.get(cfg["parser"])\n'
        '        or MACERATA_PARSERS.get(cfg["parser"])\n',
        '        or SIRACUSA_PARSERS.get(cfg["parser"])\n'
        '        or MACERATA_PARSERS.get(cfg["parser"])\n'
        '        or FERRARA_PARSERS.get(cfg["parser"])\n',
        "Ferrara scalar parser map",
    )
    text = replace_once(
        text,
        '    if cfg["parser"] in MATERA_PARSERS:\n'
        '        batch = _adapt_matera_public_fields(batch, cfg["parser"])\n'
        '    for record in batch.records:\n',
        '    if cfg["parser"] in MATERA_PARSERS:\n'
        '        batch = _adapt_matera_public_fields(batch, cfg["parser"])\n'
        '    if cfg["parser"] in FERRARA_PARSERS:\n'
        '        batch = _adapt_ferrara_public_fields(batch, cfg["parser"])\n'
        '    for record in batch.records:\n',
        "Ferrara scalar adapter",
    )

    helpers = "\n".join([
        "",
        "def _bundle_digest(member_hashes: dict[str, str]) -> str:",
        "    if not member_hashes:",
        '        raise RuntimeError("Source bundle must contain at least one member")',
        "    for label, digest in member_hashes.items():",
        '        if not isinstance(label, str) or not label or re.fullmatch(r"[A-Za-z0-9._-]+", label) is None:',
        '            raise RuntimeError(f"Invalid source-bundle label: {label!r}")',
        '        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:',
        '            raise RuntimeError(f"Invalid source-bundle SHA-256 for {label!r}: {digest!r}")',
        '    payload = "".join(member_hashes[label] for label in sorted(member_hashes)).encode("ascii")',
        '    return "bundle:" + hashlib.sha256(payload).hexdigest()',
        "",
        "",
        "def _acquire_source_input(cfg: dict[str, Any], work_dir: Path) -> tuple[Path | dict[str, Path], str]:",
        '    resources = cfg.get("resources")',
        "    if resources is None:",
        '        suffix = Path(urlparse(cfg["resource_url"]).path).suffix or ".pdf"',
        '        local_path = work_dir / f"{cfg[\'source_key\']}{suffix}"',
        '        return local_path, _download(cfg["resource_url"], local_path)',
        "",
        "    if not isinstance(resources, dict) or not resources:",
        '        raise RuntimeError(f"{cfg[\'source_key\']}: resources must be a non-empty mapping")',
        "    paths: dict[str, Path] = {}",
        "    member_hashes: dict[str, str] = {}",
        "    for label in sorted(resources):",
        "        member = resources[label]",
        '        if not isinstance(member, dict) or set(member) != {"resource_url", "sha256"}:',
        '            raise RuntimeError(f"{cfg[\'source_key\']}: source-bundle member shape drift for {label!r}")',
        '        url = member["resource_url"]',
        '        expected_sha = member["sha256"]',
        '        if not isinstance(url, str) or not url.startswith("https://"):',
        '            raise RuntimeError(f"{cfg[\'source_key\']}: invalid source-bundle URL for {label!r}")',
        '        if not isinstance(expected_sha, str) or re.fullmatch(r"[0-9a-f]{64}", expected_sha) is None:',
        '            raise RuntimeError(f"{cfg[\'source_key\']}: invalid source-bundle SHA-256 for {label!r}")',
        '        suffix = Path(urlparse(url).path).suffix or ".bin"',
        '        local_path = work_dir / f"{cfg[\'source_key\']}-{label}{suffix}"',
        "        actual_sha = _download(url, local_path)",
        "        if actual_sha != expected_sha:",
        '            raise RuntimeError(f"{cfg[\'source_key\']}: bundle member {label!r} SHA mismatch; expected {expected_sha}, got {actual_sha}")',
        "        paths[label] = local_path",
        "        member_hashes[label] = actual_sha",
        "",
        "    actual_bundle_sha = _bundle_digest(member_hashes)",
        '    expected_bundle_sha = cfg.get("sha256")',
        "    if actual_bundle_sha != expected_bundle_sha:",
        '        raise RuntimeError(f"{cfg[\'source_key\']}: bundle manifest SHA mismatch; expected {expected_bundle_sha}, got {actual_bundle_sha}")',
        "    return paths, actual_bundle_sha",
        "",
    ])
    text = replace_once(
        text,
        "\ndef build_registry(config: dict[str, Any], work_dir: Path) -> dict[str, Any]:\n",
        helpers + "\ndef build_registry(config: dict[str, Any], work_dir: Path) -> dict[str, Any]:\n",
        "Bundle helper insertion",
    )
    text = replace_once(
        text,
        '    for cfg in config["sources"]:\n'
        '        suffix = Path(urlparse(cfg["resource_url"]).path).suffix or ".pdf"\n'
        '        local_path = work_dir / f"{cfg[\'source_key\']}{suffix}"\n'
        '        actual_sha = _download(cfg["resource_url"], local_path)\n'
        '        approval_mode = str(cfg.get("approval_mode") or "raw_sha256")\n',
        '    for cfg in config["sources"]:\n'
        '        source_input, actual_sha = _acquire_source_input(cfg, work_dir)\n'
        '        approval_mode = str(cfg.get("approval_mode") or "raw_sha256")\n',
        "Bundle acquisition loop",
    )
    text = replace_once(
        text,
        "        batch = _parse_source(local_path, parse_cfg)\n",
        "        batch = _parse_source(source_input, parse_cfg)\n",
        "Bundle parser input",
    )
    REGISTRY_PATH.write_text(text, encoding="utf-8")


def build_ferrara_sources() -> list[dict]:
    resources = {
        "A": {"resource_url": "https://prefettura.interno.gov.it/sites/default/files/0/2026-08/h-bis-a-fornitura-moduli-prefabbricati-e-dei-relativi-arredi_is_0.pdf", "sha256": "4fdf292b1538892c7b5ff79d3c0c14e0ed3b5830effb791316b0fddb8c90ae01"},
        "B": {"resource_url": "https://prefettura.interno.gov.it/sites/default/files/0/2026-08/h-bis-b-demolizione-di-edifici-ed-altre-strutture_is_0.pdf", "sha256": "97d9af0d587af0b7d93d31df33bd612440bf5be5b48b57872d436e2afeb164ec"},
        "C": {"resource_url": "https://prefettura.interno.gov.it/sites/default/files/0/2026-08/h-bis-c-movimenti-di-terra_is_0.pdf", "sha256": "99f519101dccff84dddd9753f0d6fa27170c33b1982858afe9fdf9ebbc63c57e"},
        "D": {"resource_url": "https://prefettura.interno.gov.it/sites/default/files/0/2026-08/h-bis-d-noleggio-con-coducente-mezzi-speciali_is_0.pdf", "sha256": "07c27b38e48a879aa0d1efff4710bf7dbbf1bb323e59f62eb0b0b796a75a46d8"},
        "E": {"resource_url": "https://prefettura.interno.gov.it/sites/default/files/0/2026-08/h-bis-e-fornitura-e-posa-in-opera-impianti-fotovoltaici_is_0.pdf", "sha256": "9cea950d37f653d0356edb9a46a7f43665a382e771c969bc93f7027f95fecf9e"},
        "F": {"resource_url": "https://prefettura.interno.gov.it/sites/default/files/0/2026-08/h-bis-f-fornitura-e-manutenzione-impianti-tecnologici_is_0.pdf", "sha256": "ac7dd77f1c4633c27a62c0ad7e074f507a10b091a327c2fc1072cfb52fd45664"},
        "G": {"resource_url": "https://prefettura.interno.gov.it/sites/default/files/0/2026-08/h-bis-g-fornitura-beni-necessari-ricostruzione_is_0.pdf", "sha256": "0657c7e0f0b9fb8ad7f0b341682716d695132e61131adc92407627a5cae82bae"},
    }
    bundle_sha = "bundle:" + hashlib.sha256("".join(resources[key]["sha256"] for key in sorted(resources)).encode("ascii")).hexdigest()
    if bundle_sha != "bundle:f3d9093a8859e082ed304b1342ab7a3ae687f7735da04b3d363bbe7440543283":
        raise SystemExit(f"Ferrara reconstruction bundle digest drift: {bundle_sha}")

    common = {
        "authority_key": "ferrara",
        "authority_name": "Prefettura di Ferrara",
        "approval_mode": "raw_sha256",
        "reference_date": "2026-09-20",
        "last_source_update": "2026-08-24",
        "last_source_update_basis": "page-rendered update metadata observed on the official current series page; the registry reference_date remains the 20 September 2026 verified-capture boundary and is not a company legal-effect date",
    }
    return [
        {
            **common,
            "register_key": "ferrara-ordinary",
            "register_name": "White List ordinaria",
            "source_page_url": "https://prefettura.interno.gov.it/it/prefetture/ferrara/white-list-elenco-imprese-iscritte",
            "source_key": "ferrara-provincial-listed",
            "parser": "ferrara-provincial-listed",
            "population_scope": "listed",
            "resource_url": "https://prefettura.interno.gov.it/sites/default/files/0/2026-08/white-list-provinciali-elenco-imprese-iscritte-agg11112024_0.pdf",
            "sha256": "0d631e678b7f85bb84d265b09b8de6fcffa09cc4a49b84be37c6c1d7b9dcd6d9",
            "expected_source_rows": 868,
            "notes": "Current official ordinary listed PDF, twice independently captured byte-identically on 20 September 2026. The fail-closed parser yields 868 observations (717 listed, 150 renewal/update in progress, 1 other/unknown), preserves 28 deterministic continuation rows and two malformed raw dates without inferential repair.",
        },
        {
            **common,
            "register_key": "ferrara-ordinary",
            "register_name": "White List ordinaria",
            "source_page_url": "https://prefettura.interno.gov.it/it/prefetture/ferrara/white-list-elenco-imprese-richiedenti",
            "source_key": "ferrara-provincial-applicants",
            "parser": "ferrara-provincial-applicants",
            "population_scope": "applicant",
            "resource_url": "https://prefettura.interno.gov.it/sites/default/files/0/2026-08/white-list-elenco-imprese-richiedenti_0.pdf",
            "sha256": "c7437cdeebd1a64d4a6de8bbe5e8c108a688269409b7c772e8a6c87162e588e7",
            "expected_source_rows": 21,
            "notes": "Single current official applicant publication, twice independently captured byte-identically on 20 September 2026. Its 21 observations are ingested once physically. Requested-activity text positively corresponds to reconstruction taxonomy categories B-F, so the same physical publication is accounted for as the logical reconstruction-applicant series without duplicate public observations.",
        },
        {
            **common,
            "register_key": "ferrara-reconstruction",
            "register_name": "White List ricostruzione",
            "source_page_url": "https://prefettura.interno.gov.it/it/prefetture/ferrara/white-list-ricostruzione-elenco-imprese-iscritte",
            "source_key": "ferrara-reconstruction-listed",
            "parser": "ferrara-reconstruction-listed",
            "population_scope": "listed",
            "resource_url": "https://prefettura.interno.gov.it/it/prefetture/ferrara/white-list-ricostruzione-elenco-imprese-iscritte",
            "sha256": bundle_sha,
            "resources": resources,
            "expected_source_rows": 694,
            "notes": "Seven official reconstruction sector PDFs A-G are acquired and SHA-256 verified independently before parsing. Their deterministic ordered hash bundle identifies the logical source edition. The parser freezes 1,161 physical sector observations into 694 compatible logical observations (539 listed, 153 renewal/update in progress, 2 other/unknown) without collapsing conflicting date/status identities.",
        },
    ]


def patch_config() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    target_keys = {"ferrara-provincial-listed", "ferrara-provincial-applicants", "ferrara-reconstruction-listed"}
    overlap = {item["source_key"] for item in config["sources"]} & target_keys
    if overlap:
        raise SystemExit(f"Ferrara source config already partially present: {sorted(overlap)}")
    config["sources"].extend(build_ferrara_sources())
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def patch_inventory() -> None:
    text = INVENTORY_PATH.read_text(encoding="utf-8")
    old = "The same current official unified applicant PDF positively contains requests for reconstruction-regime h-bis activities as well as ordinary White List activities. This logical source-series binding accounts for the special-regime applicant population without duplicating public applicant observations."
    new = "The same current official unified applicant PDF has requested-activity descriptions that positively correspond to reconstruction taxonomy categories B-F as well as ordinary White List activities; the PDF itself is not separately labelled as a reconstruction/h-bis applicant publication. This logical source-series binding accounts for the evidenced special-regime applicant scope without creating a second physical publication or duplicate public observations."
    INVENTORY_PATH.write_text(replace_once(text, old, new, "Ferrara inventory wording"), encoding="utf-8")


def patch_doc() -> None:
    text = DOC_PATH.read_text(encoding="utf-8")
    heading = "## Subsequent applicant-scope and parser validation"
    if heading in text:
        raise SystemExit("Ferrara subsequent-validation section already present")
    lines = [
        "",
        "",
        heading,
        "",
        "After the initial source-surface check, the byte-pinned unified applicant PDF was reviewed at row/activity level. Its requested-activity descriptions positively include categories corresponding to reconstruction taxonomy sectors B-F (demolition, earthmoving, special-vehicle hire, photovoltaic systems and technological systems). The PDF itself is **not** separately labelled as a reconstruction or h-bis applicant publication. The defensible treatment is therefore one physical applicant publication ingested once, with two logical source-series bindings (`ferrara-provincial-applicants` and `ferrara-reconstruction-applicants`) and no duplicate public observations.",
        "",
        "Production parser validation on the pinned resources freezes these boundaries:",
        "",
        "- ordinary listed: 868 logical observations from the 87-page PDF — 717 `listed`, 150 `renewal_update_in_progress`, 1 `other_or_unknown`; 859 observations with structured identifiers, 28 deterministic continuation rows and two preserved raw date anomalies;",
        "- unified applicants: 21 pending observations, 21/21 with structured identifiers; one physical ingest only;",
        "- reconstruction listed: 1,161 physical sector observations across A-G grouped into 694 logical observations — 539 `listed`, 153 `renewal_update_in_progress`, 2 `other_or_unknown`; 683/694 with structured identifiers, 285 multi-sector groups and four preserved raw date anomalies.",
        "",
        "The reconstruction grouping key includes identifier, source date semantics and status. Matching identifiers with conflicting date/status evidence therefore remain separate observations. Sector C page 23 and applicant page 5 are accepted as empty only under their exact reviewed source/hash/page conditions; any source drift remains fail-closed.",
        "",
    ]
    DOC_PATH.write_text(text.rstrip() + "\n".join(lines), encoding="utf-8")


def write_tests() -> None:
    if TEST_PATH.exists():
        raise SystemExit("Ferrara public bundle test unexpectedly already exists")
    lines = [
        "from white_list_archive.parsers.multi_prefecture_tables import ParsedBatch",
        "from white_list_archive.publishing.public_national_registry import (",
        "    FERRARA_RECONSTRUCTION_PARSER,",
        "    _adapt_ferrara_public_fields,",
        "    _bundle_digest,",
        ")",
        "",
        "",
        "MEMBER_HASHES = {",
        '    "A": "4fdf292b1538892c7b5ff79d3c0c14e0ed3b5830effb791316b0fddb8c90ae01",',
        '    "B": "97d9af0d587af0b7d93d31df33bd612440bf5be5b48b57872d436e2afeb164ec",',
        '    "C": "99f519101dccff84dddd9753f0d6fa27170c33b1982858afe9fdf9ebbc63c57e",',
        '    "D": "07c27b38e48a879aa0d1efff4710bf7dbbf1bb323e59f62eb0b0b796a75a46d8",',
        '    "E": "9cea950d37f653d0356edb9a46a7f43665a382e771c969bc93f7027f95fecf9e",',
        '    "F": "ac7dd77f1c4633c27a62c0ad7e074f507a10b091a327c2fc1072cfb52fd45664",',
        '    "G": "0657c7e0f0b9fb8ad7f0b341682716d695132e61131adc92407627a5cae82bae",',
        "}",
        "",
        "",
        "def test_ferrara_bundle_identity_is_order_stable_and_content_addressed():",
        '    expected = "bundle:f3d9093a8859e082ed304b1342ab7a3ae687f7735da04b3d363bbe7440543283"',
        "    assert _bundle_digest(MEMBER_HASHES) == expected",
        "    assert _bundle_digest(dict(reversed(list(MEMBER_HASHES.items())))) == expected",
        "    changed = dict(MEMBER_HASHES)",
        '    changed["G"] = "0" * 64',
        "    assert _bundle_digest(changed) != expected",
        "",
        "",
        "def _batch(fields):",
        '    return ParsedBatch(records=[{"source_fields": fields}], diagnostics={"public_records": 1})',
        "",
        "",
        "def test_ferrara_public_adapter_closes_ordinary_fields():",
        "    batch = _adapt_ferrara_public_fields(",
        '        _batch({"listing_date_raw": "01/02/2026", "expiry_date_raw": "01/02/2027", "notes": ["RINNOVO IN CORSO"], "physical_locators": ["p1:r2", "p2:r1"]}),',
        '        "ferrara-provincial-listed",',
        "    )",
        '    assert batch.records[0]["source_fields"]["physical_locators"] == ["p1:r2", "p2:r1"]',
        '    assert batch.records[0]["source_fields"]["listing_date_raw_variants"] == ["01/02/2026"]',
        "",
        "",
        "def test_ferrara_public_adapter_closes_shared_applicant_fields():",
        "    batch = _adapt_ferrara_public_fields(",
        '        _batch({"application_date_raw": "03/04/2026", "requested_activities_source": "demolizione edifici", "physical_locators": ["p1:r4"], "shared_publication_no_duplicate_ingest": True, "logical_series": ["ferrara-provincial-applicants", "ferrara-reconstruction-applicants"]}),',
        '        "ferrara-provincial-applicants",',
        "    )",
        '    assert "logical_series" not in batch.records[0]["source_fields"]',
        '    assert batch.records[0]["source_fields"]["application_date_raw_variants"] == ["03/04/2026"]',
        "",
        "",
        "def test_ferrara_public_adapter_preserves_reconstruction_provenance():",
        "    batch = _adapt_ferrara_public_fields(",
        '        _batch({"listing_date_raw": "01/01/2026", "expiry_date_raw": "01/01/2027", "sectors": ["B", "C"], "name_variants": ["Example S.r.l."], "office_variants": ["Ferrara"], "notes": [], "physical_locators": ["B:p1:t1:r2", "C:p1:t1:r2"], "physical_sector_observations": 2}),',
        "        FERRARA_RECONSTRUCTION_PARSER,",
        "    )",
        '    assert batch.records[0]["source_fields"]["sections"] == ["B", "C"]',
        '    assert batch.records[0]["source_fields"]["registered_office_variants"] == ["Ferrara"]',
        "",
    ]
    TEST_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    patch_registry()
    patch_config()
    patch_inventory()
    patch_doc()
    write_tests()


if __name__ == "__main__":
    main()
