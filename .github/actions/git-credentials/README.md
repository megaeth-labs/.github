# Git Credentials

`uses: megaeth-labs/.github/.github/actions/git-credentials@main`

<!-- generated: description -->
Let git — and so cargo, go, pip and anything else that shells out to git — fetch private repositories over HTTPS without prompting, by adding a global `url.<https-with-token>.insteadOf <https>` rewrite for one host. The token never appears in the script: it is passed through the environment and masked in the log. Any token works: a GitHub App installation token (the recommended kind — mint one with `actions/create-github-app-token` for the repositories the build needs), a fine-grained or classic PAT. Optional extras cover the two things the old per-repository copies also did — mark every directory safe for container runners whose workspace belongs to another user, and disable git's low-speed abort for slow mirrors — plus an SSH rewrite for lockfiles that pin `git@host:` URLs. `mode: unset` removes the rewrite again. Nothing is organisation-specific; the host is an input.
<!-- /generated -->

Standalone action; no family guide.

## Inputs

<!-- generated: inputs -->
| Input | Required | Default | Description |
|---|---|---|---|
| `token` | no |  | The token to embed in the rewritten URL. Required unless `mode` is `unset`. |
| `host` | no | `github.com` | Git host to rewrite, without scheme. |
| `username` | no | `x-access-token` | Username part of the rewritten URL. `x-access-token` is what GitHub expects for App installation tokens and also accepts for PATs. |
| `mode` | no | `set` | `set` adds the rewrite, `unset` removes it (and the SSH rewrite, if any). |
| `rewrite_ssh` | no | `false` | `true`: also rewrite `ssh://git@<host>/` and `git@<host>:` to the token URL, for lockfiles or manifests that pin SSH remotes. |
| `safe_directory` | no | `false` | `true`: `git config --global --add safe.directory '*'`, needed on container runners whose workspace is owned by a different user than the one running git. |
| `disable_low_speed_abort` | no | `false` | `true`: set `http.lowSpeedLimit 0` and `http.lowSpeedTime 999999` so git never aborts a slow fetch. The old per-repository copies did this. |
| `show_config` | no | `false` | `true`: print `git config --global --list` afterwards (the token is masked). |
<!-- /generated -->

## Outputs

<!-- generated: outputs -->
| Output | Description |
|---|---|
| `rewrite` | The `url.<…>.insteadOf` key that was set or unset, token elided. |
<!-- /generated -->

## What it runs

<!-- generated: steps -->
1. Configure git
<!-- /generated -->

## Errors it reports

<!-- generated: errors -->
- `mode must be`
- `host must be a bare host name, got`
- `username must be a plain word, got`
- `token is required when mode is`
- `token contains characters that cannot go in a URL`
<!-- /generated -->

## Example

Mint an App installation token for the private repositories the build pulls,
then let git use it. Cargo, go and pip all go through git for
`https://github.com/…` sources:

```yaml
- uses: actions/create-github-app-token@v3
  id: app-token
  with:
    client-id: ${{ vars.MEGA_MAXWELL_CLIENT_ID }}
    private-key: ${{ secrets.MEGA_MAXWELL_PK }}
    owner: megaeth-labs
    repositories: private-dep-a,private-dep-b      # what the build fetches

- uses: megaeth-labs/.github/.github/actions/git-credentials@main
  with:
    token: ${{ steps.app-token.outputs.token }}

- run: cargo build --release
```

A PAT works the same way (`token: ${{ secrets.SOME_PAT }}`). On a container
runner whose workspace is owned by another user add `safe_directory: "true"`;
for lockfiles that pin `git@github.com:` remotes add `rewrite_ssh: "true"`;
to take the rewrite out again before a step that must not see it,
`mode: unset`.

## Notes

- The rewrite lives in the runner's global git config for the rest of the
  job. Ephemeral runners discard it; on a long-lived self-hosted runner use
  `mode: unset` at the end of the job, or the next job inherits it.
- Running it twice replaces the token, it never stacks two rewrites for the
  same host. Only one token per host at a time.
- App installation tokens expire after one hour. A job that fetches late in
  a long build needs the token minted just before the fetch.
- The `x-access-token` username is what GitHub expects for App tokens and
  also accepts for PATs; the old per-repository copies embedded the PAT as
  the username instead, which works for PATs only.
- The old copies also set `credential.helper store`; the URL rewrite makes
  it redundant and it is not set here.
