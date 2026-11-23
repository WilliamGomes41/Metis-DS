---
name: summarize-pr
description: Create a validated local HTML overview when asked to review or summarize a GitHub pull request for Metis-DS.
---

# Summarize a GitHub pull request

The [PR-REVIEW fork](https://github.com/WilliamGomes41/PR-REVIEW) supplies the instructions, template and scripts. Use all three from commit `55b29eef96f2797acd179b75dfe937806dc25494`. Prepare a temporary checkout when the user requests a GitHub pull request review or overview. No global skill installation is required.

```sh
skill_checkout=$(mktemp -d)
git -C "$skill_checkout" init -q &&
  git -C "$skill_checkout" fetch --no-tags --depth=1 https://github.com/WilliamGomes41/PR-REVIEW.git 55b29eef96f2797acd179b75dfe937806dc25494 &&
  git -C "$skill_checkout" checkout -q --detach FETCH_HEAD
```

Read `skills/summarize-pr/SKILL.md` in that checkout and use the template and checker from the same directory. This pin replaces the upstream global update check. To update it, sync the fork, review the upstream changes and replace the pinned commit through the normal Metis change process.

Use the gather script when authenticated `gh` and its dependencies are available. Otherwise use the GitHub connector to read the PR description, diff, changed files, review threads and head commit. If Git fetch is unavailable, use the connector to read the pinned skill and retrieve its template and checker from the same commit. State any remaining tool or evidence gap and continue with the available review evidence.

Validate the generated overview with `node scripts/check.mjs <overview.html>` from the fetched skill directory. Save it locally, outside the tracked files. For a review, also perform the requested code review and return its findings. Include the overview link unless the user requests a findings-only response. Publishing the overview, editing the PR, replying to comments and monitoring the PR require a separate request.
