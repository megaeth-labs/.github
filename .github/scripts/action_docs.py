#!/usr/bin/env python3
"""Render the generated parts of the action documentation from action.yml.

Every action directory under .github/actions/ carries a README.md whose
hand-written prose surrounds blocks delimited by

    <!-- generated: <section> -->
    ...
    <!-- /generated -->

This script rewrites the content of those blocks from the action's
action.yml — its description, inputs, outputs, the steps it runs and the
errors its shell steps report — and the catalogue block in
.github/actions/README.md from every action's name and description. The prose
outside the blocks is never touched. `--check` exits 1 if any file would
change, which is how actions-test.yml keeps the docs honest.

stdlib only, except PyYAML (present on GitHub-hosted runners).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
ACTIONS = ROOT / ".github" / "actions"
FAMILIES = {  # directory prefix -> (family name, guide)
    "release-": ("Release pipeline", "RELEASE.md"),
    "claude-": ("Claude CI", "CLAUDE-CI.md"),
}
BLOCK = re.compile(r"(<!-- generated: (?P<name>[a-z-]+) -->\n)(?P<body>.*?)(<!-- /generated -->)", re.S)


def family_of(directory: str) -> tuple[str, str | None]:
    for prefix, (name, guide) in FAMILIES.items():
        if directory.startswith(prefix):
            return name, guide
    return "Standalone", None


def one_line(text: object) -> str:
    return " ".join(str(text or "").split())


def cell(text: str) -> str:
    return text.replace("|", "\\|")


def load_action(directory: Path) -> dict:
    return yaml.safe_load((directory / "action.yml").read_text())


def render_inputs(action: dict) -> str:
    inputs = action.get("inputs") or {}
    if not inputs:
        return "This action takes no inputs.\n"
    rows = ["| Input | Required | Default | Description |", "|---|---|---|---|"]
    for name, spec in inputs.items():
        spec = spec or {}
        required = "yes" if spec.get("required") else "no"
        default = spec.get("default", "")
        default = "" if default in (None, "") else f"`{default}`"
        rows.append(f"| `{name}` | {required} | {cell(default)} | {cell(one_line(spec.get('description')))} |")
    return "\n".join(rows) + "\n"


def render_outputs(action: dict) -> str:
    outputs = action.get("outputs") or {}
    if not outputs:
        return "This action sets no outputs.\n"
    rows = ["| Output | Description |", "|---|---|"]
    for name, spec in outputs.items():
        rows.append(f"| `{name}` | {cell(one_line((spec or {}).get('description')))} |")
    return "\n".join(rows) + "\n"


def render_steps(action: dict) -> str:
    steps = ((action.get("runs") or {}).get("steps")) or []
    if not steps:
        return "This action runs no steps of its own.\n"
    lines = []
    for step in steps:
        label = step.get("name")
        if not label and "uses" in step:
            label = f"`{step['uses'].split('@')[0]}`"
        if not label:
            label = "(unnamed run step)"
        if "uses" in step and step.get("name"):
            label += f" — `{step['uses'].split('@')[0]}`"
        cond = one_line(step.get("if"))
        if cond:
            label += f" *(only if `{cond}`)*"
        lines.append(f"1. {label}")
    return "\n".join(lines) + "\n"


def render_errors(action: dict) -> str:
    steps = ((action.get("runs") or {}).get("steps")) or []
    seen: list[str] = []
    for step in steps:
        for match in re.finditer(r'::error::(.*?)(?:"|\'|$)', str(step.get("run", "")), re.M):
            message = match.group(1).strip()
            if message and message not in seen:
                seen.append(message)
    if not seen:
        return "Its shell steps report no errors of their own; failures come from the actions and tools it calls.\n"
    return "\n".join(f"- `{cell(m)}`" for m in seen) + "\n"


def render_description(action: dict) -> str:
    return one_line(action.get("description")) + "\n"


RENDERERS = {
    "description": render_description,
    "inputs": render_inputs,
    "outputs": render_outputs,
    "steps": render_steps,
    "errors": render_errors,
}


def fill(text: str, renderers: dict, context) -> str:
    def replace(match: re.Match) -> str:
        name = match.group("name")
        if name not in renderers:
            raise SystemExit(f"unknown generated block '{name}'")
        return f"{match.group(1)}{renderers[name](context)}{match.group(4)}"

    return BLOCK.sub(replace, text)


def skeleton(directory: Path, action: dict) -> str:
    family, guide = family_of(directory.name)
    guide_line = f"Family: [{family}](../{guide})." if guide else "Standalone action; no family guide."
    return f"""# {action.get('name', directory.name)}

`uses: megaeth-labs/.github/.github/actions/{directory.name}@main`

<!-- generated: description -->
<!-- /generated -->

{guide_line}

## Inputs

<!-- generated: inputs -->
<!-- /generated -->

## Outputs

<!-- generated: outputs -->
<!-- /generated -->

## What it runs

<!-- generated: steps -->
<!-- /generated -->

## Errors it reports

<!-- generated: errors -->
<!-- /generated -->

## Example

(hand-written)

## Notes

(hand-written)
"""


def render_catalogue(_: object) -> str:
    rows = ["| Action | Family | Does |", "|---|---|---|"]
    for directory in sorted(p for p in ACTIONS.iterdir() if (p / "action.yml").exists()):
        action = load_action(directory)
        family, guide = family_of(directory.name)
        family_cell = f"[{family}]({guide})" if guide else family
        rows.append(f"| [`{directory.name}`]({directory.name}/README.md) | {family_cell} | {cell(one_line(action.get('description')))} |")
    return "\n".join(rows) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="exit 1 if any file would change")
    args = parser.parse_args()
    changed: list[Path] = []
    for directory in sorted(p for p in ACTIONS.iterdir() if (p / "action.yml").exists()):
        readme = directory / "README.md"
        action = load_action(directory)
        before = readme.read_text() if readme.exists() else skeleton(directory, action)
        after = fill(before, RENDERERS, action)
        if after != (readme.read_text() if readme.exists() else None):
            changed.append(readme)
            if not args.check:
                readme.write_text(after)
    catalogue = ACTIONS / "README.md"
    before = catalogue.read_text()
    after = fill(before, {"catalogue": render_catalogue}, None)
    if after != before:
        changed.append(catalogue)
        if not args.check:
            catalogue.write_text(after)
    if args.check and changed:
        print("generated documentation is stale; run .github/scripts/action_docs.py:", file=sys.stderr)
        for path in changed:
            print(f"  {path.relative_to(ROOT)}", file=sys.stderr)
        return 1
    for path in changed:
        print(f"updated {path.relative_to(ROOT)}")
    if not changed:
        print("documentation up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
