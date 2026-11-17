from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AccountInfo:
    profile: str
    region: Optional[str] = None
    id: Optional[str] = None
    role: Optional[str] = None
    purpose: str = "production"
    host: Optional[str] = None  # for odoo/non-cloud providers


@dataclass
class ProviderInfo:
    provider: str  # aws | huawei | azure | gcp | odoo
    accounts: list[AccountInfo] = field(default_factory=list)


@dataclass
class CustomerInfo:
    name: str
    display_name: str
    folder: str
    providers: list[ProviderInfo] = field(default_factory=list)
    # Other names this customer is known by (e.g. acme-retail is also "Nabati").
    aliases: list[str] = field(default_factory=list)
    # Sub-engagements for folders holding several unrelated clients
    # (token/ holds Primaya Hospital and Bisnis Indonesia).
    engagements: list[dict] = field(default_factory=list)
    # GitHub Projects board number for customers that have one; issues get
    # attached there after sync. None means no board.
    github_project: int | None = None

    def all_profiles(self) -> list[str]:
        # Skip accounts with no CLI profile (GCP projects, Huawei entries
        # pending credentials). Callers lowercase these, so a None here
        # crashes every lookup that reaches such an account.
        return [acc.profile for p in self.providers for acc in p.accounts if acc.profile]

    def search_terms(self) -> list[str]:
        """Every string this customer should be findable by."""
        terms = [self.name, self.display_name, self.folder, *self.aliases]
        for e in self.engagements:
            if e.get("name"):
                terms.append(e["name"])
            if e.get("aws_profile"):
                terms.append(e["aws_profile"])
        return [t.lower() for t in terms if t]

    def all_account_ids(self) -> list[str]:
        return [acc.id for p in self.providers for acc in p.accounts if acc.id]

    def providers_of(self, provider: str) -> list[ProviderInfo]:
        return [p for p in self.providers if p.provider == provider]
