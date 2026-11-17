#!/usr/bin/env python3
"""Parse cloud provider configs and emit a JSON map of customer → profiles.

Usage:
    discover_customers.py                          # AWS full map
    discover_customers.py --list                   # List all unique customers
    discover_customers.py --customer NAME          # AWS fuzzy-match
    discover_customers.py --provider hcloud        # Huawei Cloud full map
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_CONFIG = Path.home() / ".aws" / "config"
DEFAULT_HCLOUD_CONFIG = Path.home() / ".hcloud" / "config.json"

CUSTOMER_RE = re.compile(r"^\s*#\s*customer\s+(.+?)\s*$", re.IGNORECASE)
PROFILE_RE = re.compile(r"^\s*\[profile\s+([^\]]+)\]\s*$")
SECTION_RE = re.compile(r"^\s*\[([^\]]+)\]\s*$")


def parse_config(path: Path) -> dict:
    result: dict = {"_ungrouped": {"profiles": []}}
    current_customer = "_ungrouped"
    current_profile: dict | None = None

    if not path.exists():
        return result

    for raw in path.read_text().splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue

        cust_match = CUSTOMER_RE.match(line)
        if cust_match:
            current_customer = cust_match.group(1).strip()
            result.setdefault(current_customer, {"profiles": []})
            current_profile = None
            continue

        prof_match = PROFILE_RE.match(line)
        if prof_match:
            current_profile = {
                "name": prof_match.group(1).strip(),
                "account": None,
                "role": None,
                "region": None,
                "sso_session": None,
                "login_session": None,
            }
            result[current_customer]["profiles"].append(current_profile)
            continue

        sect_match = SECTION_RE.match(line)
        if sect_match and not prof_match:
            current_profile = None
            continue

        if current_profile is not None and "=" in line:
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip()
            if key == "sso_account_id":
                current_profile["account"] = val
            elif key == "sso_role_name":
                current_profile["role"] = val
            elif key == "region":
                current_profile["region"] = val
            elif key == "sso_session":
                current_profile["sso_session"] = val
            elif key == "login_session":
                current_profile["login_session"] = val

    return result


def parse_hcloud_config(path: Path) -> dict:
    """Parse ~/.hcloud/config.json and group profiles by customer prefix."""
    if not path.exists():
        return {}

    raw = json.loads(path.read_text())
    profiles = raw.get("profiles", [])
    current = raw.get("current", None)
    result: dict = {}

    for p in profiles:
        name = p.get("name", "")
        # Logic: prefix_env_role -> prefix is customer
        prefix = name.split("_")[0] if "_" in name else name
        prefix_upper = prefix.upper()
        result.setdefault(prefix_upper, {"provider": "hcloud", "profiles": []})
        result[prefix_upper]["profiles"].append({
            "name": name,
            "region": p.get("region") or None,
            "mode": p.get("mode") or None,
            "current": name == current,
        })

    return result


def find_customer(data: dict, query: str) -> list[str]:
    """Find customers matching the query. Returns a list of matching keys."""
    q = query.strip().lower()
    customers = [k for k in data.keys() if k != "_ungrouped"]

    # Exact match
    matches = [k for k in customers if k.lower() == q]
    if matches: return matches

    # Starts with
    matches = [k for k in customers if k.lower().startswith(q)]
    if matches: return matches

    # Contains
    matches = [k for k in customers if q in k.lower()]
    return matches


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=None)
    ap.add_argument("--customer", default=None)
    ap.add_argument("--list", action="store_true", help="List all customers found")
    ap.add_argument("--provider", default="aws", choices=["aws", "hcloud"],
                    help="Cloud provider (default: aws)")
    args = ap.parse_args()

    if args.provider == "hcloud":
        cfg_path = Path(args.config).expanduser() if args.config else DEFAULT_HCLOUD_CONFIG
        data = parse_hcloud_config(cfg_path)
    else:
        cfg_path = Path(args.config).expanduser() if args.config else DEFAULT_CONFIG
        data = parse_config(cfg_path)

    if args.list:
        customers = sorted([k for k in data.keys() if k != "_ungrouped"])
        print(json.dumps({"customers": customers}, indent=2))
        return 0

    if args.customer:
        matches = find_customer(data, args.customer)
        if not matches:
            print(json.dumps({"error": f"no customer match for '{args.customer}'", "suggestion": "Try --list to see all customers"}))
            return 1
        if len(matches) > 1:
            print(json.dumps({"error": f"multiple matches for '{args.customer}'", "matches": matches}))
            return 1

        match = matches[0]
        print(json.dumps({match: data[match]}, indent=2))
        return 0

    # Default: print all data
    print(json.dumps(data, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
