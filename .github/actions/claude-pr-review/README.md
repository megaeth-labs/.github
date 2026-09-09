# Claude PR Review

`uses: megaeth-labs/.github/.github/actions/claude-pr-review@main`

<!-- generated: description -->
Run the staged, incremental MegaETH Claude pull request review.
<!-- /generated -->

Family: [Claude CI](../CLAUDE-CI.md).

## Inputs

<!-- generated: inputs -->
| Input | Required | Default | Description |
|---|---|---|---|
| `claude_code_oauth_token` | yes |  | OAuth token for Claude Code. |
| `github_identity_token` | no |  | Optional GitHub token used for review publication and state updates. When supplied, it is also used to resolve addressed automated review threads. Empty uses the job token and skips thread resolution. |
| `allowed_bots` | no | `mega-putin` | Bot accounts allowed to trigger Claude Code. |
| `extra_allowed_tools` | no |  | Additional read-only tools to append to the canonical allowedTools list. |
| `extra_prompt` | no |  | Additional analysis instructions appended after the canonical prompt. |
| `model` | no | `claude-opus-4-7` | Model used for full, high-risk, and deep reviews. |
| `incremental_model` | no |  | Model used for low-risk incremental reviews. Empty uses the Claude Code default (Sonnet class). |
| `review_depth` | no | `standard` | `standard` runs one lead review. `deep` asks the lead to fan out review dimensions and adversarially verify them before returning structured data. |
| `max_turns` | no |  | Optional override for the per-invocation turn budget (`--max-turns`). Empty (default) uses the built-in budget derived from model tier and review depth (fast 12, standard 44, deep 56). Set a positive integer to pin the ceiling for the main analysis pass; the retry pass keeps its 1.5x headroom relative to this value. |
| `debug_logs` | no | `false` | Deprecated and ignored. The analysis session's full output — its tool calls, the files it opened, and the ones it never read — is now always printed, and the whole `.pr-review` state directory plus the session transcript are uploaded as a run artifact. Kept only so consumers that still pass it do not break. |
| `state_artifact` | no | `true` | `true` uploads the `.pr-review` state directory — routing input, both diffs, the raw model output, the compiled payload, the pipeline trace, and the analysis session transcript — as a run artifact. This is the only copy that outlives the runner, so leave it on unless the repository forbids artifacts. |
| `state_artifact_retention_days` | no | `14` | Retention in days for the review state artifact. |
| `premortem` | no | `auto` | `auto` runs the internal pre-mortem only for full or high-risk reviews. `on` always runs it; `off` disables it. Pre-mortem provenance never appears in the published review. |
<!-- /generated -->

## Outputs

<!-- generated: outputs -->
| Output | Description |
|---|---|
| `mode` | Review mode (`full`, `incremental`, or `skip`). |
| `reviewed_head` | Frozen PR head reviewed by this run. |
| `verdict` | Compiled verdict (`clean`, `findings`, or `questions`). |
| `published` | Whether output was published for the frozen head. |
<!-- /generated -->

## What it runs

<!-- generated: steps -->
1. Prepare immutable review context
1. Compose bounded LLM analysis
1. Analyze and verify findings — `anthropics/claude-code-action` *(only if `steps.prepare.outputs.mode != 'skip'`)*
1. Retry missing structured review output — `anthropics/claude-code-action` *(only if `steps.prepare.outputs.mode != 'skip' && (steps.review.outcome == 'failure' || steps.review.outputs.structured_output == '')`)*
1. Capture analysis session transcript *(only if `always()`)*
1. Compile and validate review
1. Publish atomically and persist state
1. Report concise review outcome *(only if `always()`)*
1. Upload review state for inspection — `actions/upload-artifact` *(only if `always() && inputs.state_artifact == 'true'`)*
<!-- /generated -->

## Errors it reports

<!-- generated: errors -->
- `max_turns must be a positive integer, got`
<!-- /generated -->

## Example

```yaml
jobs:
  pr-review:
    runs-on: ubuntu-24.04
    timeout-minutes: 25
    concurrency:
      group: claude-pr-review-${{ github.event.pull_request.number }}
      cancel-in-progress: true
    permissions:
      contents: read
      pull-requests: write
      id-token: write
      actions: read
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 1

      - uses: megaeth-labs/.github/.github/actions/claude-pr-review@main
        with:
          claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
          github_identity_token: ${{ steps.app-token.outputs.token }}   # optional: one identity for reviews, comments, thread resolution
          extra_allowed_tools: "Bash(cargo:*)"
```

## Notes

- How a round runs, the manifest, the questions lifecycle, the comment-
  triggered reconciliation and how to inspect a run: [CLAUDE-CI.md](../CLAUDE-CI.md).
- PRs opened by the identity behind `github_identity_token` (release
  candidates, settle PRs, dependency bumps) are skipped before any model
  step.
- A PR that edits the calling repository's own `claude.yml` skips the review
  by design of `claude-code-action`; it works again once the change merges.
- Turn budgets: 12 for a low-risk incremental round, 44 for a strong-tier
  one, 56 for `deep`; `max_turns` overrides, and the retry gets half again
  as many.
