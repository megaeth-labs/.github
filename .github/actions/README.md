# Claude CI Composite Actions

Reusable Tier-1 Claude CI actions for MegaETH repositories.

> **Home:** these actions live in `megaeth-labs/.github`. They were migrated here
> from `megaeth-labs/documentation`; reference them at
> `megaeth-labs/.github/.github/actions/claude-<name>`.

## Actions

- `.github/actions/claude-interactive` - interactive `@claude` handling.
- `.github/actions/claude-pr-review` - pull request review.
- `.github/actions/claude-label-check` - pull request label validation.
- `.github/actions/claude-issue-triage` - newly opened issue triage.

- `.github/actions/pr-lint` - lint the PR (currently: PR title against Conventional Commits, with a sticky comment on failure).

### pr-lint

Run it as a step inside a job the consumer owns and names. The status-check
context is that job's name, so a repo whose branch ruleset requires an exact
check name (e.g. mega-reth requires `Validate PR title is Conventional Commit`)
just names the job accordingly:

```yaml
name: PR Lint
on:
  pull_request:
    types: [opened, reopened, edited, synchronize]
  merge_group:
jobs:
  conventional-title:
    name: Validate PR title is Conventional Commit
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write
    steps:
      - uses: megaeth-labs/.github/.github/actions/pr-lint@main
```

`types` (newline-separated allowed Conventional Commit types) can be overridden;
it defaults to the org convention.

## Inputs

All actions accept:

- `claude_code_oauth_token` - required. Pass `${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}`.
- `allowed_bots` - optional, defaults to `mega-putin`.
- `extra_allowed_tools` - optional, appended to the canonical `--allowedTools` list. Rust repos can pass `Bash(cargo:*)` here.

Prompt-bearing actions (`pr-review`, `label-check`, and `issue-triage`) also accept:

- `extra_prompt` - optional, appended after a blank line for per-repo prompt deltas.

The `interactive` action does not accept `extra_prompt` because `@claude` is native.

The `pr-review` action additionally accepts:

- `github_identity_token` - optional, defaults to empty.
  When supplied, this token is the single identity for creating reviews,
  posting or updating status comments, and resolving addressed automated
  review threads.
  When omitted, publication uses the job token and leaves GitHub thread state
  unchanged.
- `model` - optional, defaults to `claude-opus-4-7`.
  This strong model handles initial, high-risk, and explicitly deep reviews.
- `incremental_model` - optional, defaults to empty, which uses the Claude Code default
  (Sonnet class).
  It handles low-risk incremental reviews.
- `review_depth` - optional, defaults to `standard`.
  Set it to `deep` to make the semantic-analysis stage fan out relevant review dimensions
  and adversarially verify the candidates before returning one structured result.
- `max_turns` - optional, defaults to empty.
  Overrides the per-invocation turn budget (`--max-turns`) that is otherwise derived from the
  model tier and review depth. Set a positive integer to pin the main analysis ceiling; the
  retry keeps its 1.5x headroom relative to it. A non-integer or non-positive value fails the run.
- `premortem` - optional, defaults to `auto`.
  Automatic mode runs the independent production-failure analysis for initial and high-risk
  reviews, but skips it for ordinary incremental updates.
  `on` always enables it and `off` disables it.
- `state_artifact` - optional, defaults to `true`.
  Uploads the run's `.pr-review` state directory as an artifact. Set it to `false` only if the
  repository forbids artifacts.
- `state_artifact_retention_days` - optional, defaults to `14`.
- `debug_logs` - deprecated and ignored. The analysis session's full output is now always
  printed. Consumers still passing it are unaffected; drop it at your convenience.


The semantic-analysis stage runs under a turn budget: 12 for a low-risk incremental review,
44 for a strong-tier one, and 56 for `deep`. Set `max_turns` to override any of these.
Roughly ten turns go on mandated context — six pipeline files plus repo guidance — before the
diff is read, and a small diff inside a large file spends many more paging through it, so the
budget tracks files to understand rather than lines changed.
The retry gets half again as many turns as the first attempt, because exhausting the budget is
deterministic and replaying it with the same budget cannot succeed.

Consumers that already create a GitHub App token can opt into the unified identity with:

```yaml
with:
  github_identity_token: ${{ steps.app-token.outputs.token }}
```

The semantic stage is bounded to 12 turns for fast incremental reviews, 44 for standard
full or high-risk reviews, and 56 for explicit deep reviews, unless `max_turns` overrides it.

