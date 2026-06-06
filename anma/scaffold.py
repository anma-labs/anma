"""`anma init`: create a minimal, runnable starting point with a worked example."""
from __future__ import annotations

from pathlib import Path

ROOT_YAML = """# ANMA project config. Modules are discovered from per-directory anma.yaml files.
schema_version: 1
source_roots:        # one or more; supports monorepos
  - src
python_version: "3.10"
"""

EXAMPLE = {
    "src/domains/accounts/anma.yaml": """name: accounts
summary: User accounts and authentication.
public:
  - accounts.service.get_user
  - accounts.service.authenticate
depends_on: []
invariants:
  - Password hashes never leave this module.
""",
    "src/domains/accounts/__init__.py": "",
    "src/domains/accounts/service.py": '''"""accounts public surface."""

def get_user(user_id: str) -> dict:
    return {"id": user_id}

def authenticate(token: str) -> bool:
    return bool(token)
''',
    "src/domains/billing/anma.yaml": """name: billing
summary: Invoices and payment processing.
public:
  - billing.service.create_invoice
depends_on:
  - accounts            # billing may use accounts' public interface
invariants:
  - Never store raw card numbers.
""",
    "src/domains/billing/__init__.py": "",
    "src/domains/billing/service.py": '''"""billing public surface. May import accounts (allowed)."""
from domains.accounts.service import get_user

def create_invoice(user_id: str, amount: int) -> dict:
    user = get_user(user_id)
    return {"user": user["id"], "amount": amount}
''',
}


def init_project(root: Path) -> list[str]:
    created: list[str] = []
    root.mkdir(parents=True, exist_ok=True)

    rc = root / "anma.yaml"
    if not rc.exists():
        rc.write_text(ROOT_YAML)
        created.append(str(rc))

    for rel, content in EXAMPLE.items():
        path = root / rel
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        created.append(str(path))
    return created
