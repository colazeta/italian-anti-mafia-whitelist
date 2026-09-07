from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

try:
    import psycopg
except ImportError as exc:  # pragma: no cover
    psycopg = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

from white_list_archive.publishing.model_population import OBJECTS


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return str(value)


def _csv_value(value: Any) -> str:
    safe = _json_safe(value)
    if isinstance(safe, (dict, list)):
        return json.dumps(safe, ensure_ascii=False, sort_keys=True)
    return "" if safe is None else str(safe)


def _columns(cur, schema: str, table: str) -> list[dict[str, str]]:
    cur.execute(
        """
        SELECT column_name, data_type, udt_name
        FROM information_schema.columns
        WHERE table_schema=%s AND table_name=%s
        ORDER BY ordinal_position
        """,
        (schema, table),
    )
    return [
        {"name": row[0], "data_type": row[1], "udt_name": row[2]}
        for row in cur.fetchall()
    ]


def _primary_key_columns(cur, schema: str, table: str) -> list[str]:
    cur.execute(
        """
        SELECT a.attname
        FROM pg_index i
        JOIN pg_class c ON c.oid=i.indrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        JOIN unnest(i.indkey) WITH ORDINALITY AS k(attnum, ord) ON TRUE
        JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum=k.attnum
        WHERE i.indisprimary AND n.nspname=%s AND c.relname=%s
        ORDER BY k.ord
        """,
        (schema, table),
    )
    return [row[0] for row in cur.fetchall()]


def _quoted_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def build_table_bundle(conn, output_dir: Path, preview_limit: int = 50) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    objects: dict[str, Any] = {}

    with conn.cursor() as cur:
        for code, label, qualified_table, kind, meaning in OBJECTS:
            schema, table = qualified_table.split(".", 1)
            columns = _columns(cur, schema, table)
            if not columns:
                raise ValueError(f"No columns found for {qualified_table}")
            column_names = [item["name"] for item in columns]
            order_columns = _primary_key_columns(cur, schema, table) or column_names[:1]
            qtable = f"{_quoted_identifier(schema)}.{_quoted_identifier(table)}"
            order_sql = ", ".join(_quoted_identifier(item) for item in order_columns)

            cur.execute(f"SELECT count(*) FROM {qtable}")
            count = int(cur.fetchone()[0])

            cur.execute(f"SELECT * FROM {qtable} ORDER BY {order_sql} LIMIT %s", (preview_limit,))
            preview_rows = [
                {name: _json_safe(value) for name, value in zip(column_names, row)}
                for row in cur.fetchall()
            ]

            csv_path = tables_dir / f"{code}.csv"
            cur.execute(f"SELECT * FROM {qtable} ORDER BY {order_sql}")
            with csv_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(column_names)
                while True:
                    batch = cur.fetchmany(1000)
                    if not batch:
                        break
                    writer.writerows([_csv_value(value) for value in row] for row in batch)

            objects[code] = {
                "object_code": code,
                "label": label,
                "table": qualified_table,
                "layer": kind,
                "meaning": meaning,
                "count": count,
                "columns": columns,
                "preview_limit": preview_limit,
                "preview_rows": preview_rows,
                "csv_path": f"tables/{code}.csv",
            }

    return {"preview_limit": preview_limit, "objects": objects}


def build_from_dsn(dsn: str, output_dir: Path, preview_limit: int = 50) -> dict[str, Any]:
    if psycopg is None:
        raise RuntimeError("psycopg is required; install the 'database' extra") from _IMPORT_ERROR
    with psycopg.connect(dsn) as conn:
        return build_table_bundle(conn, output_dir, preview_limit)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export browsable database-table previews plus full internal CSVs for Dataset Explorer."
    )
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--preview-limit", type=int, default=50)
    args = parser.parse_args()
    if args.preview_limit < 1 or args.preview_limit > 500:
        raise SystemExit("--preview-limit must be between 1 and 500")
    payload = build_from_dsn(args.dsn, args.output_dir, args.preview_limit)
    payload_json = json.dumps(payload, ensure_ascii=False)
    catalog_path = args.output_dir / "table_catalog.json"
    catalog_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    js_path = args.output_dir / "table_catalog.js"
    js_path.write_text(f"window.__TABLE_CATALOG__={payload_json};\n", encoding="utf-8")
    print(
        json.dumps(
            {"output": str(catalog_path), "javascript": str(js_path), "objects": len(payload["objects"])},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