### PR review pipeline

The PR reviewer is an explicit staged pipeline:

1. A deterministic preparation step freezes the base and head SHAs, loads the durable review
   manifest, fetches prior automated threads, computes the full or incremental diff, and
   selects the model tier. It then posts or updates the sticky status comment to
   `🔄 Review in progress`, so the PR shows the round has started instead of staying silent
   until the review lands minutes later.
2. Claude performs semantic analysis and verification with read-only tools.
   It returns schema-constrained data and cannot publish comments or resolve threads.
3. A deterministic compiler validates findings, enforces severity budgets, checks RIGHT-side
   anchors, formats the standard human-facing messages, and suppresses internal review
   machinery.
4. A deterministic publisher rechecks the live head, submits at most one review, optionally
   resolves addressed automated threads, and updates one sticky status comment.

The sticky comment contains a hidden, versioned manifest with the last published head,
reviewer and rubric versions, stable finding IDs, thread IDs, and finding dispositions.
Later runs use that manifest as a checkpoint and fall back to GitHub review history if the
manifest is unavailable.
The manifest never contains complete diffs, PR prose, tool output, secrets, or Claude session
transcripts.
Inline findings are linked back to the exact published review and comment IDs, with bounded
retries for GitHub API propagation.
When `github_identity_token` is configured, the publisher does not mark a GitHub thread
resolved unless GitHub confirms the resolution mutation.
The configured identity is stored in the review manifest while historical `claude` and
`github-actions` state remains readable for migration.

The action performs a full review when there is no valid checkpoint, the previous head is not
an ancestor, or the pipeline or rubric version changed.
Otherwise it reviews only the delta since the last published head and rechecks open findings.
It discards output if the PR head changes during analysis.

Internal production-failure analysis is never named in GitHub review output.
Confirmed issues become ordinary findings.
Useful uncertainty becomes an `Open question` with medium or low confidence and a concrete
verification request.
Rejected candidates and an empty internal analysis remain invisible.

Open questions have the same durable lifecycle as findings.
Each one gets a stable ID and a hidden marker on its status line, and the manifest records
which review asked it.
Each question is published inside a `<details>` block that starts expanded.
A later round dispositions every open question as `open`, `answered`, or `withdrawn`, and the
publisher edits the original review body in place so the summary line reads
`✅ **Answered**` or `🚫 **Withdrawn**` with a one-line reason, and the block collapses.
The rationale bullets are kept rather than deleted, so an answered question stays one green
line that expands to the original question, why it mattered, and how to verify it.
Editing a submitted review body creates no new review and no new notification, and rewriting
reproduces the same header (marker included), so the update is idempotent and retried on the
next round if GitHub rejects it.
Questions published before the `<details>` shape existed fall back to a single-line rewrite.
A question that is already open is never re-asked; the original stays the copy the author
answers.

### Inspecting a review run

The published review says what the reviewer concluded. These say how it got there, and they
are the starting point for tuning the rubric, the prompt, or the turn budget.

