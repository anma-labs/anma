#!/usr/bin/env python3
"""Compare architectural quality between a control and ANMA project.

Usage:
    python3 compare_quality.py /path/to/control /path/to/anma
"""

import sys
import re
from pathlib import Path


def analyze(root, label):
    root = Path(root)
    metrics = {}

    # 1. Code files
    py_files = [f for f in root.rglob('*.py')
                if '.git' not in str(f) and 'tools/' not in str(f)
                and 'checks/' not in str(f) and 'benchmark/' not in str(f)]
    metrics['python_files'] = len(py_files)

    total_lines = 0
    imports_across_modules = 0
    direct_function_calls = 0
    for f in py_files:
        content = f.read_text()
        total_lines += len(content.split('\n'))
        # Count cross-module imports (rough: from app. or from src. or from services.)
        imports_across_modules += len(re.findall(
            r'^(?:from|import)\s+(?:app|src|services|modules)\.',
            content, re.MULTILINE))
    metrics['total_code_lines'] = total_lines
    metrics['cross_module_imports'] = imports_across_modules

    # 2. Architectural artifacts
    contracts = list(root.rglob('CONTRACT.yaml'))
    contracts = [c for c in contracts if 'tools' not in str(c)]
    metrics['contracts'] = len(contracts)
    metrics['gateways'] = len(list(root.rglob('GATEWAY.yaml')))
    metrics['manifest'] = 1 if (root / 'MANIFEST.yaml').exists() else 0
    metrics['graph'] = 1 if (root / 'GRAPH.yaml').exists() else 0

    # 3. Declared interfaces and dependencies
    total_interfaces = 0
    total_declared_deps = 0
    total_declared_errors = 0
    total_invariants = 0
    for c in contracts:
        content = c.read_text()
        total_interfaces += len(re.findall(r'^\s+- id:', content, re.MULTILINE))
        total_declared_deps += len(re.findall(r'^\s+- module:', content, re.MULTILINE))
        total_declared_errors += len(re.findall(
            r'^\s+errors:\s*\[([^\]]+)\]', content, re.MULTILINE))
        total_invariants += len(re.findall(r'^\s+- ".*"', content, re.MULTILINE))
    metrics['declared_interfaces'] = total_interfaces
    metrics['declared_dependencies'] = total_declared_deps
    metrics['declared_errors'] = total_declared_errors
    metrics['declared_invariants'] = total_invariants

    # 4. Event-driven communication
    bus_publishes = 0
    bus_subscribes = 0
    for f in py_files:
        content = f.read_text()
        bus_publishes += len(re.findall(
            r'publish\(|emit\(|\.fire\(|bus\.send\(', content))
        bus_subscribes += len(re.findall(
            r'subscribe\(|\.on\(|bus\.register\(|@.*event', content))
    metrics['bus_publishes'] = bus_publishes
    metrics['bus_subscribes'] = bus_subscribes

    # 5. Test files
    test_files = [f for f in py_files if 'test' in f.name.lower()]
    test_count = 0
    for f in test_files:
        content = f.read_text()
        test_count += len(re.findall(r'def test_', content))
    metrics['test_files'] = len(test_files)
    metrics['test_count'] = test_count

    # 6. Architectural doc lines (contracts + gateway + manifest + graph)
    arch_lines = 0
    for pattern in ['CONTRACT.yaml', 'GATEWAY.yaml', 'MANIFEST.yaml',
                    'GRAPH.yaml', 'STATE.yaml', 'MEMORY.yaml',
                    'ASSUMPTIONS.yaml', 'CHANGELOG.yaml', 'TESTS.yaml']:
        for f in root.rglob(pattern):
            if 'tools' not in str(f):
                arch_lines += len(f.read_text().split('\n'))
    metrics['arch_doc_lines'] = arch_lines

    # 7. Error handling (try/except blocks)
    error_handlers = 0
    http_error_responses = 0
    for f in py_files:
        content = f.read_text()
        error_handlers += len(re.findall(r'except\s+\w+', content))
        http_error_responses += len(re.findall(
            r'HTTPException|status_code\s*=\s*4\d\d|raise.*Error', content))
    metrics['error_handlers'] = error_handlers
    metrics['http_error_responses'] = http_error_responses

    return metrics


