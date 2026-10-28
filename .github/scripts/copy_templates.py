#!/usr/bin/env python3
"""Render the release workflow templates for one repository.

GitHub's "New workflow" picker only fills `$default-branch`; everything else
in workflow-templates/ is this organisation's example value (`VERSION`,
`plain`, the job's own repository). This script copies the release templates
with a repository's real values filled in, so a consumer's workflows start as
an exact copy of the reference callers:

    copy_templates.py --repo mega-reth --default-branch develop \\
        --version-file Cargo.toml --version-pattern toml \\
        --bump-command "cargo update --workspace" \\
        --dependency-repositories rust-rocksdb,pstd,rocksdb \\
        --out /tmp/mega-reth-workflows

Each substitution is anchored on exact template text and must match at least
once, so a template edit that drops an anchor fails here instead of shipping
an unfilled copy. Values are written as YAML scalars, quoted when a plain
scalar would change them (`make bump # regenerate` would otherwise lose its
comment-like tail). The rendered files are then checked: no placeholder left,
every `with:` key given to a megaeth-labs/.github action is an input of that
action (read from this checkout's action.yml) with every required input
present, and every substituted value reads back exactly as given.

`--out` must not exist: the files are written to a fresh directory, never on
top of an earlier render. Without `--out` a new temporary directory is used.
Copy the files into `.github/workflows/` of the target repository from there.

stdlib only, except PyYAML (present on GitHub-hosted runners). No network.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "workflow-templates"
ACTIONS = ROOT / ".github" / "actions"
RELEASE_TEMPLATES = ("release-candidate.yml", "release-settle.yml", "app-token-lint.yml")
SHARED_ACTION = re.compile(r"megaeth-labs/\.github/\.github/actions/(?P<name>[a-z0-9-]+)@(?P<ref>\S+)")
TOKEN_ACTION = "actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1 # v3"
# Template text that a render must replace; any left over is an unfilled placeholder.
PLACEHOLDERS = ("$default-branch", "${{ github.event.repository.name }}")
BUMP_EXAMPLE = re.compile(r"^ *# Anything else that must move with the version.*?\n(?: *#.*\n)*", re.M)
CANDIDATE_STEP = "      - uses: megaeth-labs/.github/.github/actions/release-candidate@main\n        with:\n          stage: propose\n"


ACTIONS_REF = re.compile(r"[A-Za-z0-9._/-]+")


class RenderError(Exception):
    pass


def scalar(value: str, flow: bool = False) -> str:
    """`value` as a YAML scalar after `key: ` (or inside `[...]` with `flow`):
    plain when it reads back unchanged there, double-quoted otherwise."""
    try:
        plain = (yaml.safe_load(f"k: [{value}]") == {"k": [value]} if flow
                 else yaml.safe_load(f"k: {value}") == {"k": value})
    except yaml.YAMLError:
        plain = False
    return value if plain else json.dumps(value)


def expected_inputs(args: argparse.Namespace) -> dict[str, str]:
    """Inputs of the shared actions that the render fills, as they must read back."""
    values = {"version_file": args.version_file, "version_pattern": args.version_pattern,
              "changelog_file": args.changelog_file}
    if args.bump_command:
        values["bump_command"] = args.bump_command
    return values


def replace(text: str, old: str, new: str, name: str, what: str) -> str:
    if old not in text:
        raise RenderError(f"{name}: template no longer contains {old!r} ({what})")
    return text.replace(old, new)


def pin(text: str, ref: str) -> str:
    return SHARED_ACTION.sub(lambda m: m[0].replace(f"@{m['ref']}", f"@{ref}"), text)


def bump_block(bump_command: str, dependency_token: str) -> str:
    indent = " " * 10
    return f"{indent}bump_command: {scalar(bump_command)}\n{indent}dependency_token: {dependency_token}\n"


def dependency_step(repositories: str) -> str:
    return (
        "      # bump_command reads private dependencies with its own read-only token.\n"
        f"      - uses: {TOKEN_ACTION}\n"
        "        id: dependency-token\n"
        "        with:\n"
        "          client-id: ${{ vars.MEGA_GUTENBERG_CLIENT_ID }}\n"
        "          private-key: ${{ secrets.MEGA_GUTENBERG_PK }}\n"
        "          owner: megaeth-labs\n"
        f"          repositories: {scalar(repositories)}\n"
        "          permission-contents: read\n\n"
    )


def render(name: str, text: str, args: argparse.Namespace) -> str:
    if name != "release-settle.yml":  # settle runs on release-v* pushes only
        text = replace(text, "$default-branch", scalar(args.default_branch, flow=True), name, "default branch")
    if name == "app-token-lint.yml":
        return pin(text, args.actions_ref)
    text = replace(text, "repositories: ${{ github.event.repository.name }}",
                   f"repositories: {scalar(args.repo)}", name, "release token repository")
    text = replace(text, "version_file: VERSION", f"version_file: {scalar(args.version_file)}", name,
                   "version file")
    text = replace(text, "version_pattern: plain", f"version_pattern: {scalar(args.version_pattern)}", name,
                   "version pattern")
    text = replace(text, "changelog_file: CHANGELOG.md", f"changelog_file: {scalar(args.changelog_file)}", name,
                   "changelog file")
    if name == "release-candidate.yml":
        match = BUMP_EXAMPLE.search(text)
        if match is None:
            raise RenderError(f"{name}: template no longer contains the bump_command example")
        if args.bump_command:
            token = "${{ github.token }}"
            if args.dependency_repositories:
                token = "${{ steps.dependency-token.outputs.token }}"
                text = replace(text, CANDIDATE_STEP, dependency_step(args.dependency_repositories) + CANDIDATE_STEP,
                               name, "propose step")
                match = BUMP_EXAMPLE.search(text)
            text = text[:match.start()] + bump_block(args.bump_command, token) + text[match.end():]
    return pin(text, args.actions_ref)


def action_inputs(name: str) -> dict:
    path = ACTIONS / name / "action.yml"
    if not path.is_file():
        raise RenderError(f"no action {name} in this checkout ({path})")
    return yaml.safe_load(path.read_text()).get("inputs") or {}


def check(name: str, text: str, expected: dict[str, str] | None = None) -> list[str]:
    """Problems in one rendered workflow: placeholders left, unknown or missing
    action inputs, and (given `expected`) a filled input that reads back differently."""
    problems = [f"{name}: unfilled placeholder {p!r}" for p in PLACEHOLDERS if p in text]
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as error:
        return problems + [f"{name}: not valid YAML: {error}"]
    for job_id, job in (doc.get("jobs") or {}).items():
        for index, step in enumerate(job.get("steps") or []):
            match = SHARED_ACTION.fullmatch(str(step.get("uses", "")))
            if not match:
                continue
            inputs = action_inputs(match["name"])
            given = step.get("with") or {}
            where = f"{name}: {job_id}/{step.get('id') or index} ({match['name']})"
            problems += [f"{where}: {key!r} is not an input" for key in given if key not in inputs]
            problems += [f"{where}: required input {key!r} missing" for key, spec in inputs.items()
                         if (spec or {}).get("required") and key not in given]
            problems += [f"{where}: {key} reads back as {given[key]!r}, not {value!r}"
                         for key, value in (expected or {}).items() if key in given and given[key] != value]
    return problems


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo", required=True, help="repository name, e.g. mega-reth")
    parser.add_argument("--default-branch", required=True, help="e.g. main or develop")
    parser.add_argument("--version-file", required=True, help="e.g. VERSION or Cargo.toml")
    parser.add_argument("--version-pattern", required=True, help="e.g. plain, toml, json")
    parser.add_argument("--changelog-file", default="CHANGELOG.md")
    parser.add_argument("--bump-command", default="", help="e.g. 'cargo update --workspace'")
    parser.add_argument("--dependency-repositories", default="",
                        help="comma-separated private repositories bump_command reads, e.g. rust-rocksdb,pstd")
    parser.add_argument("--actions-ref", default="main", help="ref the shared actions are pinned to")
    parser.add_argument("--out", type=Path, help="directory to create (must not exist)")
    args = parser.parse_args(argv)
    for field in ("repo", "default_branch", "version_file", "version_pattern", "changelog_file", "actions_ref"):
        if not getattr(args, field).strip():
            parser.error(f"--{field.replace('_', '-')} must not be blank")
    if not ACTIONS_REF.fullmatch(args.actions_ref):
        parser.error("--actions-ref must be a branch, tag or SHA (letters, digits, . _ / -)")
    if args.dependency_repositories and not args.bump_command:
        parser.error("--dependency-repositories is only used by --bump-command")
    if args.repo in {r.strip() for r in args.dependency_repositories.split(",")}:
        parser.error("--dependency-repositories must not name the repository itself")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.out is not None and args.out.exists():
        print(f"error: {args.out} already exists; render into a fresh directory", file=sys.stderr)
        return 1
    try:
        rendered = {name: render(name, (TEMPLATES / name).read_text(), args) for name in RELEASE_TEMPLATES}
        problems = [p for name, text in rendered.items() for p in check(name, text, expected_inputs(args))]
    except RenderError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    if problems:
        for problem in problems:
            print(f"error: {problem}", file=sys.stderr)
        return 1
    if args.out is None:
        out = Path(tempfile.mkdtemp(prefix=f"{args.repo}-workflows-"))
    else:
        out = args.out
        out.mkdir(parents=True)
    for name, text in rendered.items():
        (out / name).write_text(text)
        print(out / name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
