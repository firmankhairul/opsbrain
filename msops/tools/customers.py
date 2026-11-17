from __future__ import annotations
import subprocess
from pathlib import Path
from typing import Optional
import yaml

from msops.models import AccountInfo, CustomerInfo, ProviderInfo

REPO_ROOT = Path(__file__).resolve().parents[2]
IGNORED_FOLDERS = {
    "docs", "scripts", "reports", "archive", "monthly-report",
    "template", "tests", "mcp", "msops", "kb", ".claude", ".kiro",
    ".gemini", ".opencode", ".git", "repo", "sandbox-ms", "non-customer",
}


def _yaml_to_customer(data: dict) -> CustomerInfo:
    providers = []
    for p in data.get("providers", []):
        accounts = [
            AccountInfo(
                # GCP projects and Huawei/one-off entries carry no CLI profile.
                # a["profile"] raised KeyError and took down every tool that
                # loads the full customer list.
                profile=a.get("profile"),
                region=a.get("region"),
                id=a.get("id"),
                role=a.get("role"),
                purpose=a.get("purpose", "production"),
                host=a.get("host"),
            )
            for a in p.get("accounts", [])
        ]
        providers.append(ProviderInfo(provider=p["provider"], accounts=accounts))
    return CustomerInfo(
        name=data["name"],
        display_name=data.get("display_name", data["name"]),
        folder=data["folder"],
        providers=providers,
        aliases=data.get("aliases") or [],
        engagements=data.get("engagements") or [],
        github_project=data.get("github_project"),
    )


def load_customers(root: Path = REPO_ROOT) -> list[CustomerInfo]:
    customers = []
    for path in sorted(root.iterdir()):
        if not path.is_dir():
            continue
        if path.name in IGNORED_FOLDERS or path.name.startswith("."):
            continue
        yaml_file = path / "customer.yaml"
        if not yaml_file.exists():
            continue
        data = yaml.safe_load(yaml_file.read_text())
        customers.append(_yaml_to_customer(data))
    return customers


def find_customer(customers: list[CustomerInfo], query: str) -> Optional[CustomerInfo]:
    q = query.strip().lower()
    # 1. exact name
    for c in customers:
        if c.name.lower() == q:
            return c
    # 2. account ID exact
    for c in customers:
        if q in [aid.lower() for aid in c.all_account_ids()]:
            return c
    # 3. profile exact
    for c in customers:
        if q in [p.lower() for p in c.all_profiles()]:
            return c
    # 4. name starts-with
    for c in customers:
        if c.name.lower().startswith(q):
            return c
    # 5. display_name contains
    for c in customers:
        if q in c.display_name.lower():
            return c
    # 6. name contains
    for c in customers:
        if q in c.name.lower():
            return c
    # 7. folder name match (case-insensitive)
    for c in customers:
        if c.folder.lower() == q or q in c.folder.lower():
            return c
    # 8. fuzzy: any word in query matches folder/name/display_name
    for c in customers:
        targets = f"{c.name} {c.display_name} {c.folder}".lower()
        if all(w in targets for w in q.split()):
            return c
    # 9. alias or sub-engagement (e.g. "nabati" -> acme-retail, "bisnis" -> token)
    for c in customers:
        if any(q == t for t in c.search_terms()):
            return c
    for c in customers:
        if any(q in t for t in c.search_terms()):
            return c
    # 10. initials match (e.g. "ffi" -> "Frisian Flag Indonesia")
    for c in customers:
        words = c.display_name.split()
        if len(words) > 1:
            initials = "".join(w[0] for w in words).lower()
            if initials == q:
                return c
    return None


def get_all_accounts(customers: list[CustomerInfo]) -> dict:
    result = {}
    for c in customers:
        for p in c.providers:
            for acc in p.accounts:
                if acc.id:
                    result[acc.id] = {
                        "customer": c.name,
                        "folder": c.folder,
                        "profile": acc.profile,
                        "region": acc.region,
                        "provider": p.provider,
                        "purpose": acc.purpose,
                    }
    return result


# Customer doc templates live in template/customer/ (repo override) with a copy shipped
# next to the package as fallback. CORE_DOCS are created for every customer; the rest are
# optional and created on demand (doc_create_customer_doc) or when the provider calls for
# it (odoo -> odoo.md).
CORE_DOCS = ("README.md", "overview.md", "instances.md", "network.md", "access.md")
OPTIONAL_DOCS = ("security.md", "kubernetes.md", "odoo.md", "cicd.md", "monitoring.md",
                 "backup-dr.md", "contacts.md")
_PROVIDER_DOCS = {"odoo": ("odoo.md",)}
_PKG_TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "template" / "customer"


def _customer_template(root: Path, name: str) -> str:
    for base in (root / "template" / "customer", _PKG_TEMPLATE_DIR):
        p = base / name
        if p.exists():
            return p.read_text(encoding="utf-8")
    raise FileNotFoundError(f"template customer/{name} tidak ada")


def render_customer_doc(root: Path, name: str, display_name: str, folder: str,
                        doc: str) -> str:
    from datetime import date
    return (_customer_template(root, doc)
            .replace("{name}", name).replace("{display_name}", display_name)
            .replace("{folder}", folder).replace("{date}", date.today().isoformat()))


def create_customer_doc(root: Path, folder: str, doc: str, dry_run: bool = True):
    """Add one optional doc (OPTIONAL_DOCS) to an existing customer; never overwrites."""
    if doc not in OPTIONAL_DOCS and doc not in CORE_DOCS:
        raise ValueError(f"doc harus salah satu dari {', '.join(CORE_DOCS + OPTIONAL_DOCS)}")
    cdir = root / folder
    y = cdir / "customer.yaml"
    if not y.exists():
        raise FileNotFoundError(f"{folder}/customer.yaml tidak ada")
    data = yaml.safe_load(y.read_text(encoding="utf-8")) or {}
    target = cdir / ("README.md" if doc == "README.md" else f"docs/{doc}")
    if target.exists():
        raise FileExistsError(f"{target} sudah ada — tidak ditimpa")
    content = render_customer_doc(root, data.get("name", folder), data.get("display_name", folder),
                                  folder, doc)
    if dry_run:
        return target, content
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    return target


# Monthly reports live in monthly-report/output/<slug>/, not per customer.
# docs/standards/ops-docs-schema.md: contract/ for the SoW, reports/ for what goes to the
# customer, assessment/ for standalone analyses. tickets/ is legacy but still scaffolded so
# the hygiene audit sees the same shape everywhere.
SUBFOLDERS = ["docs", "contract", "tickets", "mop", "incident_report",
              "mom", "knowledge-base", "assessment", "reports"]


def scaffold_customer(root: Path, name: str, folder: str, providers: list[dict]) -> Path:
    customer_dir = root / folder
    for sub in SUBFOLDERS:
        (customer_dir / sub).mkdir(parents=True, exist_ok=True)

    yaml_data = {
        "name": name,
        "display_name": name,
        "folder": folder,
        "providers": providers,
    }
    (customer_dir / "customer.yaml").write_text(
        yaml.dump(yaml_data, default_flow_style=False, allow_unicode=True)
    )

    wanted = list(CORE_DOCS)
    for p in providers or []:
        wanted += [d for d in _PROVIDER_DOCS.get(str(p.get("provider", "")).lower(), ()) if d not in wanted]
    for filename in wanted:
        doc_path = customer_dir / ("README.md" if filename == "README.md" else f"docs/{filename}")
        if not doc_path.exists():
            doc_path.write_text(render_customer_doc(root, name, name, folder, filename))

    return customer_dir
