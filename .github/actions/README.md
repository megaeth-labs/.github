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

- `.github/actions/pr-title-lint` - validate the PR title against Conventional Commits (sticky comment on failure).

See also `../workflows/pr-lint.yml` — a reusable workflow (`workflow_call`) that
lints the PR title against Conventional Commits, callable at
`megaeth-labs/.github/.github/workflows/pr-lint.yml`. It simply delegates to the
`pr-title-lint` composite action.

### PR title lint: which form to use

- **Reusable workflow** (`workflows/pr-lint.yml`) — simplest. The consumer adds a
  thin caller with the `pull_request` trigger and one `uses:` job. The resulting
  status-check context is `<caller-job> / Validate PR title is Conventional Commit`.
- **Composite action** (`actions/pr-title-lint`) — use when a **required** status
  check must keep an exact name. The consumer owns the job (and names it), calling
  the action as a single step; the check context is then just the job name. mega-reth
  needs this because its release-branch ruleset requires a check literally named
  `Validate PR title is Conventional Commit`.

  ```yaml
  jobs:
    conventional-title:
      name: Validate PR title is Conventional Commit
      runs-on: ubuntu-latest
      permissions:
        pull-requests: write
      steps:
        - uses: megaeth-labs/.github/.github/actions/pr-title-lint@main
  ```

## Inputs

All actions accept:

- `claude_code_oauth_token` - required. Pass `${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}`.
- `allowed_bots` - optional, defaults to `mega-putin`.
- `extra_allowed_tools` - optional, appended to the canonical `--allowedTools` list. Rust repos can pass `Bash(cargo:*)` here.

Prompt-bearing actions (`pr-review`, `label-check`, and `issue-triage`) also accept:

- `extra_prompt` - optional, appended after a blank line for per-repo prompt deltas.

The `interactive` action does not accept `extra_prompt` because `@claude` is native.

The `pr-review` action additionally accepts:

- `model` - optional, defaults to `opus`. Passed through to `claude --model`. Set another model id to override, or empty to fall through to the Claude Code CLI default (Sonnet class). Note the `opus` default means every consumer runs reviews on Opus out of the box.
- `review_depth` - optional, defaults to `standard` (single-agent review). Set to `deep` for multi-agent orchestration: the lead agent fans out one sub-agent per review dimension, adversarially verifies each finding, then converges on the same single consolidated review. `deep` costs more tokens and wall-clock, so raise the calling job's `timeout-minutes` (see Concurrency) and prefer gating it per-PR (e.g. a label) rather than enabling it for every review.
- `premortem` - optional, defaults to `on`. Adds an independent pre-mortem track to the review: a fresh sub-agent with no shared context assumes the PR already shipped and caused a production incident, reconstructs the most credible failure paths (top 5 candidates), an evidence-verifier sub-agent confirms or rejects each one against the actual code at head, and only `confirmed` findings are published as inline comments (marked `(pre-mortem, confirmed)`). `plausible_unverified` items appear only as non-blocking verification requests in the review body; rejected/stale/out-of-scope candidates are suppressed. The track is non-blocking — the review event is always `COMMENT`, never `REQUEST_CHANGES` — and caps the round at 5 Critical/Major plus 5 Minor/Nit inline comments across both tracks. It adds sub-agent wall-clock, so give the calling job `timeout-minutes` of at least `35`. Set to `off` to disable. The role prompts live in `claude-pr-review/premortem.md`.

## Per-Repo Conventions

The prompt-bearing actions instruct Claude to read and respect a consumer repo's own agent
instruction files when they exist (`REVIEW.md`, `README.md`, `CLAUDE.md`, `AGENTS.md`, and any
other repo-level agent guidance), with those per-repo rules taking precedence over the
canonical inline prompt. Use these files for repo-specific rules; reserve `extra_prompt` for
small deltas that do not belong in a checked-in convention file.

`pr-review` lets Claude iterate through multiple review passes before submission and stop only after it converges on no new actionable findings.
It blocks the standalone inline-comment tool and requires new findings to be submitted through one pending GitHub review that is submitted once, so a completed review round should create one review notification.
When old automated review threads are addressed, the action instructs Claude to resolve them silently instead of adding per-thread confirmation replies.
It also tags every inline comment with a bold severity label (`**[Critical]**`, `**[Major]**`, `**[Minor]**`, `**[Nit]**`).
A consumer repo's `REVIEW.md` may override or extend this severity scale.

## Consumer Requirements

Consumer jobs should pin these actions to a commit SHA (with a `# main` comment), e.g.
`megaeth-labs/.github/.github/actions/claude-interactive@<sha>`. Bumping the pinned SHA after a
merge to `.github` `main` rolls the change out to that consumer.
The available actions are `claude-interactive`, `claude-pr-review`, `claude-label-check`, and
`claude-issue-triage`.

Consumer jobs must run `actions/checkout` before these actions. They must also provide the
`CLAUDE_CODE_OAUTH_TOKEN` secret and set role-appropriate job permissions:

- `claude-interactive`: `contents: write`, `pull-requests: write`, `issues: write`, `id-token: write`, `actions: read`
- `claude-pr-review`: `contents: read`, `pull-requests: write`, `id-token: write`, `actions: read`
- `claude-label-check`: `contents: read`, `pull-requests: write`, `id-token: write`
- `claude-issue-triage`: `contents: read`, `issues: write`, `id-token: write`

Before consumer repositories can reference these actions, an org maintainer must enable
Settings -> Actions -> General -> Access -> "Accessible from repositories in the megaeth-labs organization"
on this (`.github`) repository.

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

      - uses: megaeth-labs/.github/.github/actions/claude-pr-review@<sha> # main
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
> It does not affect consumers pinned to a SHA in normal operation.

## Concurrency (pr-review)

Consumers should give the `pr-review` job a `timeout-minutes` value of at least `25` (`35` when the default-on pre-mortem track is enabled) plus a job-level concurrency group with `cancel-in-progress: false`.
This helps an in-progress multi-turn review finish instead of being cancelled mid-run, because the action resolves addressed automated threads silently and posts one consolidated review per round.
Cancelling can leave partial state:

```yaml
pr-review:
  timeout-minutes: 25
  concurrency:
    group: claude-pr-review-${{ github.event.pull_request.number }}
    cancel-in-progress: false
```
