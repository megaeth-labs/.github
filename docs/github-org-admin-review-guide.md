# MegaETH GitHub Organization Admin — Request Review Guide

An Org Owner or designated organization administrator makes the decision and records the result. Team Leaders and Solo stewards provide context; they are not additional approvers under this guide. Repository-level Secrets and Variables are owned by Team Leaders and are out of scope.

| If the request is about… | Go to |
| --- | --- |
| Unclear ownership, a direct repository grant, or an outside collaborator | [Ownership and unusual access](#ownership-and-unusual-access) |
| Getting past a branch rule for one operation | [Temporary branch-rule bypass](#temporary-branch-rule-bypass) |
| Changing a branch rule or `review_policy` | [Changing branch policy](#changing-branch-policy) |
| Changing visibility, archiving, deleting, or transferring a repository | [Repository lifecycle](#repository-lifecycle) |

For any request, identify the **repository URL, requesting account, current state, intended change, and reason**. Read live settings before deciding. If the repository, responsible person, or impact is unclear, resolve that first. After a change, read it back and record the decision, result, and any expiry.

## Ownership and unusual access

**General principle.** Each repository has one accountable owner. `ownership=<Team>` identifies the responsible team; its base team has Read, Contributors have Write, and Leaders have Maintain. `ownership=Solo` identifies a Solo repository with a named individual steward and an approved direct grant. Keep the approved CI/CD role in either mode. `ownership` does not itself grant access.

**Review.** For a proposed owner or grant, check the real person behind the GitHub account, the repository's purpose, existing team and direct grants, and the exact access gained or lost. A direct grant to a Solo steward is expected; a direct grant that duplicates Team access needs a reason. For an outside collaborator, check the sponsor, minimum useful role, and end date. Preserve unrelated outside collaborators when fixing access.

**Temporary exception.** Use a named, repository-scoped grant with an expiry when ordinary team membership cannot meet a short-lived need. Record who will remove it. Do not silently turn a Team repository into Solo to accommodate one person.

## Temporary branch-rule bypass

**General principle.** The default branch uses a PR; `review_policy=team` adds one approval and CODEOWNER review, plus an extra approval for unattributed changes. All branches prohibit force pushes. These [three active organization rulesets](https://github.com/organizations/megaeth-labs/settings/rules) are [default-branch-protection](https://github.com/organizations/megaeth-labs/settings/rules/25225321), [default-branch-review](https://github.com/organizations/megaeth-labs/settings/rules/25225323), and [prohibit-force-push](https://github.com/organizations/megaeth-labs/settings/rules/25151780). Repository-level rules may add requirements.

**Review.** Ask for the exact repository, branch, blocked operation, applicable rule, and why the normal PR or repair path cannot work. Identify the commits or PR involved, the actor who will perform the operation, the risk of losing history or review, and how the result will be verified.

**Temporary exception.** Limit the bypass to the specific operation and time window; keep the PR trail where feasible, then remove temporary access and check the resulting branch. Check the live bypass list before deciding who can perform the operation; the review process does not itself change GitHub permissions. [GitHub bypass modes](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository).

## Changing branch policy

**General principle.** `review_policy`, not `ownership`, selects the extra default-branch review rule: `team` requires approval; `solo` still requires a PR but permits self-merge under the other applicable rules. A Team-owned repository can have `review_policy=solo`. Treat a property change as a policy change, not a metadata cleanup. [GitHub property-based ruleset targeting](https://docs.github.com/en/organizations/managing-organization-settings/creating-rulesets-for-repositories-in-your-organization).

**Review.** Compare the current and proposed property or ruleset, affected repositories and branches (including future repositories), bypass actors, and effective rules before and after. Ask why a lasting change is needed and how it will be rolled back if it weakens protection unexpectedly. Only an Org Owner or designated admin decides; a Team Leader can explain the workflow.

**Temporary exception.** If the need is one merge or recovery operation, use the [bypass review above](#temporary-branch-rule-bypass) instead of changing `review_policy` or weakening an organization-wide ruleset. Set a rollback time for any genuinely temporary rule change and verify that the original protection is restored.

## Repository lifecycle

**General principle.** The active [organization repository policy](https://github.com/organizations/megaeth-labs/settings/policies/repositories/25075427) restricts creation, deletion, and transfer to Org admins. Archiving preserves a repository for later inspection; deletion and transfer need a clear disposition of its code and consumers.

**Review.** Confirm the repository ID and owner/steward, branches and unique work, open PRs/issues, downstream consumers, data exposure, and retention needs. For visibility changes, identify who gains access. Check the tracking sheet's proposed action, but decide from current GitHub state and the reviewed request.

**Temporary exception.** For urgent containment with unresolved retention questions, restrict access or archive first and revisit deletion later. Do not treat a temporary bypass as permanent approval to delete or transfer. After execution, verify the result and update **Current Status** from observed state.
