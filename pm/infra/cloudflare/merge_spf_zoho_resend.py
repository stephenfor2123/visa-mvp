#!/usr/bin/env python3
"""Merge Zoho + Resend into a single SPF TXT record on Cloudflare.

Requires:
  export CLOUDFLARE_API_TOKEN=<token with Zone.DNS Edit for htexvisa.com>

Usage:
  python3 pm/infra/cloudflare/merge_spf_zoho_resend.py
  python3 pm/infra/cloudflare/merge_spf_zoho_resend.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

ZONE = "htexvisa.com"
MERGED_SPF = "v=spf1 include:zohomail.com include:amazonses.com ~all"


def _api(method: str, path: str, token: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if not payload.get("success"):
        raise RuntimeError(json.dumps(payload.get("errors", payload), ensure_ascii=False))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    if not token:
        print("ERROR: set CLOUDFLARE_API_TOKEN (Zone.DNS Edit for htexvisa.com)")
        return 1

    try:
        zone_resp = _api("GET", f"/zones?name={ZONE}", token)
        zone_id = zone_resp["result"][0]["id"]

        records_resp = _api(
            "GET",
            f"/zones/{zone_id}/dns_records?type=TXT&name={ZONE}",
            token,
        )
        spf_records = [
            r
            for r in records_resp["result"]
            if r.get("content", "").startswith('"v=spf1') or r.get("content", "").startswith("v=spf1")
        ]
        if not spf_records:
            print("ERROR: no SPF TXT record found on @")
            return 1
        if len(spf_records) > 1:
            print("WARN: multiple SPF records found; only the first will be updated")

        record = spf_records[0]
        current = record["content"].strip('"')
        print(f"current: {current}")
        print(f"target:  {MERGED_SPF}")

        if current == MERGED_SPF:
            print("OK: SPF already merged")
            return 0

        if args.dry_run:
            print("DRY RUN: no changes made")
            return 0

        _api(
            "PATCH",
            f"/zones/{zone_id}/dns_records/{record['id']}",
            token,
            {"content": MERGED_SPF, "ttl": record.get("ttl", 1)},
        )
        print("OK: SPF updated")
        return 0
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code}: {body}")
        return 1
    except Exception as exc:  # pragma: no cover
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
