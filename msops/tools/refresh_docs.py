"""Refresh customer docs from AWS live state."""
from __future__ import annotations
import json
import subprocess
from pathlib import Path
from typing import Optional


def _write_or_diff(doc_path: Path, content: str, dry_run: bool) -> dict:
    """Write the doc, or (dry run) return the unified diff against what is there now.

    The doc is overwritten whole, so the diff is the only chance to see what a stale
    doc still said before it is gone."""
    import difflib
    old = doc_path.read_text(encoding="utf-8", errors="ignore") if doc_path.exists() else ""
    diff = "".join(difflib.unified_diff(old.splitlines(True), content.splitlines(True),
                                        fromfile=f"{doc_path.name} (sekarang)",
                                        tofile=f"{doc_path.name} (live)", n=1))
    changed = sum(1 for l in diff.splitlines() if l[:1] in "+-" and not l.startswith(("+++", "---")))
    if dry_run:
        return {"path": str(doc_path), "dry_run": True, "changed_lines": changed,
                "diff": diff[:6000] + ("\n... (dipotong)" if len(diff) > 6000 else "")}
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text(content)
    return {"path": str(doc_path), "dry_run": False, "changed_lines": changed}


def _aws_cmd(args: list[str], profile: str, region: str) -> Optional[dict]:
    """Run AWS CLI command and return parsed JSON."""
    cmd = ["aws"] + args + ["--profile", profile, "--region", region, "--output", "json"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            return json.loads(r.stdout)
    except Exception:
        pass
    return None


def refresh_instances(root: Path, customer_folder: str, profile: str, region: str,
                      dry_run: bool = False) -> dict:
    """Fetch EC2 instances and RDS and write to instances.md."""
    lines = [f"# {customer_folder} — Instances\n", f"_Auto-generated from AWS live state. Profile: {profile}, Region: {region}_\n"]

    # EC2
    ec2 = _aws_cmd(["ec2", "describe-instances", "--query",
                     "Reservations[].Instances[].[InstanceId,InstanceType,State.Name,PrivateIpAddress,PublicIpAddress,Tags[?Key=='Name'].Value|[0],PlatformDetails]"],
                    profile, region)
    lines.append("\n## EC2 Instances\n")
    lines.append("| Name | Instance ID | Type | State | Private IP | Public IP | Platform |")
    lines.append("|------|------------|------|-------|------------|-----------|----------|")
    if ec2:
        for r in ec2:
            name = r[5] or "-"
            lines.append(f"| {name} | {r[0]} | {r[1]} | {r[2]} | {r[3] or '-'} | {r[4] or '-'} | {r[6] or '-'} |")

    # RDS
    rds = _aws_cmd(["rds", "describe-db-instances", "--query",
                     "DBInstances[].[DBInstanceIdentifier,DBInstanceClass,Engine,EngineVersion,DBInstanceStatus,Endpoint.Address]"],
                    profile, region)
    lines.append("\n## RDS Instances\n")
    lines.append("| DB Identifier | Class | Engine | Version | Status | Endpoint |")
    lines.append("|--------------|-------|--------|---------|--------|----------|")
    if rds:
        for r in rds:
            lines.append(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5] or '-'} |")

    content = "\n".join(lines) + "\n"
    doc_path = root / customer_folder / "docs" / "instances.md"
    written = _write_or_diff(doc_path, content, dry_run)
    return {**written, "ec2_count": len(ec2) if ec2 else 0, "rds_count": len(rds) if rds else 0}


def refresh_network(root: Path, customer_folder: str, profile: str, region: str,
                    dry_run: bool = False) -> dict:
    """Fetch VPC, subnets, security groups and write to network.md."""
    lines = [f"# {customer_folder} — Network\n", f"_Auto-generated from AWS live state. Profile: {profile}, Region: {region}_\n"]

    # VPCs
    vpcs = _aws_cmd(["ec2", "describe-vpcs", "--query",
                      "Vpcs[].[VpcId,CidrBlock,State,Tags[?Key=='Name'].Value|[0]]"],
                     profile, region)
    lines.append("\n## VPCs\n")
    lines.append("| Name | VPC ID | CIDR | State |")
    lines.append("|------|--------|------|-------|")
    if vpcs:
        for v in vpcs:
            lines.append(f"| {v[3] or '-'} | {v[0]} | {v[1]} | {v[2]} |")

    # Subnets
    subnets = _aws_cmd(["ec2", "describe-subnets", "--query",
                          "Subnets[].[SubnetId,VpcId,CidrBlock,AvailabilityZone,Tags[?Key=='Name'].Value|[0]]"],
                         profile, region)
    lines.append("\n## Subnets\n")
    lines.append("| Name | Subnet ID | VPC | CIDR | AZ |")
    lines.append("|------|-----------|-----|------|----|")
    if subnets:
        for s in subnets:
            lines.append(f"| {s[4] or '-'} | {s[0]} | {s[1]} | {s[2]} | {s[3]} |")

    content = "\n".join(lines) + "\n"
    doc_path = root / customer_folder / "docs" / "network.md"
    written = _write_or_diff(doc_path, content, dry_run)
    return {**written, "vpc_count": len(vpcs) if vpcs else 0, "subnet_count": len(subnets) if subnets else 0}


def refresh_customer_docs(root: Path, customer_folder: str, profile: str, region: str,
                          doc_type: str = "all", dry_run: bool = True) -> dict:
    """Refresh docs from AWS live state. doc_type: all, instances, network.
    dry_run (default) returns the diff per doc instead of writing."""
    results = {"profile": profile, "region": region, "dry_run": dry_run}
    if doc_type in ("all", "instances"):
        results["instances"] = refresh_instances(root, customer_folder, profile, region, dry_run)
    if doc_type in ("all", "network"):
        results["network"] = refresh_network(root, customer_folder, profile, region, dry_run)
    return results
