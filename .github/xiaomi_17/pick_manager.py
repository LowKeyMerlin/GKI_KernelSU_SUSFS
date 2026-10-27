#!/usr/bin/env python3
"""Pick the manager commit for a pinned kernel commit.

Default is the manager built from the kernel commit itself. --max-ahead N allows up to N
later commits but never one past a change under uapi/. If the kernel commit has no
manager build, the nearest build above it (within FALLBACK_WINDOW) is used.
Prints the sha on stdout and the reason on stderr.
"""
import argparse
import json
import subprocess
import sys

MAX_COMMITS = 300  # safety cap on the commit walk
FALLBACK_WINDOW = 5  # how far above K to look when K itself has no manager build


def gh_api(path):
    proc = subprocess.run(
        ["gh", "api", path], capture_output=True, text=True, encoding="utf-8"
    )
    if proc.returncode != 0:
        sys.exit(f"gh api {path} failed: {proc.stderr.strip()}")
    return json.loads(proc.stdout)


def commits_after(repo, kernel_sha, branch):
    """Commits strictly after kernel_sha on branch, oldest first."""
    found, page = [], 1
    while len(found) < MAX_COMMITS:
        data = gh_api(
            f"repos/{repo}/compare/{kernel_sha}...{branch}?per_page=100&page={page}"
        )
        if data.get("status") not in ("ahead", "identical"):
            sys.exit(
                f"kernel commit {kernel_sha[:8]} is not an ancestor of {branch} "
                f"(compare status: {data.get('status')})"
            )
        batch = data.get("commits", [])
        found.extend(c["sha"] for c in batch)
        if len(batch) < 100 or len(found) >= data.get("total_commits", 0):
            break
        page += 1
    return found[:MAX_COMMITS]


def changes_contract(repo, sha, prefix):
    files = gh_api(f"repos/{repo}/commits/{sha}").get("files", [])
    return any(
        f["filename"].startswith(prefix) and (f["additions"] or f["deletions"])
        for f in files
    )


def has_manager_build(repo, workflow, sha):
    runs = gh_api(
        f"repos/{repo}/actions/workflows/{workflow}/runs?head_sha={sha}&status=success"
    )
    return runs.get("total_count", 0) > 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="owner/name, e.g. Baka-SU/BakaSU")
    ap.add_argument("--kernel-sha", required=True)
    ap.add_argument("--workflow", required=True, help="manager CI workflow file")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--contract-prefix", default="uapi/")
    ap.add_argument("--max-ahead", type=int, default=0,
                    help="allow a manager up to N commits after the kernel commit (default 0)")
    a = ap.parse_args()

    window = max(a.max_ahead, 0)
    reach = max(window, FALLBACK_WINDOW)
    candidates = [a.kernel_sha]  # index = commits after K
    for sha in commits_after(a.repo, a.kernel_sha, a.branch)[:reach]:
        if changes_contract(a.repo, sha, a.contract_prefix):
            print(f"stopping before contract change {sha[:8]}", file=sys.stderr)
            break
        candidates.append(sha)

    built = [has_manager_build(a.repo, a.workflow, s) for s in candidates]
    # newest build within --max-ahead
    for i in range(min(window, len(candidates) - 1), -1, -1):
        if built[i]:
            why = "equal to the kernel commit" if i == 0 else f"{i} commit(s) after the kernel commit"
            print(f"manager commit {candidates[i][:8]} ({why})", file=sys.stderr)
            print(candidates[i])
            return 0
    # no build for the kernel commit: nearest one above
    for i in range(1, len(candidates)):
        if built[i]:
            print(f"kernel commit has no manager build; nearest above is {candidates[i][:8]} "
                  f"({i} commit(s) ahead)", file=sys.stderr)
            print(candidates[i])
            return 0
    sys.exit(f"no manager CI build within {reach} commit(s) of {a.kernel_sha[:8]}")


if __name__ == "__main__":
    sys.exit(main())
