# Contract Guide

How to write effective ANMA contracts.

## Anatomy of a Contract

```yaml
module: my-module          # kebab-case name
version: 1                 # integer, increment on breaking changes
status: draft              # draft | stable | frozen | breaking-change | deprecated
type: regular              # regular | infrastructure

purpose: "One sentence describing what this module does"

provides:
  - id: interface_name     # snake_case
    input: { ... }         # typed fields
    output: { ... }        # typed fields
    errors: [ERROR_ONE, ERROR_TWO]  # SCREAMING_SNAKE_CASE
    invariants:
      - "behavioral guarantee callers can depend on"

consumes:
  - module: other-module
    interface: some_interface
    required: true
    contract_version: 1

contract_rules:
  adding_interface: allowed
  modifying_interface: notify
  removing_interface: breaking
```

## Types

ANMA uses a small, explicit type system:

| Type | Meaning |
|------|---------|
| `string` | UTF-8 text |
| `string_nullable` | string or null |
| `integer` | whole number |
| `boolean` | true/false |
| `uuid` | UUID v4 string |
| `timestamp` | ISO 8601 UTC datetime |
| `enum(a\|b\|c)` | one of the listed values |
| `object` | arbitrary JSON object |
| `object_nullable` | object or null |
| `"Type[]"` | array of Type (quoted for YAML) |
| `"Type[]_nullable"` | array of Type or null |

No optional fields. If a field can be absent, use an explicit `_nullable` type.

## Writing Good Invariants

Invariants are behavioral guarantees that callers depend on. They belong in the contract. Implementation details do not.

### Good invariants

```yaml
invariants:
  - "auto-sends verification email; unverified accounts have limited access"
  - "INVALID_CREDENTIALS returned for both wrong password and non-existent email"
  - "succeeds silently for non-existent emails to prevent enumeration"
  - "account locked after 5 consecutive failures"
```

These describe **what callers can depend on**. If you changed these behaviors, callers would break.

### Bad invariants (these are assumptions)

```yaml
# DON'T put these in CONTRACT.yaml — they go in ASSUMPTIONS.yaml
invariants:
  - "uses bcrypt with cost factor 12"          # implementation detail
  - "stored in PostgreSQL"                      # storage choice
  - "JWT tokens expire after 1 hour"            # internal config
  - "rate limited to 10 req/s via Redis"        # infrastructure detail
```

**Rule:** If changing this behavior would break *callers*, it's an invariant. If changing it would only affect *this module's internals*, it's an assumption.

## The CONTRACT / ASSUMPTIONS Boundary

CONVENTIONS.yaml defines this under `contract_design.invariants_vs_assumptions`:

