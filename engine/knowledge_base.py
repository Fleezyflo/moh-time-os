"""Knowledge base: ingest clients, team, projects from source systems."""

import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from engine.asana_client import list_projects, list_workspaces
from engine.gogcli import run_gog

from lib import paths

KB_PATH = str(paths.config_dir() / "knowledge_base.json")
FORECAST_SHEET_ID = "1iTWOo77r1l-65AwDh2KAnhKg1ch7X1XLqxtWQQgorVI"


@dataclass
class TeamMember:
    name: str
    title: str
    department: str
    email: str | None
    active: bool


@dataclass
class Client:
    name: str
    type: str  # retainer, project, forecast
    status: str  # active, historical, pipeline
    domains: list[str]
    contacts: list[str]


@dataclass
class Project:
    name: str
    client: str | None
    status: str  # active, completed, on_hold
    source: str  # asana, manual
    asana_gid: str | None


@dataclass
class KnowledgeBase:
    team: list[TeamMember]
    clients: list[Client]
    projects: list[Project]
    updated_at: str

    def to_dict(self) -> dict:
        return {
            "team": [asdict(t) for t in self.team],
            "clients": [asdict(c) for c in self.clients],
            "projects": [asdict(p) for p in self.projects],
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "KnowledgeBase":
        return cls(
            team=[TeamMember(**t) for t in d.get("team", [])],
            clients=[Client(**c) for c in d.get("clients", [])],
            projects=[Project(**p) for p in d.get("projects", [])],
            updated_at=d.get("updated_at", ""),
        )


def load_kb() -> KnowledgeBase | None:
    if not os.path.exists(KB_PATH):
        return None
    try:
        with open(KB_PATH) as f:
            return KnowledgeBase.from_dict(json.load(f))
    except Exception:
        return None


def save_kb(kb: KnowledgeBase) -> None:
    os.makedirs(os.path.dirname(KB_PATH), exist_ok=True)
    with open(KB_PATH, "w") as f:
        json.dump(kb.to_dict(), f, indent=2, ensure_ascii=False)


def ingest_team_from_forecast(account: str = "molham@hrmny.co") -> list[TeamMember]:
    """Pull team from Forecast sheet salary section."""

    # Get salary rows (around rows 225-320 based on earlier analysis)
    res = run_gog(
        ["sheets", "get", FORECAST_SHEET_ID, "Forecast!A225:BK350", "--json"],
        account=account,
        timeout=60,
    )

    if not res.ok:
        print(f"Error fetching team: {res.error}")
        return []

    rows = res.data.get("values", [])
    team = []
    current_dept = "Unknown"

    # Find current month column (Jan 2026 = ~48, Feb 2026 = ~49)
    # We'll use column 49 (Feb 2026) as reference
    CURRENT_MONTH_COL = 49

    for row in rows:
        if len(row) < 3:
            continue

        # Check for department header
        if row[0] and "Salaries" not in str(row[0]):
            # Could be department header
            dept = str(row[0]).strip()
            if dept and dept not in ("", "ADMIN COSTS", "TOTAL", "FIXED"):
                current_dept = dept

        # Check for salary row
        if len(row) > 0 and "Salaries" in str(row[0]):
            title = str(row[1]).strip() if len(row) > 1 else ""
            name = str(row[2]).strip() if len(row) > 2 else ""

            # Skip budget placeholders
            if not name or name.lower() == "budget":
                continue

            # Check if active (has salary in current month)
            current_salary = ""
            if len(row) > CURRENT_MONTH_COL:
                current_salary = str(row[CURRENT_MONTH_COL]).strip()

            # Parse salary - active if > 0
            active = False
            if current_salary:
                # Remove formatting
                clean = re.sub(r"[^\d.]", "", current_salary)
                try:
                    if float(clean) > 0:
                        active = True
                except ValueError:
                    pass

            # Infer email from name (simple heuristic)
            email = None
            name_parts = name.lower().split()
            if len(name_parts) >= 2:
                # firstname@hrmny.co pattern
                email = f"{name_parts[0]}@hrmny.co"

            team.append(
                TeamMember(
                    name=name,
                    title=title,
                    department=current_dept,
                    email=email,
                    active=active,
                )
            )

    return team


def ingest_clients_from_forecast(account: str = "molham@hrmny.co") -> list[Client]:
    """Pull clients from Forecast sheet revenue section."""

    # Get revenue rows (rows 5-100 based on earlier analysis)
    res = run_gog(
        ["sheets", "get", FORECAST_SHEET_ID, "Forecast!A5:BK100", "--json"],
        account=account,
        timeout=60,
    )

    if not res.ok:
        print(f"Error fetching clients: {res.error}")
        return []

    rows = res.data.get("values", [])
    clients = []
    seen_names = set()

    # Current month columns (Jan 2026 = ~48, Feb 2026 = ~49)
    CURRENT_MONTH_COL = 49

    for row in rows:
        if len(row) < 3:
            continue

        row_type = str(row[0]).strip() if row[0] else ""

        # Only process Revenue rows
        if not row_type.startswith("Revenue"):
            continue

        client_name = str(row[1]).strip() if len(row) > 1 else ""
        engagement_type = str(row[2]).strip().lower() if len(row) > 2 else ""

        # Skip empty, TBD, or already seen
        if not client_name or client_name.lower() in ("tbd", "others", ""):
            continue
        if client_name in seen_names:
            continue
        seen_names.add(client_name)

        # Determine type
        if "forecast" in row_type.lower():
            client_type = "forecast"
        elif "retainer" in engagement_type:
            client_type = "retainer"
        else:
            client_type = "project"

        # Check if active (has revenue in current or future months)
        has_current = False
        has_future = False

        for col_idx in range(CURRENT_MONTH_COL, min(len(row), CURRENT_MONTH_COL + 12)):
            val = str(row[col_idx]).strip() if col_idx < len(row) else ""
            clean = re.sub(r"[^\d.]", "", val)
            try:
                if float(clean) > 0:
                    if col_idx == CURRENT_MONTH_COL:
                        has_current = True
                    else:
                        has_future = True
            except ValueError:
                pass

        if has_current or has_future:
            status = "active"
        elif client_type == "forecast":
            status = "pipeline"
        else:
            status = "historical"

        # Try to infer domain from name
        domains = []
        name_lower = client_name.lower().replace(" ", "")
        # Common patterns
        if "gargash" in name_lower:
            domains.append("gargash.com")
        elif "gmg" in name_lower:
            domains.append("gmg.com")
        # Add more as needed

        clients.append(
            Client(
                name=client_name,
                type=client_type,
                status=status,
                domains=domains,
                contacts=[],
            )
        )

    return clients


def ingest_projects_from_asana() -> list[Project]:
    """Pull projects from Asana."""

    projects = []

    try:
        workspaces = list_workspaces()
    except Exception as e:
        print(f"Asana error: {e}")
        return []

    for ws in workspaces:
        if "hrmny" not in ws.get("name", "").lower():
            continue

        try:
            asana_projects = list_projects(ws["gid"])
        except Exception as e:
            print(f"Error listing projects: {e}")
            continue

        for p in asana_projects:
            name = p.get("name", "")

            # Try to extract client from project name
            # Common patterns: "[ClientName] Project" or "ClientName | Project"
            client = None
            if "|" in name:
                client = name.split("|")[0].strip()
            elif name.startswith("[") and "]" in name:
                client = name[1 : name.index("]")].strip()

            projects.append(
                Project(
                    name=name,
                    client=client,
                    status="active",  # Asana archived projects filtered by default
                    source="asana",
                    asana_gid=p.get("gid"),
                )
            )

    return projects


def build_knowledge_base(account: str = "molham@hrmny.co") -> KnowledgeBase:
    """Build complete knowledge base from all sources."""

    print("Ingesting team from Forecast sheet...")
    team = ingest_team_from_forecast(account)
    print(
        f"  Found {len(team)} team members ({sum(1 for t in team if t.active)} active)"
    )

    print("Ingesting clients from Forecast sheet...")
    clients = ingest_clients_from_forecast(account)
    print(
        f"  Found {len(clients)} clients ({sum(1 for c in clients if c.status == 'active')} active)"
    )

    print("Ingesting projects from Asana...")
    projects = ingest_projects_from_asana()
    print(f"  Found {len(projects)} projects")

    kb = KnowledgeBase(
        team=team,
        clients=clients,
        projects=projects,
        updated_at=datetime.now(UTC).isoformat(),
    )

    save_kb(kb)
    print(f"\nKnowledge base saved to {KB_PATH}")

    return kb


def lookup_client_by_domain(domain: str) -> Client | None:
    """Look up client by email domain."""
    kb = load_kb()
    if not kb:
        return None

    domain = domain.lower()
    for client in kb.clients:
        if domain in [d.lower() for d in client.domains]:
            return client
    return None


def lookup_team_member_by_name(name: str) -> TeamMember | None:
    """Look up team member by name (partial match)."""
    kb = load_kb()
    if not kb:
        return None

    name = name.lower()
    for member in kb.team:
        if name in member.name.lower():
            return member
    return None


def is_known_client(name: str) -> bool:
    """Check if name matches a known client."""
    kb = load_kb()
    if not kb:
        return False

    name = name.lower()
    for client in kb.clients:
        if name in client.name.lower() or client.name.lower() in name:
            return True
    return False


if __name__ == "__main__":
    kb = build_knowledge_base()

    print("\n" + "=" * 50)
    print("ACTIVE TEAM:")
    for t in kb.team:
        if t.active:
            print(f"  {t.name:25} | {t.title:30} | {t.department}")

    print("\n" + "=" * 50)
    print("ACTIVE CLIENTS:")
    for c in kb.clients:
        if c.status == "active":
            print(f"  {c.name:30} | {c.type:10}")

    print("\n" + "=" * 50)
    print("ASANA PROJECTS:")
    for p in kb.projects[:20]:
        print(f"  {p.name[:50]:50} | client: {p.client or '?'}")
