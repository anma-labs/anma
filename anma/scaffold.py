"""`anma init`: create a minimal, runnable starting point with a worked example.

The example is language-specific (``--language``): the same accounts/billing graph
where ``billing`` may import ``accounts`` but not vice-versa, written idiomatically
per language. The contract *graph* is identical across languages — only the source
files and the root config's ``language``/metadata differ.
"""
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


GO_ROOT_YAML = """# ANMA project config (Go). Modules are discovered from per-directory anma.yaml.
schema_version: 1
language: go
source_roots:        # for Go this is the go.mod directory
  - .
"""

GO_EXAMPLE = {
    "go.mod": "module example.com/shop\n\ngo 1.22\n",
    "domains/accounts/anma.yaml": """name: accounts
summary: User accounts and authentication.
public:
  - accounts.GetUser
  - accounts.Authenticate
depends_on: []
invariants:
  - Password hashes never leave this module.
""",
    "domains/accounts/service.go": """package accounts

// GetUser returns a user's basic info.
func GetUser(userID string) map[string]string {
\treturn map[string]string{"id": userID, "name": "Ada"}
}

// Authenticate reports whether a token is valid.
func Authenticate(token string) bool {
\treturn token != ""
}
""",
    "domains/billing/anma.yaml": """name: billing
summary: Invoices and payment processing.
public:
  - billing.CreateInvoice
depends_on:
  - accounts            # billing may use accounts' public interface
invariants:
  - Never store raw card numbers.
""",
    "domains/billing/service.go": """package billing

import "example.com/shop/domains/accounts" // billing may import accounts (allowed)

// CreateInvoice creates an invoice for a user.
func CreateInvoice(userID string, amount int) map[string]any {
\tuser := accounts.GetUser(userID)
\treturn map[string]any{"user": user["id"], "amount": amount}
}
""",
}

TS_ROOT_YAML = """# ANMA project config (TypeScript). Modules are discovered from per-directory anma.yaml.
schema_version: 1
language: typescript
source_roots:
  - src
"""

TS_EXAMPLE = {
    "tsconfig.json": """{
  "compilerOptions": {
    "baseUrl": "src",
    "strict": true
  }
}
""",
    "src/domains/accounts/anma.yaml": """name: accounts
summary: User accounts and authentication.
public:
  - accounts/service.getUser
  - accounts/service.authenticate
depends_on: []
invariants:
  - Password hashes never leave this module.
""",
    "src/domains/accounts/service.ts": """// accounts public surface.
export function getUser(userId: string): { id: string; name: string } {
  return { id: userId, name: "Ada" };
}

export function authenticate(token: string): boolean {
  return token !== "";
}
""",
    "src/domains/billing/anma.yaml": """name: billing
summary: Invoices and payment processing.
public:
  - billing/service.createInvoice
depends_on:
  - accounts            # billing may use accounts' public interface
invariants:
  - Never store raw card numbers.
""",
    "src/domains/billing/service.ts": """// billing public surface. May import accounts (allowed).
import { getUser } from "../accounts/service";

export function createInvoice(userId: string, amount: number) {
  const user = getUser(userId);
  return { user: user.id, amount };
}
""",
}

DART_ROOT_YAML = """# ANMA project config (Dart). Modules are discovered from per-directory anma.yaml.
schema_version: 1
language: dart
source_roots:        # for Dart this is the package's `lib/` directory
  - lib
"""

DART_EXAMPLE = {
    "pubspec.yaml": """name: example_shop
description: ANMA Dart example.
environment:
  sdk: ">=3.0.0 <4.0.0"
""",
    "lib/domains/accounts/anma.yaml": """name: accounts
summary: User accounts and authentication.
public:
  - accounts/service.getUser
  - accounts/service.authenticate
depends_on: []
invariants:
  - Password hashes never leave this module.
""",
    "lib/domains/accounts/service.dart": """// accounts public surface.
class User {
  final String id;
  final String name;
  const User(this.id, this.name);
}

User getUser(String userId) => User(userId, 'Ada');

bool authenticate(String token) => token.isNotEmpty;
""",
    "lib/domains/billing/anma.yaml": """name: billing
summary: Invoices and payment processing.
public:
  - billing/service.createInvoice
depends_on:
  - accounts            # billing may use accounts' public interface
invariants:
  - Never store raw card numbers.
""",
    "lib/domains/billing/service.dart": """// billing public surface. May import accounts (allowed).
import 'package:example_shop/domains/accounts/service.dart';

Map<String, Object> createInvoice(String userId, int amount) {
  final user = getUser(userId);
  return {'user': user.id, 'amount': amount};
}
""",
}

# language -> (root anma.yaml, {relative path: content}). New languages append here.
SCAFFOLDS: dict[str, tuple[str, dict[str, str]]] = {
    "python": (ROOT_YAML, EXAMPLE),
    "go": (GO_ROOT_YAML, GO_EXAMPLE),
    "typescript": (TS_ROOT_YAML, TS_EXAMPLE),
    "dart": (DART_ROOT_YAML, DART_EXAMPLE),
}


def init_project(root: Path, language: str = "python") -> list[str]:
    try:
        root_yaml, example = SCAFFOLDS[language]
    except KeyError:
        supported = ", ".join(sorted(SCAFFOLDS))
        raise ValueError(
            f"no `anma init` scaffold for language '{language}'. "
            f"Available: {supported}."
        ) from None

    created: list[str] = []
    root.mkdir(parents=True, exist_ok=True)

    rc = root / "anma.yaml"
    if not rc.exists():
        rc.write_text(root_yaml)
        created.append(str(rc))

    for rel, content in example.items():
        path = root / rel
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        created.append(str(path))
    return created