> CONTRACT invariants = BEHAVIORAL (what it guarantees).
> ASSUMPTIONS = IMPLEMENTATION (how it's built).

The practical test: **can an agent implement and verify this from the interface alone?** If yes, it's a CONTRACT invariant. If it depends on infrastructure, deployment config, or runtime environment, it's an ASSUMPTION.

### CONTRACT invariants (behavioral, testable through the interface)

```yaml
# An agent can write a test for each of these using only the interface
invariants:
  - "idempotent — safe to retry"
  - "returns max 50 results per page"
  - "succeeds silently for non-existent emails to prevent enumeration"
  - "completion is irreversible — completing a completed item returns ALREADY_COMPLETED"
  - "null fields in update input are not modified"
```

These are observable through inputs and outputs. Call the interface twice with the same input — does it behave the same? Send a page request — does it cap at 50? An agent can verify all of this without knowing anything about the infrastructure.

### ASSUMPTIONS (implementation, depends on infrastructure)

```yaml
# An agent CANNOT verify these from the interface — they depend on how it's deployed
assumptions:
  - id: retry_policy
    category: infrastructure
    content: "Retry 3 times with exponential backoff"
  - id: cache_ttl
    category: infrastructure
    content: "Responses cached for 5 minutes"
  - id: rate_limit
    category: infrastructure
    content: "Rate limited to 100 requests per minute"
  - id: latency_slo
    category: infrastructure
    content: "Target response under 500ms (SLO)"
```

These depend on middleware, caching layers, deployment config, or monitoring. They're real constraints — but they're not part of the contract because swapping Redis for Memcached or changing the retry count doesn't break callers.

### Gray areas

Some things look like both. Use the interface test:

| Statement | CONTRACT or ASSUMPTION? | Why |
|-----------|------------------------|-----|
| "passwords must be at least 8 characters" | CONTRACT | Agent can test: submit 7-char password, expect WEAK_PASSWORD |
| "passwords hashed with bcrypt cost 12" | ASSUMPTION | Agent can't observe hashing algorithm from the interface |
| "returns results ordered by created_at descending" | CONTRACT | Agent can test: create items, verify order |
| "uses a B-tree index on created_at" | ASSUMPTION | Agent can't observe index strategy from the interface |
| "account locked after 5 failed logins" | CONTRACT | Agent can test: fail 5 times, expect ACCOUNT_LOCKED |
| "lockout tracked via Redis counter with 15min TTL" | ASSUMPTION | Agent can't observe the storage mechanism |

When in doubt, ask: "If I replaced the entire implementation with a different stack, would this statement still need to be true for callers to work?" If yes, CONTRACT. If no, ASSUMPTION.

## Writing Good Errors

### Naming conventions

```yaml
errors: [
  USER_NOT_FOUND,          # {ENTITY}_NOT_FOUND
  REGISTRATION_FAILED,     # {ACTION}_FAILED
  INVALID_EMAIL,           # INVALID_{FIELD}
  RATE_LIMITED,            # cross-cutting (shared name)
  UNAUTHORIZED,            # cross-cutting
]
```

### Be specific

```yaml
# Good — caller knows exactly what went wrong
errors: [EMAIL_TAKEN, WEAK_PASSWORD, INVALID_EMAIL]

# Bad — caller can't handle different cases
errors: [REGISTRATION_ERROR]
```

### Use cross-cutting names consistently

These error codes mean the same thing everywhere:
- `RATE_LIMITED` — too many requests
- `UNAUTHORIZED` — missing or invalid credentials
- `FORBIDDEN` — valid credentials but insufficient permissions

## Dependencies: Direct vs. BUS

### Direct (`consumes`)

Use when the call is:
- **Synchronous** — caller needs the response before continuing
- **Frequent** — called on most requests
- **Stable** — interface rarely changes

```yaml
consumes:
  - module: user-auth
    interface: verify_token
    required: true
    contract_version: 1
```

### BUS events (via invariants)

Use when the communication is:
- **Async** — fire-and-forget
- **One-to-many** — multiple modules need to react
- **Cross-cutting** — cleanup, notifications, logging

Declare BUS events in the publishing interface's invariants:

```yaml
provides:
  - id: delete_account
    invariants:
      - "publishes account_deleted event via BUS"
```

### Examples

| Scenario | Type | Why |
|----------|------|-----|
| Verify JWT on every request | Direct | synchronous, frequent |
| Send notification on todo complete | BUS invariant | async, fire-and-forget |
| Account deletion cleanup | BUS invariant | one-to-many fan-out |
| Get user profile for display | Direct | synchronous, frequent |
| Log audit events | BUS invariant | async, cross-cutting |

## Contract Lifecycle

### draft

Module is being designed. Changes are expected and don't require notification.

```yaml
contract_rules:
  adding_interface: allowed
  modifying_interface: allowed
  removing_interface: allowed
```

### stable

Consumers depend on this contract. Changes require notification.

```yaml
contract_rules:
  adding_interface: allowed
  modifying_interface: notify      # tell consumers before changing
  removing_interface: breaking     # triggers breaking-change status
```

### frozen

Critical infrastructure. Can only be extended, never modified.

```yaml
contract_rules:
  adding_interface: allowed
  modifying_interface: forbidden
  removing_interface: forbidden
```

## Granularity

- **Minimum 3 interfaces** — if you have fewer, merge this into another module
- **Maximum 7 interfaces** — if you have more, consider splitting
- **Split at 12** — mandatory split, the module is too large

These constraints keep contracts small enough to fit in AI context windows while being large enough to be useful.

## Common Patterns

### CRUD module

```yaml
provides:
  - id: create_thing
  - id: get_thing
  - id: update_thing
  - id: delete_thing
  - id: list_things
```

### Auth-protected module

```yaml
consumes:
  - module: user-auth
    interface: verify_token
    required: true
    contract_version: 1

provides:
  - id: do_something
    input: { user_id: uuid, ... }   # user_id from verified token
    errors: [UNAUTHORIZED, ...]
```

### Event-publishing module

```yaml
provides:
  - id: complete_action
    invariants:
      - "publishes BUS event for downstream processing"
```

## Checklist

Before marking a contract as `stable`:

- [ ] Every interface has at least one invariant
- [ ] All error codes follow naming conventions
- [ ] No implementation details in invariants (move to ASSUMPTIONS.yaml)
- [ ] Input/output types are explicit (no `any` or untyped fields)
- [ ] Consumed interfaces reference real modules
- [ ] `python3 tools/lint_contracts.py --strict` passes with 0 warnings
