#!/usr/bin/env python3
"""Lint GitHub App token minting in workflow files.

The org has two GitHub Apps that mint tokens through actions/create-github-app-token:

  Maxwell    CI app (vars.MEGA_MAXWELL_CLIENT_ID / secrets.MEGA_MAXWELL_PK, older
             names CI_APP_ID / MEGA_CI_APP_PK). Its commits and PRs are what
             automation shows as `mega-maxwell[bot]`; it never touches a release.
  Gutenberg  Release app (vars.RELEASE_APP_CLIENT_ID / secrets.RELEASE_APP_PRIVATE_KEY),
             only usable from a job in the `release` environment.

Rules, each reported as `::error file=<path>::<job>/<step>: <rule>: <message>`:

  L1  A Maxwell token may not request `permission-<x>: write` except for
      pull-requests and issues (a permission that is not a literal value, such as
      an expression, cannot be verified and is refused too).
  L2  A Gutenberg token must sit in a job whose `environment` is `release`, or in a
      `publish` job when the token requests exactly `permission-contents: read`
      (private-dependency reads in on-release build jobs).
  L3  In a release workflow, no Maxwell token at all; and a Gutenberg read-only
      dependency token's `repositories:` must not name the repository itself.
  L4  A release workflow may not use `mega-maxwell[bot]` as a git identity or a
      PR author filter.
  L5  `environment: release` may appear only in release-candidate.yml,
      release-settle.yml and on-release.yml.
  L6  A Maxwell or Gutenberg token, and any app token in a release workflow or
      a `release`-environment job, must request at least one `permission-<x>`:
      without one, create-github-app-token returns every permission the
      installation has, contents write included.

A release workflow is one that uses megaeth-labs/.github's release-candidate,
release-settle, release-publish or release-route action, or is on-release.yml.

Input problems (unreadable or malformed YAML, a missing path, a directory without
workflow files) are errors too, so a broken file never lints clean.

stdlib only, except PyYAML (present on GitHub-hosted runners). No network.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Iterator
from pathlib import Path

import yaml

TOKEN_ACTION = "actions/create-github-app-token@"
MAXWELL_MARKERS = ("MEGA_MAXWELL_", "CI_APP_ID", "MEGA_CI_APP_PK")
GUTENBERG_MARKER = "RELEASE_APP_"
MAXWELL_WRITABLE = {"permission-pull-requests", "permission-issues"}
RELEASE_USES = re.compile(r"megaeth-labs/\.github/\.github/actions/release-(candidate|settle|publish|route)")
ON_RELEASE = "on-release"
RELEASE_ENVIRONMENT_FILES = {"release-candidate", "release-settle", ON_RELEASE}
MAXWELL_IDENTITY = "mega-maxwell[bot]"
WORKFLOW_SUFFIXES = (".yml", ".yaml")

Violation = tuple[str, str, str, str]


def escape_data(text: str) -> str:
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def escape_property(text: str) -> str:
    return escape_data(text).replace(":", "%3A").replace(",", "%2C")


def error_line(path: str, violation: Violation) -> str:
    job, step, rule, message = violation
    return f"::error file={escape_property(path)}::{escape_data(f'{job}/{step}: {rule}: {message}')}"


def strings(node: object) -> Iterator[str]:
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for key, value in node.items():
            yield from strings(key)
            yield from strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from strings(value)


def mentions_maxwell_identity(node: object) -> bool:
    return any(MAXWELL_IDENTITY in text.lower() for text in strings(node))


def environment_name(job: dict) -> str | None:
    environment = job.get("environment")
    if isinstance(environment, dict):
        environment = environment.get("name")
    return environment.strip() if isinstance(environment, str) else None


def step_label(step: dict, index: int) -> str:
    for key in ("name", "id"):
        if isinstance(step.get(key), str) and step[key].strip():
            return " ".join(step[key].split())
    return f"#{index}"


def permissions_of(with_: dict) -> dict[str, str]:
    return {str(k): str(v).strip() for k, v in with_.items() if str(k).startswith("permission-")}


def is_read_only_contents(permissions: dict[str, str]) -> bool:
    return {k: v.lower() for k, v in permissions.items()} == {"permission-contents": "read"}


def repository_names(with_: dict) -> set[str]:
    names = re.split(r"[\s,]+", str(with_.get("repositories") or ""))
    return {n.rsplit("/", 1)[-1].lower() for n in names if n}


def is_release_workflow(path: str, doc: dict) -> bool:
    if Path(path).stem == ON_RELEASE:
        return True
    jobs = doc.get("jobs") if isinstance(doc.get("jobs"), dict) else {}
    for job in jobs.values():
        if not isinstance(job, dict):
            continue
        uses = [job.get("uses")] + [s.get("uses") for s in job.get("steps") or [] if isinstance(s, dict)]
        if any(isinstance(u, str) and RELEASE_USES.search(u) for u in uses):
            return True
    return False


def lint_job(job_id: str, job: dict, stem: str, release: bool, repo: str | None) -> list[Violation]:
    found: list[Violation] = []
    environment = environment_name(job)
    if environment == "release" and stem not in RELEASE_ENVIRONMENT_FILES:
        found.append((job_id, "-", "L5", "environment `release` is only for release-candidate.yml, release-settle.yml and on-release.yml"))
    if release and mentions_maxwell_identity({k: v for k, v in job.items() if k != "steps"}):
        found.append((job_id, "-", "L4", f"{MAXWELL_IDENTITY} is not a release identity"))
    steps = job.get("steps") if isinstance(job.get("steps"), list) else []
    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            found.append((job_id, f"#{index}", "parse", "step is not a mapping"))
            continue
        label = step_label(step, index)
        if release and mentions_maxwell_identity(step):
            found.append((job_id, label, "L4", f"{MAXWELL_IDENTITY} is not a release identity"))
        uses = step.get("uses")
        if not (isinstance(uses, str) and uses.startswith(TOKEN_ACTION)):
            continue
        with_ = step.get("with") if isinstance(step.get("with"), dict) else {}
        refs = " ".join(str(with_.get(k, "")) for k in ("client-id", "app-id", "private-key"))
        permissions = permissions_of(with_)
        maxwell = any(m in refs for m in MAXWELL_MARKERS)
        if not permissions and (maxwell or GUTENBERG_MARKER in refs or release or environment == "release"):
            app = "Maxwell" if maxwell else "Gutenberg" if GUTENBERG_MARKER in refs else "app"
            found.append((job_id, label, "L6", f"{app} token requests no permission-* inputs, so it gets every permission of the installation (contents write included); list the permissions it needs"))
        if maxwell:
            for name, value in permissions.items():
                if name not in MAXWELL_WRITABLE and (value.lower() == "write" or "${{" in value):
                    found.append((job_id, label, "L1", f"Maxwell token requests {name}: {value}; Maxwell may only write pull-requests and issues"))
            if release:
                found.append((job_id, label, "L3", "no Maxwell token in a release workflow; mint a Gutenberg token instead"))
        if GUTENBERG_MARKER in refs:
            if not (environment == "release" or (environment == "publish" and is_read_only_contents(permissions))):
                found.append((job_id, label, "L2", f"Gutenberg token needs `environment: release` (or `publish` with only permission-contents: read), job has {environment or 'none'}"))
            if release and repo and is_read_only_contents(permissions) and repo.lower() in repository_names(with_):
                found.append((job_id, label, "L3", f"read-only dependency token names the repository itself ({repo})"))
    return found


def lint_source(path: str, text: str, repo: str | None) -> list[str]:
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f" (line {mark.line + 1})" if mark else ""
        reason = getattr(exc, "problem", None) or str(exc)
        return [error_line(path, ("-", "-", "parse", f"malformed YAML{where}: {reason}"))]
    if not isinstance(doc, dict):
        return [error_line(path, ("-", "-", "parse", "not a workflow: the document is not a mapping"))]
    jobs = doc.get("jobs")
    if jobs is not None and not isinstance(jobs, dict):
        return [error_line(path, ("-", "-", "parse", "`jobs` is not a mapping"))]
    release = is_release_workflow(path, doc)
    stem = Path(path).stem
    found: list[Violation] = []
    if release and mentions_maxwell_identity({k: v for k, v in doc.items() if k != "jobs"}):
        found.append(("(workflow)", "-", "L4", f"{MAXWELL_IDENTITY} is not a release identity"))
    for job_id, job in (jobs or {}).items():
        if isinstance(job, dict):
            found.extend(lint_job(str(job_id), job, stem, release, repo))
        else:
            found.append((str(job_id), "-", "parse", "job is not a mapping"))
    return [error_line(path, v) for v in found]


def collect(paths: list[str]) -> tuple[list[str], list[str]]:
    files: list[str] = []
    errors: list[str] = []
    for given in paths:
        path = Path(given)
        if path.is_dir():
            here = sorted(str(f) for f in path.iterdir() if f.is_file() and f.suffix in WORKFLOW_SUFFIXES)
            if not here:
                errors.append(error_line(given, ("-", "-", "input", "no workflow files (*.yml, *.yaml) found")))
            files.extend(here)
        elif path.is_file():
            files.append(given)
        else:
            errors.append(error_line(given, ("-", "-", "input", "no such file or directory")))
    return files, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("paths", nargs="+", help="workflow files or directories of them")
    parser.add_argument("--repo", help="name of the repository being linted (default: from $GITHUB_REPOSITORY)")
    args = parser.parse_args()
    repo = (args.repo or os.environ.get("GITHUB_REPOSITORY") or "").rsplit("/", 1)[-1] or None
    if repo is None:
        print("::warning::app-token-lint: repository name unknown (pass --repo); the own-repository check of L3 is skipped")
    files, errors = collect(args.paths)
    for file in files:
        try:
            text = Path(file).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(error_line(file, ("-", "-", "parse", f"cannot read file: {exc}")))
            continue
        errors.extend(lint_source(file, text, repo))
    for line in errors:
        print(line)
    if errors:
        print(f"app-token-lint: {len(errors)} violation(s) in {len(files)} file(s)")
        return 1
    print(f"app-token-lint: {len(files)} file(s) clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
