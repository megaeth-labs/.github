# release-tools

Not an action: the pure text helpers the `release-*` actions share, kept out
of the bash steps so they can be unit tested without a repository. Stdlib
only. The actions call them as `python3 $GITHUB_ACTION_PATH/../release-tools/<module>.py <subcommand> …`.

## `release_tools.py`

| Subcommand | Does |
|---|---|
| `normalize VERSION` | `X.Y.Z` on stdout (accepts `vX.Y.Z`); exit 1 if not a semantic version |
| `is-greater VERSION LATEST_TAG_OR_EMPTY` | exit 0 if `VERSION` is newer than the tag, else 1 |
| `read-file PATH PATTERN` | the version found in the file (`plain`, `toml`, `json`) |
| `bump-file PATH PATTERN VERSION` | rewrite the version in place; prints the old version |
| `notes REPO VERSION DATE` | stdin `"<sha>\t<subject>"` lines → the Markdown section: heading `## vX.Y.Z (DATE)` (no date when `DATE` is empty), commits grouped by Conventional Commit type, PR links from `(#N)` suffixes, `chore(release):` commits dropped |
| `changelog-insert PATH VERSION SECTION_MD` | insert or replace the version's section; prints `inserted` / `replaced`; keeps exactly one blank line between blocks so formatters leave the file alone |
| `changelog-extract PATH VERSION` | the section body on stdout; exit 1 if absent |
| `changelog-copy SRC DST VERSION` | copy the version's section (heading included) from one changelog into another; prints `inserted` / `replaced` / `unchanged` / `absent` |

Version patterns: `plain` is the whole file, trimmed; `toml` is the first
line of the form `version = "…"` at column 0 (the `[package]` or
`[workspace.package]` version, never a dependency's); `json` is the first
`"version": "…"`.

## `crates_tools.py`

Helpers for `release-publish-rust-crates`: parse the crate list, check every
listed crate's manifest version against `cargo metadata`, and partition the
list into crates to publish and crates already on crates.io.

## Tests

`test_release_tools.py` and `test_crates_tools.py`, run by `actions-test.yml`
on every PR: `python3 -m unittest discover -s .github/actions/release-tools -p 'test_*.py'`.
