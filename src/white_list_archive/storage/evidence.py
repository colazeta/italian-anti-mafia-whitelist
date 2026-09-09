"""Content-addressed S3 evidence with verified retrieval before DB promotion."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit


@dataclass(frozen=True)
class StoreConfig:
    bucket: str
    endpoint: str
    region: str
    policy_evidence: str

    def __post_init__(self):
        parsed = urlsplit(self.endpoint)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or
                parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/")):
            raise ValueError("Evidence endpoint must be an HTTPS origin without credentials")
        if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", self.bucket):
            raise ValueError("Invalid evidence bucket")
        if not self.region.strip() or not self.policy_evidence.strip():
            raise ValueError("Region and reviewed retention/private-access policy evidence are required")

    @classmethod
    def from_env(cls):
        names = ("EVIDENCE_BUCKET", "EVIDENCE_ENDPOINT", "EVIDENCE_REGION", "EVIDENCE_POLICY_EVIDENCE")
        if any(not os.environ.get(n) for n in names):
            raise ValueError("Configure EVIDENCE_BUCKET, EVIDENCE_ENDPOINT, EVIDENCE_REGION and EVIDENCE_POLICY_EVIDENCE")
        return cls(*(os.environ[n] for n in names))


def object_key(manifest):
    digest = manifest["sha256"]
    if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise ValueError("Invalid SHA-256")
    if type(manifest["byte_size"]) is not int or manifest["byte_size"] <= 0:
        raise ValueError("Invalid byte size")
    # Byte identity must not depend on a filename or a potentially changing MIME label.
    return f"sha256/{digest[:2]}/{digest}"


class EvidenceStore:
    def __init__(self, client, config: StoreConfig):
        self.client, self.config = client, config

    def read_verified(self, manifest) -> bytes:
        key = object_key(manifest)
        response = self.client.get_object(Bucket=self.config.bucket, Key=key)
        stream = response["Body"]
        try:
            data = stream.read(manifest["byte_size"] + 1)
        finally:
            stream.close()
        if len(data) != manifest["byte_size"] or hashlib.sha256(data).hexdigest() != manifest["sha256"]:
            raise ValueError("Stored evidence failed independent size/SHA-256 verification")
        return data

    def archive(self, path: Path, manifest: dict) -> dict:
        key = object_key(manifest)
        # Buffer the verified bytes once: a changing local file cannot change the upload.
        with path.open("rb") as f:
            data = f.read(manifest["byte_size"] + 1)
        if len(data) != manifest["byte_size"] or hashlib.sha256(data).hexdigest() != manifest["sha256"]:
            raise ValueError("Local evidence does not match frozen capture manifest")
        created = True
        try:
            self.client.put_object(Bucket=self.config.bucket, Key=key, Body=data,
                                   ContentType=manifest["content_type"], IfNoneMatch="*",
                                   Metadata={"sha256": manifest["sha256"]})
        except Exception as exc:
            code = getattr(exc, "response", {}).get("Error", {}).get("Code")
            code = str(code) if code is not None else None
            # S3 normally returns 412 for an existing conditional target. Cloudflare R2
            # can instead return ObjectLockedByBucketPolicy when Bucket Lock protects
            # the already-created key. Either response is only evidence that an object
            # may already exist; full GET + SHA-256 verification below remains mandatory.
            if code not in ("PreconditionFailed", "412", "ObjectLockedByBucketPolicy", "10069"):
                raise
            created = False
        # Existing-object responses can still hide a conflicting object. Never trust
        # status code, HEAD, ETag or metadata as byte-identity evidence.
        self.read_verified(manifest)
        return {"schema_version": 1, "sha256": manifest["sha256"],
                "byte_size": manifest["byte_size"], "content_type": manifest["content_type"],
                "storage_uri": f"{self.config.endpoint.rstrip('/')}/{self.config.bucket}/{key}",
                "endpoint": self.config.endpoint, "created": created,
                "verified_at": datetime.now(timezone.utc).isoformat(),
                "policy_evidence": self.config.policy_evidence,
                "resource_url": manifest["resource_url"], "captured_at": manifest["captured_at"],
                "reference_date": manifest["reference_date"],
                "manifest_sha256": hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
                "database_promoted": False}

    def promote(self, conn, manifest: dict) -> None:
        """Caller owns the transaction. Only update an already linked ContentObject."""
        uri = f"{self.config.endpoint.rstrip('/')}/{self.config.bucket}/{object_key(manifest)}"
        with conn.cursor() as cur:
            cur.execute("""SELECT content_object_id, file_size, mime_type, storage_uri, storage_status_code
                           FROM source.content_object WHERE sha256=%s FOR UPDATE""", (manifest["sha256"],))
            row = cur.fetchone()
            if not row or row[1:3] != (manifest["byte_size"], manifest["content_type"]):
                raise ValueError("Existing ContentObject missing or metadata mismatch")
            if row[4] == "durable" and row[3] != uri:
                raise ValueError("Refusing to replace an existing durable location")
            # Receipts alone cannot authorise promotion: independently read again.
            self.read_verified(manifest)
            cur.execute("""UPDATE source.content_object SET storage_uri=%s, storage_status_code='durable'
                           WHERE content_object_id=%s""", (uri, row[0]))


def client_for(config):
    import boto3
    from botocore.config import Config
    return boto3.client("s3", endpoint_url=config.endpoint, region_name=config.region,
                        config=Config(signature_version="s3v4", connect_timeout=10, read_timeout=60,
                                      retries={"max_attempts": 3, "mode": "standard"}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("archive", "retrieve"))
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--file", type=Path, required=True, help="Input for archive; new output for retrieve")
    parser.add_argument("--receipt", type=Path, help="New private receipt path, required for archive")
    parser.add_argument("--promote", action="store_true", help="Update existing ContentObject using EVIDENCE_DATABASE_URL")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    object_key(manifest)
    if args.action == "archive" and (not args.receipt or args.receipt.exists()):
        parser.error("Archive requires a new receipt path; previous receipts cannot be overwritten")
    if args.promote and (args.action != "archive" or not os.environ.get("EVIDENCE_DATABASE_URL")):
        parser.error("Promotion requires archive and EVIDENCE_DATABASE_URL")
    config = StoreConfig.from_env()
    store = EvidenceStore(client_for(config), config)
    if args.action == "retrieve":
        data = store.read_verified(manifest)
        with args.file.open("xb") as f:
            f.write(data)
    else:
        receipt = store.archive(args.file, manifest)
        if args.promote:
            import psycopg
            with psycopg.connect(os.environ["EVIDENCE_DATABASE_URL"]) as conn:
                store.promote(conn, manifest)
            receipt["database_promoted"] = True
        with args.receipt.open("x") as f:
            json.dump(receipt, f, indent=2)
            f.write("\n")
    print("Evidence integrity verified; output remains private.")


if __name__ == "__main__":
    main()
