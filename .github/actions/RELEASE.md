# The release pipeline

How MegaETH repositories cut, settle and publish releases with the shared
actions in this directory, how to install the pipeline in a repository, which
options exist, and what to do when something goes wrong.

The code is next to this file: `release-candidate/`, `release-route/`,
`release-settle/`, `release-publish/` (the core), `release-verify-version/`,
`release-publish-rust-crates/`, `release-upload-artifact/`, `release-assets/`
(the publish targets), `release-snapshot/` (the snapshot bookends),
`release-tools/` (the text helpers they share, unit tested by
`actions-test.yml`), and `app-token-lint/` (the lint that keeps app tokens
scoped). `git-auth/` is the credential wrapper the actions run their git and
gh commands under. The reference callers a repository stamps from are in
`workflow-templates/` at the repository root. `README.md` beside this file
documents the Claude CI actions and is not needed for releases.

Contents:

1. [What it does, and the choices behind it](#what-it-does-and-the-choices-behind-it)
2. [One release, step by step](#one-release-step-by-step)
3. [Installing it in a repository](#installing-it-in-a-repository)
4. [Options](#options)
5. [Publish targets (`on-release.yml`)](#publish-targets-on-releaseyml)
6. [Snapshots (`snapshot-publish.yml`)](#snapshots-snapshot-publishyml)
7. [Operations and recovery](#operations-and-recovery)
8. [Reference](#reference)

## What it does, and the choices behind it

A release is four phases across three workflows in the consuming repository:
candidate, settle (including its publish job), and publish targets. They call
the composite actions here at `@main`. The shared actions hold the decisions:
the read-only `release-route` action classifies every push and dispatch and
answers `cut`, `refresh`, `publish` or `skip`, with a one-line reason in the
job log.

| Phase | Trigger | Result |
|---|---|---|
| **Candidate** | a maintainer dispatches `release-candidate.yml` with a version | a PR on the default branch that bumps the version and drafts the changelog entry; merging it creates `release-vX.Y.Z` at the merge commit |
| **Settle** | a push to `release-vX.Y.Z`: the branch being cut, and every later push to it | `route` answers `refresh`; `release-settle` writes nothing for a clean candidate merge, otherwise opens or updates one reviewed `chore/release-settle-vX.Y.Z` PR carrying the changelog entry |
| **Publish** | the settle PR merging, or a dispatch of `release-settle.yml` with a version whose branch needs no settle PR | `release-publish` creates the annotated tag `vX.Y.Z` at the settled commit and publishes the GitHub Release with the changelog section as notes |
| **Publish targets** | the GitHub Release being published | whatever the repository ships: crates to crates.io, binaries to the artifact registry, downloads on the Release page, composed in `on-release.yml` from the publish-target actions |

The choices that shape it:

- **Trunk first.** The version bump and the changelog draft land on the
  default branch through an ordinary reviewed PR; the release branch is cut
  from that merge. Fixes for a release go to the release branch by PR and
  should also land on the default branch, because the next candidate is cut
  from there. When the release is an earlier commit rather than the tip
  (`base_commit`), the same reviewed PR lands on the release branch instead
  and the default branch is left alone; see
  [Releasing a commit that is not the tip](#releasing-a-commit-that-is-not-the-tip).
- **No release-candidate tags.** A tag is created exactly once, at
  publication, on the commit that ships, and `release-publish` is the only
  place in the flow that creates one. Tags are immutable: the `v*` tag
  ruleset forbids updating or deleting them, and its only bypass actors are
  the repository admin role and the app, so nothing else can create one.
- **The settle PR is the release decision.** A push to the release branch
  never publishes directly unless it is the fresh settle PR merging; other
  pushes refresh settlement. A clean candidate merge creates no settle PR.
  When the branch is exactly the candidate merge, with no
  fixes on top and no settle PR or tag, and its changelog section matches the
  regenerated notes (or changelog handling is disabled), a maintainer dispatches
  `release-settle.yml` with the version: the clean state routes straight to
  `publish`, and the run waits for a required reviewer of the `release`
  environment. That approval stands in for the PR.
- **Settlement is a state, not a mode.** For a versioned dispatch,
  `release-route` reads the repository (the candidate PR's merge commit,
  whether that commit is an ancestor of the branch tip, whether a settle PR
  is open, whether the tag and the GitHub Release exist) and computes one of
  five states: `clean`, `needs-settle-pr`, `resume`, `published`, `blocked`.
  Clean and resume route to `publish`, needs-settle-pr routes to `refresh`,
  published and blocked skip with the reason. A tag that exists at the
  candidate merge without its Release (a run that died between the two
  steps) is `resume`: publishing runs again and creates the missing Release.
  Dispatch routing assumes a matching changelog; publish verifies the actual
  section and refuses a mismatch before tagging. A refresh action also compares
  the section, so a stale section creates a settle PR even at the candidate
  merge. A tag at a settle-PR merge is blocked by versioned dispatch; recover
  that publication by re-running its original push-triggered run.
- **The changelog has one owner per phase, and no dates.** The candidate PR
  drafts the entry under an undated `## vX.Y.Z` heading from non-merge
  commit subjects and syncs the previous release's final entry from its tag. The
  settle PR re-drafts the same undated entry over the commits that actually
  ship. The Release body is that section read from the tagged tree,
  verbatim; nothing stamps a date anywhere. The default branch catches up in
  the next candidate PR: nothing is back-merged.
- **The app is the identity.** Every push, PR, tag and Release is made by
  the Gutenberg GitHub App (`mega-gutenberg[bot]`), from a token minted in
  the job. Its PRs trigger CI (a `GITHUB_TOKEN` push would not), the tag
  ruleset makes it the only tag creator, and publish refuses PRs the app did
  not open.
- **Credentials are organization-level; one environment gates the writes.**
  The app credentials are an organization variable (`MEGA_GUTENBERG_CLIENT_ID`)
  and an organization secret (`MEGA_GUTENBERG_PK`) granted to each consumer, so the branch and PR
  jobs mint tokens with no environment at all. Only the jobs that tag,
  create the Release or upload release artifacts run in the `release` environment,
  which has required reviewers and a deployment policy of the default
  branch, `release-v*` branches and `v*` tags. The publish-target
  credentials (`CARGO_REGISTRY_TOKEN`, `GCP_AUTH_KEY`, whatever the targets
  need) live in it as environment secrets, so a branch build can never read
  them.
- **A lint holds those rules.** `app-token-lint` runs on every workflow
  change (the `app-token-lint.yml` template). Rule L2' allows a Gutenberg
  mint only in `release-candidate.yml`, `release-settle.yml`,
  `on-release.yml` (exact filenames, not prefixes); rule L6 requires every app
  token in a release workflow to list its `permission-*` inputs explicitly,
  because a token minted without them gets every permission of the
  installation, contents write included.
- **Nothing force-pushes any branch, or a tag.** Re-dispatching a candidate
  supersedes the open one: it closes that PR with a comment, deletes the
  branch, pushes a fresh one as a new ref and opens a fresh PR. Re-running a
  settle refresh updates its own PR's branch with ordinary pushes, and a PR
  it does not maintain is closed and started fresh. So the pipeline works in
  repositories whose rulesets ban force pushes on every branch, with no
  exemption. A test (`.github/scripts/test_no_force_push.py`) fails if any
  shipped action or template gains a forced push.
- **Generic.** The actions know nothing about MegaETH: the version file and
  its format, the changelog path, the branch prefix, the app identity and
  every publish destination are inputs. The templates carry this
  organisation's defaults.

## One release, step by step

Commands assume `gh` authenticated as a maintainer and the default branch
`main`.

**1. Candidate.**

```sh
gh workflow run release-candidate.yml --ref main -f version=1.2.3
```

The app opens a candidate PR from the branch
`chore/release-candidate-1.2.3`: the version file bumped, whatever
`bump_command` maintains (a lockfile, path-dependency versions), the
changelog entry `## v1.2.3` drafted from non-merge commit subjects since the last
`v*` tag (grouped by Conventional Commit type, with PR links), and the
previous release's entry synced from its tag. Review it like any PR; fix
wording in it if the generated entry needs work.

While the PR is open, every push to the default branch starts the workflow's
`refresh` job for it: the refresh merges the default branch into the PR's
head (a merge commit, never a rebase, so the branch history is not
rewritten) and re-drafts the entry. That push clears approvals under
`require_last_push_approval`, so the merge must be re-approved afterwards.
Re-dispatching the candidate supersedes the PR instead: it is closed with a
comment, its branch is deleted, and a fresh branch and PR are opened, so
edits made on it are not carried over.

**2. Cut.** Merging the candidate PR is a push to the default branch;
`route` recognises the merged, app-authored candidate PR and answers `cut`,
and the cut job creates `release-v1.2.3` at the merge commit. No tag yet.
From here, fixes for the release go to `release-v1.2.3` by PR, and each one
should also reach `main`.

**3. Settle.** The push that created the branch, and every later push to it,
runs `release-settle.yml`. Once the candidate has landed on the branch,
`route` answers `refresh` and the settle job opens (or refreshes) the PR
from `chore/release-settle-v1.2.3` onto the release branch, with the entry
for the commits since the previous tag under the undated `## v1.2.3`
heading when the state is `needs-settle-pr`. At the candidate merge with no
open settle PR or tag and a section matching regenerated notes (or changelog
handling disabled), the state is `clean`: the action skips all write steps
and creates no settle PR. Its summary says the release branch is unchanged
at the candidate merge and nothing was written. Push routing cannot see
changelog state, so its `refresh` answer can legitimately end in this clean
no-op. Use the versioned dispatch in step 4 to publish that branch. Otherwise,
review the settle PR like any PR; each new push refreshes it.

**4. Publish**, one of two ways:

- *Merge the settle PR.* The merge is a push to the release branch; `route`
  re-reads the PR through the API (merged, merge commit equals the pushed
  commit, head and base names, opened by the app) and checks the settled-SHA
  marker in its body against the merge commit's parent, then answers
  `publish`. A PR that went stale before it merged (the branch moved after
  it was written) publishes nothing: `route` answers `refresh` and a fresh
  PR follows.
- *Dispatch a clean branch.*

  ```sh
  gh workflow run release-settle.yml --ref main -f version=1.2.3
  ```

  When the branch tip is exactly the candidate merge, with no open settle PR
  and no tag, dispatch routing assumes a clean changelog and routes straight to
  `publish` with `settle_source=dispatch`. Publish compares the committed
  section with regenerated notes and refuses a mismatch; dispatch with a
  blank `version` to refresh that section through a settle PR first.
  A branch with commits beyond the candidate merge, or an open
  settle PR, routes to `refresh` instead; a version already published, or
  one whose candidate is not an ancestor of the tip, skips with the reason.
  A tag not at the candidate merge also skips, even when a settle PR created
  it; re-run the original push-triggered run to recover that publication.
  A blank `version` refreshes every eligible release branch and never
  publishes.

Both ways run the same publish job in the `release` environment, so both
wait for a required reviewer under "Review deployments" on the run page.
After the approval, the job re-verifies the PR (for a dispatch, the merged
candidate PR, and that the release branch still points at the commit,
checked again right before the tag push), creates the annotated tag `v1.2.3`
at that commit once, and publishes the GitHub Release with the entry as
notes, marked latest only when it is newer than the current latest Release.
A version that is not newer than every other `vX.Y.Z` tag is refused before
the tag, so an older line merged late is never tagged or made latest.

**5. Publish targets.** The Release's `published` event starts
`on-release.yml`, which builds and publishes whatever the repository ships.
Each target is a job; `dry_run` is off on a real release. See
[Publish targets](#publish-targets-on-releaseyml).

### Releasing a commit that is not the tip

`main` moves while a release is being prepared. To ship an earlier commit,
name it:

```sh
gh workflow run release-candidate.yml --ref main \
  -f version=1.2.3 -f base_commit="$(git rev-parse origin/main~4)"
```

The commit may be given as anything the checkout resolves: a full SHA, a
tag, `origin/main~4`. It must be reachable from the default branch, **or**
sit on the latest `v*` release line (from the merge-base with the default
branch through that tag). Settlement leaves the tag off trunk, so a hotfix
of the current release is named as that tag (or its peeled SHA), not as a
commit further down the default branch.

A side branch that never landed on trunk is still refused. So is an older
release line that a higher `v*` tag has already passed: the version must
still beat the newest tag, and those commits are outside the latest-line
window.

Step 1 then works differently, and steps 3 to 5 are unchanged:

- `propose` creates `release-v1.2.3` at that commit itself, rather than
  leaving it to `cut`, and opens the candidate PR **against that branch**.
  The PR cannot target the default branch: merging it there would take the
  commits this release is deliberately leaving out. `propose` also carries
  the default branch's release workflows onto the old tree (the
  `release_workflows` input, by default `release-settle.yml` and
  `on-release.yml`), because a branch cut at an older commit would otherwise
  run pre-migration workflows; a stale `release-publish.yml` found there is
  deleted.
- The changelog entry is drafted over what actually ships, the commits from
  the previous tag up to the named commit, not up to the tip.
- Merging the candidate PR puts the version bump and the entry on
  `release-v1.2.3`. There is no step 2: the `cut` job does not fire, because
  `route` only selects `cut` for a candidate merged into the default branch.
  The release-branch ruleset governs this PR, so it needs its approving
  review, like any other change to a release branch.
- **The default branch is left untouched.** Its version file keeps the old
  version, and it gains no changelog entry until the next candidate, which
  syncs the entry back from the tag the way it does after any release. The
  next version must still be newer than `v1.2.3`.

If an attempt fails after the branch was created (a broken `bump_command`,
say), re-dispatching the same version and commit reuses the branch. If
hotfix PRs have already landed on it, propose sits on the tip (it does not
reset to `base_commit`) and skips the version bump when the version file
already reads the requested version. A branch that does not contain
`base_commit` is refused.

## Installing it in a repository

**1. The app must cover the repository.** The Gutenberg GitHub App has to be
installed on it (organisation settings, GitHub Apps, mega-gutenberg,
repository access). Nothing here can check that for you; a missing
installation shows up as the token step failing in the first run.

**2. Organization variable and secret.** The workflows mint the app token from
the organization variable `MEGA_GUTENBERG_CLIENT_ID` and the organization secret
`MEGA_GUTENBERG_PK`. Grant the organization secret access to each consumer
repository, and make the variable available to it. Organization scope, not an environment: the
candidate and settle branch jobs mint tokens with no environment, so the
credentials must resolve outside one.

**3. Rulesets.** Two:

- `release branch`, target `branch`, on `refs/heads/release-*`: `deletion`,
  `non_fast_forward`, `pull_request` (one approving review, squash or merge
  merges), and a `branch_name_pattern` requiring `release-vX.Y.Z`. No app
  bypass on this one: the settle PR is genuinely reviewed. Required checks
  use `do_not_enforce_on_create: true` so the branch can be cut, and "require
  branches to be up to date" is on.
- `release tag`, target `tag`, on `refs/tags/v*`: `creation`, `update`,
  `deletion`, `non_fast_forward`, and a `tag_name_pattern` requiring
  semantic-version tags. Bypass actors: the repository admin role and the
  app. This is what makes the app the only tag creator.

A ruleset that restricts branch deletion must not cover
`refs/heads/chore/release-*`: the pipeline deletes those branches when it
supersedes or replaces a PR. Copy the rulesets from a repository that has
them rather than typing them:

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

**4. The `release` environment.** The single gated environment for tagging,
Release creation and artifact upload; snapshots use `snapshot` instead,
outside the human review gate. Required reviewers: the maintainers who
may approve a release. A versioned dispatch publishes without a PR, so this
review is its approval. Deployment policy: the default branch, `release-v*`
branches and `v*` tags. The settle publish job runs on the first two, the
upload jobs on the last; a ref outside the policy can never enter the
environment. The publish-target credentials go in as environment secrets
(`CARGO_REGISTRY_TOKEN`, `GCP_AUTH_KEY`, whatever the targets need); an
environment secret wins over a repository secret of the same name, and a
repository-level copy of a publish credential should not exist at all, since
a branch build could read it.

```sh
uid=$(gh api users/LOGIN -q .id)
gh api -X PUT repos/OWNER/REPO/environments/release --input - <<JSON
{"wait_timer": 0, "prevent_self_review": false,
 "reviewers": [{"type": "User", "id": $uid}],
 "deployment_branch_policy": {"protected_branches": false, "custom_branch_policies": true}}
JSON
gh api -X POST repos/OWNER/REPO/environments/release/deployment-branch-policies -f name=main -f type=branch
gh api -X POST repos/OWNER/REPO/environments/release/deployment-branch-policies -f name='release-v*' -f type=branch
gh api -X POST repos/OWNER/REPO/environments/release/deployment-branch-policies -f name='v*' -f type=tag
```

**5. The workflows.** Stamp `release-candidate.yml`, `release-settle.yml`
and `app-token-lint.yml` from "New workflow, By megaeth-labs" (or copy them
from `workflow-templates/`), then fill in the repository's facts, the same
values in the first two: `version_file` and `version_pattern`, and
`changelog_file` if not `CHANGELOG.md`. In `release-candidate.yml`, set
`bump_command` if anything else must move with the version (with
`dependency_token` when the command reads private repositories), and install
the toolchain it needs in the `propose` job before the action step. There is
no `release-publish.yml` to install: publishing is the `publish` job of
`release-settle.yml`. Add `on-release.yml` from the template only if there
are publish targets. Check the copies before pushing (from a checkout of
this repository):

```sh
python3 .github/scripts/app_token_lint.py --repo REPO /path/to/REPO/.github/workflows
```

Required PR checks must also run against release branches. A consumer
`pull_request.branches: [main]` filter must include `"release-v*"` too
(substitute the actual default branch); audit job conditions, path filters,
test workflows and any `compat:` label check. Otherwise a candidate targeting
a release branch, and the follow-up settle PR, cannot satisfy those required
checks. Carry the corrected CI workflows onto existing release branches.
For `base_commit` candidates, include them in `release_workflows`, for example:

```yaml
release_workflows: |
  .github/workflows/release-settle.yml
  .github/workflows/on-release.yml
  .github/workflows/lint.yml
```

The default carry list includes only the two release workflows, not lint or
tests. Fix the CI filters on the default branch before proposing the candidate
so its PR carries the corrected files.

**6. The changelog.** Create `CHANGELOG.md` with a preamble and nothing
else; the first candidate PR adds the first entry. A previous, hand-made
release history is not needed: the notes for the first pipeline release are
generated from the commits since the latest `v*` tag, whatever made it.

**7. First release.** Run the steps in
[One release, step by step](#one-release-step-by-step). If the repository
has publish targets, rehearse `on-release.yml` before the settle: it can
only run on a tag whose tree contains the file, so the rehearsal target is
the *previous* tag if the file was cherry-picked there, otherwise the first
real release is the first run.

## Options

Every input is documented in the action's `action.yml`; these are the ones a
repository decides.

**Where the version lives** (`version_file`, `version_pattern`, on all the
core actions, always the same values):

| Pattern | Reads / writes | Typical home |
|---|---|---|
| `plain` | the whole file, trimmed | a `VERSION` file |
| `toml` | the first line of the form `version = "…"` at column 0: the `[package]` or `[workspace.package]` version, never a dependency's | `Cargo.toml`, `pyproject.toml` |
| `json` | the first `"version": "…"` | a `package.json` |

**What else moves with the version** (`bump_command`, candidate only): a
shell command run after the version file is rewritten, with `OLD_VERSION`
and `NEW_VERSION` in the environment, in the repository root, under
`bash -euo pipefail`; whatever it changes is committed with the bump. The
candidate job must have the toolchain it needs. When the command reads
private repositories, give it `dependency_token`: a separate read-only token
naming those repositories, never the release token. Examples:

- `cargo update --workspace`: refresh a Rust workspace's `Cargo.lock`.
- `sed -i -E "/path = /s/version = \"$OLD_VERSION\"/version = \"$NEW_VERSION\"/" Cargo.toml && cargo update --workspace`:
  path dependencies pinned to the workspace version, then the lockfile.

**Labels** (`pr_labels`, candidate and settle): for repositories whose label
gates apply to the app's PRs. The templates leave this empty: where a consumer
requires a `compat:` label, the reviewer chooses it for each candidate or
settle PR. The shared actions do not enforce a compatibility-label gate.

**Branch prefix** (`release_branch_prefix`, default `release-v`): change it
everywhere at once, including the `branches:` filter in `release-settle.yml`
and the `release branch` ruleset pattern.

**Identity** (`pr_author`, `git_user_name`, `git_user_email`): the defaults
are the Gutenberg app; only change them for a different app. The lint
refuses `mega-maxwell[bot]` as a git identity or PR-author filter in a
release workflow (rule L4).

## Publish targets (`on-release.yml`)

The Release's `published` event runs the repository's `on-release.yml`. What
every one of them carries, and why (the template has all of it):

- `TAG: ${{ github.ref_name }}` and a `Require a tag ref` first step in each
  job, never a tag input: the `release` environment authorises the run's
  ref, so that ref is the only thing the run may build and publish.
- `environment: release` on every job that reads a release publish credential.
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
- `dry_run` threaded from a `workflow_dispatch` input (default true there)
  into every target, so the whole workflow can be rehearsed on a tag ref:
  `gh workflow run on-release.yml --ref vX.Y.Z -f dry_run=true`. A run
  started by the Release event is never a dry run.

A `release` event resolves the workflow from the tagged commit's tree, so
the file must exist at the tag. A release branch cut from a default branch
that has it carries it; a branch cut before it landed needs it cherry-picked
(through its own PR, the `release-*` ruleset requires one) before the settle
PR is merged, or the Release publishes with nothing attached and no failed
run. Settle warns when the settled commit lacks a workflow the default
branch has.

The targets:

| Action | Publishes | On re-run | On `dry_run` |
|---|---|---|---|
| `release-publish-rust-crates` | an explicit crate list to crates.io at the release version: one `cargo publish -p … -p …` (Cargo ≥ 1.90 orders and waits); polls the index afterwards. Every crate's manifest must already be at the version. Never `--workspace`: list the crates. | crates already at the version are skipped | `cargo publish --dry-run` for every listed crate, nothing uploaded |
| `release-upload-artifact` | one file to Artifact Registry (generic repository) or a GCS bucket; every destination is an input. Authentication is the caller's: run `google-github-actions/auth` before it. | identical file already there → `exists`; different → fails, never overwrites | checksum and destination check only |
| `release-assets` | files plus a generated `SHA256SUMS` on the GitHub Release; needs the job token with `contents: write` | `--clobber` | prints the sums, attaches nothing |
| `release-verify-version` | nothing: runs a version probe (`my-binary --version`) and requires `<name> <version>` (`expected` overrides, with `{name}` and `{version}`) | n/a | a mismatch warns; a probe that cannot run fails even here |

## Snapshots (`snapshot-publish.yml`)

Not every component is versioned. Deployments pin some binaries by commit
(`version: latest`, `profile: release`, and the commit) and want "build this
commit and push it", with no tag, no GitHub Release and no changelog. That
is the snapshot flow: one dispatch-only workflow, `snapshot-publish.yml`,
bookended by `release-snapshot`:

1. `release-snapshot` `stage: resolve` turns the dispatch input `ref` (or
   the run's own commit) into the full commit, refuses it unless it is
   reachable from `allowed_branches`, and hands out the registry
   coordinates: `version` is the commit, `path` is `<profile>/<label>`
   (`release/latest`).
2. The repository's own build steps, then `release-upload-artifact` per file
   with those coordinates: the layout the tagged pipeline writes, with
   `latest` in place of the tag, so deployment tooling reads both the same
   way. Re-runs on the same commit are no-ops for files already there.
3. `release-snapshot` `stage: summary` writes the run summary: every upload
   with its checksum, and the manifest entry to pin; optionally a
   `snapshot/<package>` commit status linking back to the run.

Install: copy the template, replace the build steps and destinations, and
put the GCP secret in the `snapshot` environment whose deployment policy allows the
branch the workflow is dispatched from. The environment authorises the
dispatch ref; `allowed_branches` guards the commit actually built. Snapshots
stay outside the `release` environment's human review gate. Nothing
else is needed: no version file, no changelog, no rulesets, no app.

## Operations and recovery

**The release branch moved after the settle PR was written.** Nothing to
do: the push already started a settle run that refreshes the PR at the new
tip. If the stale PR was merged anyway, nothing publishes; `route` answers
`refresh` ("merged settle PR #N was stale … a fresh settle PR follows") and
the fresh PR is the one to review.

**A workflow the release needs is not on the release branch.** A `release`
event runs `on-release.yml` from the *tag's* tree, so a workflow added to
the default branch after the branch was cut is silently absent: the Release
publishes with nothing attached and no failed run. Settle warns when the
tip lacks a workflow the default branch has. Fix: cherry-pick the file onto
the release branch through its own PR, then merge the settle PR. (A tag's
tree is final: a target that was missing or broken at a tag cannot be re-run
for that tag; the next release gets it.)

**A candidate is re-dispatched** (a fix landed, or the first attempt failed
part-way): the fresh candidate supersedes the old one. An open candidate PR
for that version is closed with a comment saying so, its branch is deleted,
the new candidate commit is pushed as a new branch and a fresh PR is opened.
Nothing is force-pushed, so there is nothing to close by hand first. A retry
converges from wherever the last attempt stopped (a PR already closed, a
branch already gone, a branch pushed with no PR yet), and a concurrent run
that pushed the branch or opened the PR first is kept rather than replaced:
the result is always one branch and one open PR. The branch is deleted on
merge only by the repository's "Automatically delete head branches" setting;
without it, a merged candidate's branch stays, unused.

**Two runs of the same stage overlap.** They queue, never cancel. The
candidate's `propose` and `cut` carry job-level concurrency groups (job-level,
because that workflow also starts on every push to the default branch, and a
workflow-wide group would let such a run evict a queued release run), the
candidate refresh runs one per PR, the settle refresh and publish one per
release branch, and `on-release` one per tag.

**The tag already exists** when settling: the refresh refuses to touch it.
If its GitHub Release exists too, pick the next version and start from the
candidate. If not, recover the interrupted publication as below.

**A publish died between the tag and the Release.** The half-published state
(tag at the candidate merge, no Release) is `resume`: re-run the failed run,
or dispatch `release-settle.yml` with the version. For a tag created by
merging a settle PR, re-run the original push-triggered run at that merge:
a versioned dispatch refuses a tag not at the candidate merge. The appropriate
path skips the tag step and creates the missing Release.

**A publish target failed after the tag was created**: fix the cause on
the default branch. If the fix is in the shared action, dispatch
`on-release.yml` again on the tag (`--ref vX.Y.Z -f dry_run=false`); all
registry and crate targets skip identical or already-published versions,
while Release assets are uploaded again with `--clobber`. If the fix is
in the workflow file itself, it cannot reach that tag's tree; the next
release carries it.

**The PR reviewer fails on a PR that edits `claude.yml`**: by design of
`anthropics/claude-code-action`, which refuses to run from a PR whose
workflow file differs from the default branch's. It is not a required check;
merge, and the reviewer works again from the merged file.

**The app cannot push, tag, or read the credentials**: check, in this order,
that the app is installed on the repository, that the organization variable
and secret are available to it (the branch jobs have no environment to fall back on), and
that the app is a bypass actor on the `v*` tag ruleset.

## Reference

What each action does, in one line:

| Action | Trigger in the consumer | Does |
|---|---|---|
| `release-route` | a push or dispatch of the candidate or settle workflow | classifies it as `cut`, `refresh`, `publish` or `skip` with a one-line reason; read-only, uses the job token; computes the settlement state for a versioned settle dispatch |
| `release-candidate` `stage: propose` | `workflow_dispatch` on the default branch | bumps `version_file`, runs `bump_command`, drafts this release's undated changelog entry under `## vX.Y.Z`, syncs the previous release's entry from its tag, opens `chore/release-candidate-X.Y.Z`; with `base_commit`, cuts `release-vX.Y.Z` at that commit first, carries the release workflows onto it and aims the PR there |
| `release-candidate` `stage: refresh` | a push to the default branch while a trunk candidate is open | merges the candidate PR's own base into its head (never a rebase) and re-drafts the entry, committing only when it changed |
| `release-candidate` `stage: cut` | the candidate PR merging | re-reads the PR through the API, refuses anything but a merged app-authored candidate into the default branch, creates `release-vX.Y.Z` at the merge commit |
| `release-settle` | `route` answering `refresh` | verifies the commit is the release branch's tip and carries the version, computes the settlement state, and on `needs-settle-pr` regenerates the notes and opens or refreshes `chore/release-settle-vX.Y.Z` without rewriting its history |
| `release-publish` | `route` answering `publish` (settle PR merged, or clean dispatch) | re-verifies the PR through the API, creates the annotated tag `vX.Y.Z` at the commit once, publishes the GitHub Release with the changelog section as notes, latest only when newer than the current latest |
| `release-snapshot` `stage: resolve` | `workflow_dispatch` of `snapshot-publish.yml` | resolves `ref` (or the run's commit) to a full SHA, refuses it unless reachable from `allowed_branches`, outputs the registry `version` (the commit) and `path` (`<profile>/<label>`) |
| `release-snapshot` `stage: summary` | after the uploads in the same job | run summary with every upload, its checksum and the manifest entry to pin; optional `snapshot/<package>` commit statuses |

Release notes are generated from commit subjects between the previous `v*`
tag and the settled commit, grouped by Conventional Commit type (breaking
changes first), with PR links from `(#N)` suffixes; `chore(release):`
commits are left out. The text logic (`normalize`, `is-greater`,
`latest-tag`, `check-order`, `settle-state`, `route`, `read-file`,
`bump-file`, `notes`, `changelog-insert`, `changelog-extract`,
`changelog-copy`) lives in `release-tools/release_tools.py`, the crate
helpers in `crates_tools.py`; both are unit tested by `actions-test.yml`
(the settlement states by `test_settle_state.py`), which also lints the
templates with `app_token_lint.py`, scans every shipped action and template
for forced pushes (`test_no_force_push.py`), and drives
`release-verify-version` end to end with fake binaries. Consumers track the
actions at `@main`: a merge here reaches every repository at once, and that
workflow is the gate.

Requirements on the consumer's side, in one list: the app installed; the
organization variable `MEGA_GUTENBERG_CLIENT_ID` and secret
`MEGA_GUTENBERG_PK` with access granted to the repository; the two rulesets, with the app as bypass actor on
the tag ruleset only; the `release` environment with its reviewers and
deployment policies; `gh` and `python3` on the runner (any GitHub-hosted
image); `release-candidate.yml` and `release-settle.yml` with the same
`version_file`/`version_pattern`/`changelog_file` in each; a `CHANGELOG.md`.