**Step summary** (the run's front page) carries the routing decision and its reason, the head
range, the model and turn budget the analysis actually ran with, the model tier, high-risk and
pre-mortem flags, and this round's counts — new findings split into inline and review-body,
new questions, prior findings resolved. It then folds in two blocks: the **pipeline trace** and
the **raw model output before compilation**. A failed run gets the same trace, which shows how
far the round got before it stopped.

**Job log** groups, in step order:

- `Review routing` (prepare) — mode and why, prior state source and whether its version still
  matches, previous and current head, the compare status and file count, both diff sizes, how
  much of the PR conversation was included versus truncated, the paths in scope, and every open
  prior finding and question the model was handed.
- `Analysis settings` (compose) — model, tier, depth, pre-mortem, turn budgets, allowed tools.
- The analysis step itself prints the session's full output, always: every tool call, which
  files it opened, and which it never read. The step is collapsed until you expand it.
- `Model output (raw, before compilation)` and `Compilation decisions` (compile) — one line per
  model result the compiler accepted, suppressed as a duplicate of an open finding, dropped at
  the per-severity cap of five, or rerouted to the review body because its line is not
  commentable, plus each prior finding and question disposition.
- `Publication` (publish) — review ID, inline comments requested versus posted, whether inline
  publication fell back to the review body, threads resolved, and the sticky comment ID.

**Run artifact** `pr-review-state-<pr>-<run>-<attempt>` holds the bytes themselves, for 14 days
by default: `review-input.json` (everything the model was given), `review.diff` and `full.diff`,
`analysis-transcript.json` (the session's turn-by-turn record, plus a `-retry-` twin when the
retry ran), `structured-output.json`, `model-output.json`, `review-payload.json` (the compiled
review, including its decision trace), `publish-result.json`, and `trace.log`.

"The model missed it" and "the pipeline dropped it" look identical in the published review and
different in these. Compare `model-output.json` against the `Compilation decisions` group first.

### Comment-triggered reconciliation (opt-in)


By default the review only runs on `pull_request` events, so an author who answers an open
question in a PR comment sees nothing happen until the next push. A consumer can also let a
comment drive a reconcile round by adding an `issue_comment` trigger:

```yaml
on:
  pull_request:
    types: [opened, synchronize, ready_for_review, reopened]
  issue_comment:
    types: [created]

jobs:
  pr-review:
    # Any PR comment except the reviewer's own status comment, which is posted
    # by the CI app and would otherwise retrigger the review. Other bots are
    # allowed — their comments may answer a question or push back on a finding.
    # Replace mega-maxwell[bot] with your reviewer app's login.
    if: >-
      github.event_name != 'issue_comment' ||
      (github.event.issue.pull_request != null &&
       github.event.comment.user.login != 'mega-maxwell[bot]')
    concurrency:
      # issue_comment payloads carry issue.number, not pull_request.number.
      group: claude-pr-review-${{ github.event.pull_request.number || github.event.issue.number }}
      cancel-in-progress: false
```

The action gates the round cheaply so routine chatter does not spend a review: on an
`issue_comment` event, `prepare` skips unless the PR still has an **open question or open
finding** in the manifest (something a comment could answer, justify, or invalidate). When it
does run it is an incremental round that reuses the same sticky-comment manifest — so the
reviewer keeps its full prior context, unlike a fresh `@claude` session — and it runs on the
cheaper incremental model tier. If the comment turns out not to change anything, the publisher
posts nothing (no new review, no notification). A comment with no new commit reconciles the
discussion against the existing head; a comment that races a push reviews the new delta too.

## Per-Repo Conventions

The prompt-bearing actions instruct Claude to read and respect a consumer repo's own agent
instruction files when they exist (`REVIEW.md`, `README.md`, `CLAUDE.md`, `AGENTS.md`, and any
other repo-level agent guidance), with those per-repo rules taking precedence over the
canonical inline prompt. Use these files for repo-specific rules; reserve `extra_prompt` for
small deltas that do not belong in a checked-in convention file.

`pr-review` tags every inline finding with a bold severity label (`**[Critical]**`,
`**[Major]**`, `**[Minor]**`, or `**[Nit]**`).
Clean reviews and re-reviews update the sticky status without creating another review
notification.
Rounds with findings or new open questions submit one atomic review and update the same sticky
status.
The sticky status comment states up front that it is a living comment rewritten in place on
every run, so a reader who meets it mid-thread can tell it describes the current head rather
than the moment it first appeared.
It carries the reviewed range, an update timestamp, this round's counts, and a roll-up of the
questions still awaiting an answer with a link to the review that asked each one.
It moves through three phases: `🔄 Review in progress` from preparation, then either the
finished verdict or `🛠️ Review did not finish` for a round that ends without publishing.
Every non-publishing path — a failure, a discarded stale head — retires the in-progress phase
itself, so the comment never sits at "in progress" after the job ends. A skip-mode round
publishes nothing and is never announced.
When old automated review threads are addressed, the deterministic publisher resolves them
without adding confirmation replies.
A consumer repo's `REVIEW.md` may override or extend the semantic severity guidance.

## Consumer Requirements

Consumer jobs should pin these actions to `@main`. A merge to this repository's `main` goes live
for every consumer automatically, with no consumer workflow edits required.
Use `megaeth-labs/.github/.github/actions/claude-interactive@main`,
`megaeth-labs/.github/.github/actions/claude-pr-review@main`,
`megaeth-labs/.github/.github/actions/claude-label-check@main`, or
`megaeth-labs/.github/.github/actions/claude-issue-triage@main`.

Because the same merge ships to every consumer at once, changes here are covered by the
`Actions` workflow, which runs the `claude-pr-review` pipeline's unit tests on every PR.

Consumer jobs must run `actions/checkout` before these actions. They must also provide the
`CLAUDE_CODE_OAUTH_TOKEN` secret and set role-appropriate job permissions:

- `claude-interactive`: `contents: write`, `pull-requests: write`, `issues: write`, `id-token: write`, `actions: read`
- `claude-pr-review`: `contents: read`, `pull-requests: write`, `id-token: write`, `actions: read`
- `claude-label-check`: `contents: read`, `pull-requests: write`, `id-token: write`
- `claude-issue-triage`: `contents: read`, `issues: write`, `id-token: write`

Before consumer repositories can reference these private actions, maintainers must enable
Settings -> Actions -> General -> Access -> "Accessible from repositories in the megaeth-labs organization".

## Example

```yaml
jobs:
  pr-review:
    runs-on: ubuntu-24.04
    permissions:
      contents: read
      pull-requests: write
      id-token: write
      actions: read
    steps:
      - uses: actions/checkout@v4
        with:
          submodules: recursive
          fetch-depth: 1

      - uses: megaeth-labs/.github/.github/actions/claude-pr-review@main
        with:
          claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
          extra_allowed_tools: "Bash(cargo:*)"
          extra_prompt: |
            Add repository-specific review instructions here.
```

> Note: a PR that _modifies the calling repo's own_ `claude.yml` skips the `pr-review`
> job.
> `claude-code-action` validates that workflow against the default branch before it exchanges
> its app token, so self-modifying PRs cannot run the review step safely.
> This only affects the repo that changed its own workflow.
> It does not affect consumers pinned to `@main` in normal operation.

## Concurrency (pr-review)

Consumers should give the `pr-review` job a `timeout-minutes` value of at least `25` plus a
job-level concurrency group with `cancel-in-progress: true`.
The publisher revalidates the live PR base and head immediately before each GitHub mutation,
and review submissions are pinned to the frozen head commit. If either revision changes,
publication stops without advancing the manifest.
Latest-only cancellation avoids spending review time on queued, obsolete heads:

```yaml
pr-review:
  timeout-minutes: 25
  concurrency:
    group: claude-pr-review-${{ github.event.pull_request.number }}
    cancel-in-progress: true
```

## Release actions

Three composite actions implement the org release flow — trunk-first
candidate, settle-by-PR, publish-once. They are language-agnostic: the only
repo-specific inputs are where the version lives (`version_file` +
`version_pattern`: `plain`, `toml`, `json`) and the changelog path. Builds and
artifact uploads are not part of them; a repo that ships binaries adds its
own `push: tags` workflow, which the tag created by `release-publish` fires.

| Action | Trigger in the consumer | Does |
|---|---|---|
| `release-candidate` `stage: propose` | `workflow_dispatch` on the default branch | bumps `version_file`, opens `chore/release-candidate-vX.Y.Z` PR |
| `release-candidate` `stage: cut` | that PR merging | creates `release-vX.Y.Z` at the merge commit |
| `release-settle` | `workflow_dispatch` with version + tip SHA | guards, generates notes since the previous tag, writes `CHANGELOG.md`, opens `chore/release-settle-vX.Y.Z` PR onto the release branch |
| `release-publish` | the settle PR merging | annotated tag at the merge commit (refuses if it exists), GitHub Release, back-merge PR of the changelog |

`workflow-templates/release-*.yml` are the reference callers; they show up
under "New workflow → By megaeth-labs" in every org repo. Pin the actions to
a SHA once you rely on them.

Requirements in the consumer repo:

- Org variable `CI_APP_ID` / secret `CI_APP_PK` (the Maxwell app). PRs
  and tag pushes must come from an App token: `GITHUB_TOKEN` does not trigger
  downstream workflows.
- An environment `release` with required reviewers on the publish job — this
  is the human gate for creating a tag.
- A tag ruleset for `v*` (no creation/deletion/force-push) with the app as a
  bypass actor, so `release-publish` is the only tag creator.
- A branch ruleset for `release-*` requiring PRs and up-to-date branches, so
  a settle PR goes stale if the candidate drifts after it was opened.
- `gh` and `python3` on the runner (any GitHub-hosted image).

Release notes are generated from commit subjects between the previous `v*`
tag and the settled commit, grouped by Conventional Commit type with PR links
from `(#N)` suffixes. The pure text logic lives in
`release-tools/release_tools.py` and is unit-tested by `actions-test.yml`.