def main():
    if len(sys.argv) != 3:
        print(f"Usage: python3 {sys.argv[0]} /path/to/control /path/to/anma")
        sys.exit(1)

    control = analyze(sys.argv[1], "Control")
    anma = analyze(sys.argv[2], "ANMA")

    print("=" * 70)
    print("ARCHITECTURAL QUALITY COMPARISON")
    print("=" * 70)

    rows = [
        ("", "Control", "ANMA"),
        ("─" * 40, "─" * 10, "─" * 10),
        ("CODE", "", ""),
        ("  Python files", control['python_files'], anma['python_files']),
        ("  Lines of code", control['total_code_lines'], anma['total_code_lines']),
        ("  Cross-module imports", control['cross_module_imports'], anma['cross_module_imports']),
        ("", "", ""),
        ("ARCHITECTURAL ARTIFACTS", "", ""),
        ("  Contracts", control['contracts'], anma['contracts']),
        ("  Gateway files", control['gateways'], anma['gateways']),
        ("  Manifest", control['manifest'], anma['manifest']),
        ("  Dependency graph", control['graph'], anma['graph']),
        ("  Architecture doc lines", control['arch_doc_lines'], anma['arch_doc_lines']),
        ("", "", ""),
        ("DECLARED SPECIFICATIONS", "", ""),
        ("  Interfaces declared", control['declared_interfaces'], anma['declared_interfaces']),
        ("  Dependencies declared", control['declared_dependencies'], anma['declared_dependencies']),
        ("  Error types declared", control['declared_errors'], anma['declared_errors']),
        ("  Invariants declared", control['declared_invariants'], anma['declared_invariants']),
        ("", "", ""),
        ("EVENT-DRIVEN DECOUPLING", "", ""),
        ("  BUS publishes", control['bus_publishes'], anma['bus_publishes']),
        ("  BUS subscribes", control['bus_subscribes'], anma['bus_subscribes']),
        ("", "", ""),
        ("TESTING", "", ""),
        ("  Test files", control['test_files'], anma['test_files']),
        ("  Test count", control['test_count'], anma['test_count']),
        ("", "", ""),
        ("ERROR HANDLING", "", ""),
        ("  Try/except handlers", control['error_handlers'], anma['error_handlers']),
        ("  HTTP error responses", control['http_error_responses'], anma['http_error_responses']),
    ]

    for row in rows:
        if isinstance(row[1], str):
            print(f"  {row[0]:<40} {row[1]:>10} {row[2]:>10}")
        else:
            print(f"  {row[0]:<40} {row[1]:>10} {row[2]:>10}")

    # Summary
    arch_total_ctrl = (control['contracts'] + control['gateways'] +
                       control['manifest'] + control['graph'])
    arch_total_anma = (anma['contracts'] + anma['gateways'] +
                       anma['manifest'] + anma['graph'])
    spec_total_ctrl = (control['declared_interfaces'] +
                       control['declared_dependencies'] +
                       control['declared_invariants'])
    spec_total_anma = (anma['declared_interfaces'] +
                       anma['declared_dependencies'] +
                       anma['declared_invariants'])
    bus_total_ctrl = control['bus_publishes'] + control['bus_subscribes']
    bus_total_anma = anma['bus_publishes'] + anma['bus_subscribes']

    print(f"\n{'=' * 70}")
    print(f"  Architecture artifacts:  Control {arch_total_ctrl:>3}  vs  ANMA {arch_total_anma:>3}")
    print(f"  Declared specifications: Control {spec_total_ctrl:>3}  vs  ANMA {spec_total_anma:>3}")
    print(f"  Event-driven messages:   Control {bus_total_ctrl:>3}  vs  ANMA {bus_total_anma:>3}")
    print(f"  Test coverage:           Control {control['test_count']:>3}  vs  ANMA {anma['test_count']:>3}")
    print(f"{'=' * 70}")


if __name__ == '__main__':
    main()
