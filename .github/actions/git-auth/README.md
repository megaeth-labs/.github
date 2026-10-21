# Git Auth

Use this action for trusted commands that fetch private GitHub dependencies or
push a branch/tag. Pass a short-lived, explicitly scoped App token when possible.
Use `actions/checkout` with `persist-credentials: false` before this action.

```yaml
- uses: megaeth-labs/.github/.github/actions/git-auth@main
  with:
    token: ${{ steps.app-token.outputs.token }}
    command: cargo fetch --locked
```

The askpass script contains no token. Only the command process tree receives the
token; no credential file, remote URL rewrite, or job-wide environment export is
created. It answers HTTPS prompts for github.com only. It does not authenticate
SSH URLs, GitHub Enterprise hosts, or commands inside Docker containers. Mount a
BuildKit secret when a Docker build needs its own Git access.

Runner-level Git config is ignored; credential helpers and GitHub HTTP auth
headers are disabled in process-local config. This intentionally excludes global
URL rewrites and proxy/CA settings: supply required proxy/CA settings through the
command environment or repository config. Repository config must be trusted.
Commands and child processes can read the token; this is not an isolation boundary.
`cargo fetch --locked` followed by an offline build reduces credential exposure.

<!-- generated: description -->
Run a command with GitHub HTTPS authentication through GIT_ASKPASS. The token is passed only through the command environment, never a Git URL or config file. Supports GitHub App installation tokens and PATs. Commands must be trusted: their child processes can read the token. Runner-level Git configuration is ignored and credential helpers are disabled for this command.
<!-- /generated -->
<!-- generated: inputs -->
| Input | Required | Default | Description |
|---|---|---|---|
| `token` | yes |  | GitHub token, scoped to the repositories and permissions the command needs. |
| `command` | yes |  | Trusted shell commands to execute with GitHub HTTPS authentication. |
| `working-directory` | no | `.` | Directory in which the command runs. |
<!-- /generated -->
<!-- generated: outputs -->
| Output | Description |
|---|---|
| `wrapper` | Path to the credential-free command wrapper in this pinned action version. |
| `askpass` | Path to the credential-free Git askpass program. |
<!-- /generated -->
<!-- generated: steps -->
1. Run with GitHub auth
<!-- /generated -->
<!-- generated: errors -->
Its shell steps report no errors of their own; failures come from the actions and tools it calls.
<!-- /generated -->
