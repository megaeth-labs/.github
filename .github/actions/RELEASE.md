# The release pipeline

How MegaETH repositories cut, settle and publish releases with the shared
actions in this directory, how to install the pipeline in a repository, which
options exist, and what to do when something goes wrong.

The code is next to this file: `release-candidate/`, `release-settle/`,
`release-publish/` (the core), `release-verify-version/`,
`release-publish-rust-crates/`, `release-upload-artifact/`, `release-assets/`,
`release-snapshot/` (the snapshot bookends)
(the publish targets), and `release-tools/` (the text helpers they share, unit
tested by `actions-test.yml`). The reference callers a repository stamps from
are in `workflow-templates/` at the repository root. `README.md` beside this
file documents the Claude CI actions and is not needed for releases.

Contents:

1. [What it does, and the choices behind it](#what-it-does-and-the-choices-behind-it)
2. [One release, step by step](#one-release-step-by-step)
3. [Installing it in a repository](#installing-it-in-a-repository)
4. [Options](#options)
5. [Publish targets (`on-release.yml`)](#publish-targets-on-releaseyml)
6. [Operations and recovery](#operations-and-recovery)
7. [Reference](#reference)

## What it does, and the choices behind it

A release is three phases, each a workflow in the consuming repository
calling one composite action here at `@main`:

| Phase | Trigger | Result |
|---|---|---|
| **Candidate** | a maintainer dispatches `release-candidate.yml` with a version | a PR on the default branch that bumps the version and drafts the changelog entry; merging it creates `release-vX.Y.Z` at the merge commit |
| **Settle** | a maintainer dispatches `release-settle.yml` with the version and the release branch's tip | the dated changelog entry is committed to the release branch, the annotated tag `vX.Y.Z` is created there, and the GitHub Release is published with the entry as notes |
| **Publish targets** | the GitHub Release being published | whatever the repository ships: crates to crates.io, binaries to the artifact registry, downloads on the Release page — composed in `on-release.yml` from the publish-target actions |

The choices that shape it:

- **Trunk first.** The version bump and the changelog draft land on the
  default branch through an ordinary reviewed PR; the release branch is cut
  from that merge. Fixes for a release go to the release branch by PR and
  must also land on the default branch, because the next candidate is cut
  from there.
- **No release-candidate tags.** A tag is created exactly once, at
  settlement, on the commit that ships. Tags are immutable: the `v*` tag
  ruleset forbids updating or deleting them, and nothing but the app can
  create them.
- **One human gate.** The settle dispatch is the release decision. A
  `release` GitHub environment on the settle job makes the run wait for its
  required reviewers; that click is the approval. An optional `settlers`
  list can additionally restrict who may start a settle. Everything after
  the click is mechanical.
- **The changelog has one owner per phase.** The candidate PR drafts the
  entry (`## vX.Y.Z`, no date) from merged PR titles and syncs the previous
  release's final entry from its tag; settlement finalises it (date, any
  commits added on the release branch) on the release branch; the tag and the
  Release carry the final text. Nothing is back-merged: the default branch's
  copy of the latest entry has no date until the next candidate PR syncs it.
- **The app is the identity.** Every push, PR, tag and Release is made by
  the Maxwell GitHub App (`mega-maxwell[bot]`), from a token minted in the
  job. Its PRs trigger CI (a `GITHUB_TOKEN` push would not), and the
  rulesets make it the only actor that can create a tag or push to a release
  branch without a PR. The `cut` and publish stages refuse PRs the app did not
  open.
- **Credentials are scoped to release tags.** Publish credentials live in a
  `publish` environment whose deployment policy allows only `v*` tag refs, so
  a branch build can never read them. The environment has no reviewers: the
  human gate is settlement.
- **No force pushes to release branches, settle branches or tags.**
  Re-running settle supersedes what it made before (closes the old PR, drops
  the branch, pushes fresh), so it works in repositories whose rulesets ban
  force pushes. The one exception is a candidate re-dispatched while its PR
  is still open: that PR's branch is updated in place, which is a force push
  (see [Operations](#operations-and-recovery)).
- **Generic.** The actions know nothing about MegaETH: the version file and
  its format, the changelog path, the branch prefix, the app identity and
  every publish destination are inputs. The templates carry this
  organisation's defaults.

## One release, step by step

The direct-settle flow, which every migrated repository uses. Commands assume
`gh` authenticated as a maintainer and the default branch `main`.

**1. Candidate.**

```sh
gh workflow run release-candidate.yml --ref main -f version=1.2.3
```

Within a minute the app opens `chore(release): candidate v1.2.3` from the
branch `chore/release-candidate-1.2.3`: the version file bumped, whatever
`bump_command` maintains (a lockfile, path-dependency versions), the
changelog entry `## v1.2.3` drafted from the merged PR titles since the last
`v*` tag (grouped by Conventional Commit type, with PR links), and the
previous release's entry synced from its tag. Review it like any PR; fix
wording in it if the generated entry needs work. A stale candidate branch
from an earlier attempt is dropped first, unless its PR is still open.

**2. Cut.** Merging the candidate PR runs the `cut` job, which creates
`release-v1.2.3` at the merge commit. No tag yet. From here, fixes for the
release go to `release-v1.2.3` by PR, and each one must also reach `main`.

**3. Settle.**

```sh
gh workflow run release-settle.yml --ref main -f version=1.2.3 \
  -f commit="$(gh api repos/OWNER/REPO/git/ref/heads/release-v1.2.3 -q .object.sha)"
```

The run pauses at the `release` environment; a required reviewer approves it
under "Review deployments" on the run page. The dispatcher may be the
reviewer (the environment is created with self-review allowed). After the
click, the action verifies the commit is a full SHA, the release branch
exists, `v1.2.3` does not, the commit is the branch tip, the version file at
that commit says `1.2.3`, and `1.2.3` is newer than the latest tag. It warns
if the tip lacks a workflow the default branch has (see
[Operations](#operations-and-recovery)). If `settlers` is set, it checks
the dispatcher against it. Then it regenerates the notes up to the tip, writes
`## v1.2.3 (YYYY-MM-DD)` into the changelog, commits that straight onto
`release-v1.2.3` (the app bypasses the branch ruleset), creates the annotated
tag `v1.2.3` at that commit, and publishes the GitHub Release, marked latest,
with the entry as notes. About a minute after approval.

**4. Publish targets.** The Release's `published` event starts
`on-release.yml`, which builds and publishes whatever the repository ships.
Each target is a job; `dry_run` is off on a real release. See
[Publish targets](#publish-targets-on-releaseyml).

Settling by PR instead (`settle_mode: pr`, the action's default; no
migrated repository uses it): step 3 opens `chore(release): settle v1.2.3`
onto the release branch with the dated entry, and merging that PR is the
decision; `release-publish.yml` then tags the merge commit and publishes the
Release, refusing if the branch moved since the PR was made (the merge's first
parent must be the settled SHA) or the PR was not opened by the app.

## Installing it in a repository

Everything below was done for mega-agents, mega-evm, stateless-validator and
salt; copy from one of them when in doubt.

**1. The app must cover the repository.** The Maxwell GitHub App has to be
installed on it (organisation settings → GitHub Apps → mega-maxwell →
repository access). Nothing here can check that for you; a missing
installation shows up as the token step failing in the first run.

**2. Secret and variable access.** The workflows mint the app token from the
organisation secret `MEGA_MAXWELL_PK` and the organisation variable
`MEGA_MAXWELL_CLIENT_ID`. Both must be readable by the repository: for a
public repository the organisation's access policy must include public
repositories explicitly.

**3. Rulesets.** Two, both with the app and the repository admins as bypass
actors (`bypass_mode: always`):

- `release branch`, target `branch`, on `refs/heads/release-*`: `deletion`,
  `non_fast_forward`, `pull_request` (one approving review, code-owner review,
  squash merges), and a `branch_name_pattern` requiring `release-vX.Y.Z`.
  This is what makes every change on a release branch a reviewed PR, except
  the app's settle commit.
- `release tag`, target `tag`, on `refs/tags/v*`: `creation`, `update`,
  `deletion`, `non_fast_forward`, and a `tag_name_pattern` requiring
  semantic-version tags. This is what makes the app the only tag creator.

Copy them from a repository that has them rather than typing them:

```sh
src=megaeth-labs/mega-agents; dst=OWNER/REPO
for id in $(gh api repos/$src/rulesets -q '.[] | select(.name | test("release")) | .id'); do
  gh api repos/$src/rulesets/$id \
    | python3 -c 'import json,sys; r=json.load(sys.stdin); print(json.dumps({k:r[k] for k in ("name","target","enforcement","bypass_actors","conditions","rules")}))' \
    | gh api -X POST repos/$dst/rulesets --input -
done
```

`RepositoryRole` actor `5` is the admin role; the `Integration` actor is the
app's id.

**4. The `release` environment.** Required reviewers: the maintainers who
may approve a release. Self-review allowed, so the dispatcher can approve
their own dispatch (`prevent_self_review: false`). Deployment branch policy:
the default branch only, because that is the ref the settle workflow is
dispatched on. No secrets.

```sh
uid=$(gh api users/LOGIN -q .id)
gh api -X PUT repos/OWNER/REPO/environments/release --input - <<JSON
{"wait_timer": 0, "prevent_self_review": false,
 "reviewers": [{"type": "User", "id": $uid}],
 "deployment_branch_policy": {"protected_branches": false, "custom_branch_policies": true}}
JSON
gh api -X POST repos/OWNER/REPO/environments/release/deployment-branch-policies -f name=main -f type=branch
```

**5. The `publish` environment**, only if the repository has publish
targets. No reviewers. Deployment policy: tags matching `v*`. The publish
credentials go in as environment secrets (`CARGO_REGISTRY_TOKEN`,
`GCP_AUTH_KEY`, whatever the targets need); an environment secret wins over an
organisation or repository secret of the same name, and a repository-level
copy of a publish credential should not exist at all, since a branch build
could read it.

```sh
gh api -X PUT repos/OWNER/REPO/environments/publish --input - <<'JSON'
{"wait_timer": 0, "reviewers": [],
 "deployment_branch_policy": {"protected_branches": false, "custom_branch_policies": true}}
JSON
gh api -X POST repos/OWNER/REPO/environments/publish/deployment-branch-policies -f name='v*' -f type=tag
```

**6. The workflows.** Stamp `release-candidate.yml`, `release-settle.yml`
and `release-publish.yml` from "New workflow → By megaeth-labs" (or copy
them from `workflow-templates/`), then fill in the repository's facts, the
same values in all three: `version_file` and `version_pattern`, and
`changelog_file` if not `CHANGELOG.md`. In `release-candidate.yml`, set
`bump_command` if anything else must move with the version, and install the
toolchain it needs in the `propose` job before the action step. Keep
`settle_mode: direct` and the `environment: release` line in the settle job;
add `settlers: admin` (or a list of logins) only if starting a settle should
be restricted beyond what the environment's reviewers approve. Keep
`release-publish.yml`
even though direct settlement never triggers it: it is the PR-mode fallback,
and its job gate rejects anything the app did not open.

Add `on-release.yml` from the template only if there are publish targets.

**7. The changelog.** Create `CHANGELOG.md` with a preamble and nothing
else; the first candidate PR adds the first entry. A previous, hand-made
release history is not needed: the notes for the first pipeline release are
generated from the commits since the latest `v*` tag, whatever made it.

**8. First release.** Run the steps in
[One release, step by step](#one-release-step-by-step). If the repository
has publish targets, rehearse `on-release.yml` before the settle: it can only
run on a tag whose tree contains the file, so the rehearsal target is the
*previous* tag if the file was cherry-picked there, otherwise the first real
release is the first run.

## Options

Every input is documented in the action's `action.yml`; these are the ones a
repository decides.

**Where the version lives** (`version_file`, `version_pattern`, on all three
core actions, always the same values):

| Pattern | Reads / writes | Used by |
|---|---|---|
| `plain` | the whole file, trimmed | mega-agents (`VERSION`) |
| `toml` | the first line of the form `version = "…"` at column 0 — the `[package]` or `[workspace.package]` version, never a dependency's | mega-evm (`Cargo.toml`), stateless-validator (`Cargo.toml`), salt (`salt/Cargo.toml`) |
| `json` | the first `"version": "…"` | a `package.json` |

**What else moves with the version** (`bump_command`, candidate only): a
shell command run after the version file is rewritten, with `OLD_VERSION`
and `NEW_VERSION` in the environment. The candidate job must have the
toolchain it needs. Examples in use:

- `cargo update --workspace` — refresh `Cargo.lock` (salt).
- `sed -i -E "/path = /s/version = \"$OLD_VERSION\"/version = \"$NEW_VERSION\"/" Cargo.toml && cargo update --workspace`
  — path dependencies pinned to the workspace version, then the lockfile
  (mega-evm).

**How settlement is approved** (`settle_mode`, `settlers`, settle only):

| `settle_mode` | Decision | Requirements |
|---|---|---|
| `direct` (the templates) | the dispatch, approved through the `release` environment | the environment's required reviewers; the app bypasses the release-branch ruleset. `settlers` (default `any`) may additionally name who can start a settle: comma-separated logins and/or `admin` (the dispatcher must have admin permission, checked with the job token) |
| `pr` (the action default) | merging the settle PR | the release-branch ruleset requires a reviewed PR; `release-publish.yml` present on the release branch |

**Labels** (`pr_labels`, candidate and settle): for repositories whose
label gates apply to the app's PRs.

**Branch prefix** (`release_branch_prefix`, default `release-v`): change it
everywhere at once, including the `branches:` filter in
`release-publish.yml` and the `release branch` ruleset pattern.

**Identity** (`pr_author`, `git_user_name`, `git_user_email`): defaults are
the Maxwell app; only change them for a different app.

## Publish targets (`on-release.yml`)

The Release's `published` event runs the repository's `on-release.yml`. What
every one of them carries, and why (the template has all of it):

- `TAG: ${{ github.ref_name }}` and a `Require a tag ref` first step in each
  job, never a tag input: the `publish` environment authorises the run's
  ref, so that ref is the only thing the run may build and publish.
- `environment: publish` on every job that reads a publish credential.
- A workflow-level `concurrency` group keyed on `github.ref`,
  `cancel-in-progress: false`: uploads must not overlap and must not be
  cancelled mid-flight.
- `release-verify-version` between the build and the first publish step for
  each binary. Never wrap a probe of the built artifact in
  `2>/dev/null || echo …`: that turns a binary that cannot load into a green
  step and a published download.
- One build feeding every target when several targets ship the same file
  (a workflow artifact between jobs), so the Release page and the registry
  carry the same bytes.
- `dry_run` threaded from a `workflow_dispatch` input into every target, so
  the whole workflow can be rehearsed on a tag ref:
  `gh workflow run on-release.yml --ref vX.Y.Z -f dry_run=true`.

The targets:

| Action | Publishes | On re-run | On `dry_run` |
|---|---|---|---|
| `release-publish-rust-crates` | an explicit crate list to crates.io at the release version — one `cargo publish -p … -p …` (Cargo ≥ 1.90 orders and waits); polls the index afterwards. Every crate's manifest must already be at the version. Never `--workspace`: list the crates. | crates already at the version are skipped | `cargo publish --dry-run` for every listed crate, nothing uploaded |
| `release-upload-artifact` | one file to Artifact Registry (generic repository) or a GCS bucket; every destination is an input. Authentication is the caller's: run `google-github-actions/auth` before it. | identical file already there → `exists`; different → fails, never overwrites | checksum and destination check only |
| `release-assets` | files plus a generated `SHA256SUMS` on the GitHub Release; needs the job token with `contents: write` | `--clobber` | prints the sums, attaches nothing |
| `release-verify-version` | nothing — runs a version probe (`my-binary --version`) and requires `<name> <version>` (`expected` overrides, with `{name}` and `{version}`) | n/a | a mismatch warns; a probe that cannot run fails even here |

The three migrated repositories with targets: mega-evm publishes four crates
and uploads `mega-evme` to the registry and the Release page;
stateless-validator uploads both of its binaries to the registry and the
Release page; mega-agents and salt ship nothing beyond the Release.

## Snapshots (`snapshot-publish.yml`)

Not every component is versioned. Deployments pin some binaries by commit —
`version: latest`, `profile: release`, and the commit — and want "build this
commit and push it", with no tag, no GitHub Release and no changelog. That
is the snapshot flow: one dispatch-only workflow, `snapshot-publish.yml`,
bookended by `release-snapshot`:

1. `release-snapshot` `stage: resolve` turns the dispatch input `ref` (or
   the run's own commit) into the full commit, refuses it unless it is
   reachable from `allowed_branches`, and hands out the registry
   coordinates: `version` = the commit, `path` = `<profile>/<label>`
   (`release/latest`).
2. The repository's own build steps, then `release-upload-artifact` per
   file with those coordinates — the layout the tagged pipeline writes,
   `latest` in place of the tag, so deployment tooling reads both the same
   way. Re-runs on the same commit are no-ops for files already there.
3. `release-snapshot` `stage: summary` writes the run summary: every
   upload with its checksum, and the manifest entry to pin; optionally a
   `snapshot/<package>` commit status linking back to the run.

Install: copy the template, replace the build steps and destinations, and
put the GCP secret in an environment whose deployment branch policy allows
the branch the workflow is dispatched from (the environment authorises the
dispatch ref; `allowed_branches` guards the commit actually built). A
repository that also runs the tagged pipeline keeps `publish` for `v*` tags
and gives snapshots their own environment. Nothing else is needed: no
version file, no changelog, no rulesets, no app.

## Operations and recovery

**The release branch moved after settling** (a fix landed): run settle
again with the new tip. In direct mode that is the whole story. In PR mode
the old settle PR is closed with a comment, its branch deleted, and a fresh
PR opened: nothing is force-pushed, so this also works under a
"ban force push" ruleset.

**A workflow the release needs is not on the release branch.** A `release`
event runs `on-release.yml` from the *tag's* tree, and `release-publish.yml`
runs from the release branch, so a workflow added to the default branch after
the branch was cut is silently absent: the Release publishes with nothing
attached and no failed run. Settle warns when the tip lacks a workflow the
default branch has. Fix: cherry-pick the file onto the release branch through
its own PR, then settle. (A tag's tree is final: a target that was missing
or broken at a tag cannot be re-run for that tag; the next release gets it.)

**A stale candidate branch exists** from an earlier attempt: the candidate
action deletes it before pushing, unless a PR on it is still open, in which
case that PR is updated in place with a force push of its branch. In a
repository whose rulesets ban force pushes, close the open candidate PR
before re-dispatching; the action then drops the branch and opens a fresh
PR.

**Two runs of the same stage overlap.** They queue, never cancel: the
candidate's `propose` and `cut`, and `release-publish`'s `publish`, carry
job-level concurrency groups (job-level, because those workflows also start
on every PR closing on their branch, and a workflow-wide group would let such
a run evict a queued one); settle has a group per version, `on-release` a
group per tag.

**The tag already exists** when settling: that version is released. Pick the
next version and start from the candidate.

**A publish target failed after the tag was created**: fix the cause on
the default branch. If the fix is in the shared action, dispatch
`on-release.yml` again on the tag (`--ref vX.Y.Z -f dry_run=false`); all
targets are idempotent, so the ones that succeeded are no-ops. If the fix is
in the workflow file itself, it cannot reach that tag's tree; the next release
carries it.

**The PR reviewer fails on a PR that edits `claude.yml`**: by design of
`anthropics/claude-code-action`, which refuses to run from a PR whose
workflow file differs from the default branch's. It is not a required check;
merge, and the reviewer works again from the merged file.

**The app cannot push, tag, or read the secret**: check, in this order, that
the app is installed on the repository, that the organisation secret and
variable are readable by it (public repositories are opted in separately),
and that the app is a bypass actor on both rulesets.

## Reference

What each action does, in one line:

| Action | Trigger in the consumer | Does |
|---|---|---|
| `release-candidate` `stage: propose` | `workflow_dispatch` on the default branch | bumps `version_file`, runs `bump_command`, drafts this release's changelog entry under `## vX.Y.Z`, syncs the previous release's entry from its tag, opens `chore/release-candidate-X.Y.Z` |
| `release-candidate` `stage: cut` | that PR merging | creates `release-vX.Y.Z` at the merge commit |
| `release-settle` | `workflow_dispatch` with version + tip SHA | guards, warns if the tip lacks a workflow the default branch has, regenerates the entry up to the tip and stamps the date; `direct`: commits it to the release branch and publishes at once; `pr`: opens `chore/release-settle-vX.Y.Z` (a re-run closes the previous settle PR and opens a fresh one) |
| `release-publish` | the settle PR merging, or `release-settle` in direct mode | annotated tag at the commit (refuses if it exists or the branch drifted), GitHub Release with the entry as notes, marked latest |
| `release-snapshot` `stage: resolve` | `workflow_dispatch` of `snapshot-publish.yml` | resolves `ref` (or the run's commit) to a full SHA, refuses it unless reachable from `allowed_branches`, outputs the registry `version` (the commit) and `path` (`<profile>/<label>`) |
| `release-snapshot` `stage: summary` | after the uploads in the same job | run summary with every upload, its checksum and the manifest entry to pin; optional `snapshot/<package>` commit statuses |

Release notes are generated from commit subjects between the previous `v*`
tag and the settled commit, grouped by Conventional Commit type, with PR
links from `(#N)` suffixes; `chore(release):` commits are left out. The text
logic (`normalize`, `is-greater`, `read-file`, `bump-file`, `notes`,
`changelog-insert`, `changelog-extract`, `changelog-copy`) lives in
`release-tools/release_tools.py`, the crate helpers in `crates_tools.py`;
both are unit tested by `actions-test.yml`, which also drives
`release-verify-version` end to end with fake binaries. Consumers track the
actions at `@main`: a merge here reaches every repository at once, and that
workflow is the gate.

Requirements on the consumer's side, in one list: the app installed; the
organisation secret `MEGA_MAXWELL_PK` and variable `MEGA_MAXWELL_CLIENT_ID`
readable; the two rulesets with the app as bypass actor; the `release`
environment (and `publish`, for targets); `gh` and `python3` on the runner
(any GitHub-hosted image); the three core workflows, with the same
`version_file`/`version_pattern`/`changelog_file` in each; a `CHANGELOG.md`.
