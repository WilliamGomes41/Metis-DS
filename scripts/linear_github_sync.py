#!/usr/bin/env python3
"""Repository-owned GitHub facts -> one Linear comment; never issue authority."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

REPOSITORY = "WilliamGomes41/Metis-DS"
REPO_URL = "https://github.com/" + REPOSITORY
TEAM_ID = "2766ee91-9cc4-449b-92db-12ce6593d76a"
MARKER = "<!-- metis-github-linear-sync-v1 -->"
CONFIG = Path(__file__).resolve().parents[1] / "config/linear_github_sync.v1.json"
TRUSTED = {"OWNER", "MEMBER", "COLLABORATOR"}
HANDOFF = re.compile(r"<!--\s*metis-linear-handoff-v1\s*\n(.*?)\n\s*-->", re.S)
PRIMARY = re.compile(r"\bPart of\s+(MET-[1-9][0-9]*)\b", re.I)


class SyncError(Exception):
    """Safe operational error; never includes HTTP response bodies or tokens."""


@dataclass(frozen=True)
class Binding:
    github_issue: int
    linear_issue: str


def load_bindings(path: Path = CONFIG) -> list[Binding]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if (data["version"] != 1 or data["repository"] != REPOSITORY
                or data["team_id"] != TEAM_ID):
            raise SyncError("Configuratie valt buiten repository/team-scope")
        result = [Binding(row["github_issue"], row["linear_issue"]) for row in data["bindings"]]
        if not result or any(type(b.github_issue) is not int or b.github_issue <= 0
                             or not re.fullmatch(r"MET-[1-9][0-9]*", b.linear_issue) for b in result):
            raise SyncError("Ongeldige identiteitskoppeling")
        if (len({b.linear_issue for b in result}) != len(result)
                or len({b.github_issue for b in result}) != len(result)):
            raise SyncError("Dubbele identiteitskoppeling")
        return result
    except (KeyError, TypeError, ValueError, OSError) as exc:
        raise SyncError("Configuratie ontbreekt of is ongeldig") from exc


def read_handoff(body: str, identifier: str) -> dict | None:
    matches = HANDOFF.findall(body)
    if not matches:
        if "metis-linear-handoff-v1" in body:
            raise SyncError("Overdrachtmarker heeft geen geldig JSON-blok")
        return None
    if len(matches) != 1:
        raise SyncError("Meerdere overdrachtblokken")
    try:
        value = json.loads(matches[0])
        if (not isinstance(value, dict) or value.get("version") != 1
                or value.get("linear_issue") != identifier
                or not re.fullmatch(r"[0-9a-f]{40}", value.get("head", ""))
                or type(value.get("remaining_work")) is not bool
                or not isinstance(value.get("next_step"), str)
                or not value["next_step"].strip() or len(value["next_step"]) > 1200
                or not isinstance(value.get("evidence"), list)
                or len(value["evidence"]) > 20):
            raise SyncError("Ongeldige overdrachtvelden of koppeling")
        for url in value["evidence"]:
            if not isinstance(url, str) or not url.startswith(REPO_URL + "/") or len(url) > 1000:
                raise SyncError("Bewijs moet binnen deze GitHub-repository liggen")
        return {k: value[k] for k in ("version", "linear_issue", "head", "remaining_work", "next_step", "evidence")}
    except (TypeError, ValueError) as exc:
        raise SyncError("Overdracht bevat ongeldig JSON/type") from exc


def validate_pr_handoff(body: str, head: str, bindings: list[Binding]) -> None:
    targets = PRIMARY.findall(body)
    if len(targets) != 1 or targets[0] not in {b.linear_issue for b in bindings}:
        raise SyncError("PR vereist precies één geconfigureerde Part of MET-koppeling")
    handoff = read_handoff(body, targets[0])
    if handoff is None or handoff["head"] != head:
        raise SyncError("PR-overdracht ontbreekt of head is achterhaald")


class Api:
    def __init__(self, github_token: str, linear_key: str):
        if not github_token or not linear_key:
            raise SyncError("GITHUB_TOKEN of LINEAR_API_KEY ontbreekt; synchronisatie niet actief")
        self.github_token, self.linear_key = github_token, linear_key

    def github(self, path: str):
        if not path.startswith(f"/repos/{REPOSITORY}/"):
            raise SyncError("GitHub-pad buiten scope")
        return self._request("https://api.github.com" + path,
                             {"Authorization": "Bearer " + self.github_token,
                              "Accept": "application/vnd.github+json"})

    def linear(self, query: str, variables: dict):
        result = self._request("https://api.linear.app/graphql",
                               {"Authorization": self.linear_key}, {"query": query, "variables": variables})
        if not isinstance(result, dict) or result.get("errors") or not isinstance(result.get("data"), dict):
            raise SyncError("Linear GraphQL-fout; geen succesvolle synchronisatie")
        return result["data"]

    @staticmethod
    def _request(url: str, headers: dict, payload: dict | None = None):
        raw = None if payload is None else json.dumps(payload).encode()
        request = urllib.request.Request(url, data=raw, headers={**headers, "Content-Type": "application/json"})
        try:
            # Do not follow a redirect with authorization headers to another host.
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, req, fp, code, msg, response_headers, newurl):
                    return None
            with urllib.request.build_opener(NoRedirect).open(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            raise SyncError(f"API-fout {urllib.parse.urlsplit(url).hostname}: HTTP {exc.code}") from None
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            raise SyncError(f"API niet bereikbaar of ongeldig antwoord: {urllib.parse.urlsplit(url).hostname}") from None


class GitHub:
    def __init__(self, api: Api):
        self.api = api

    def pages(self, path: str) -> list[dict]:
        result = []
        for page in range(1, 1001):
            rows = self.api.github(f"/repos/{REPOSITORY}/{path}&per_page=100&page={page}")
            if not isinstance(rows, list):
                raise SyncError("GitHub-paginering gaf geen lijst")
            result.extend(rows)
            if len(rows) < 100:
                return result
        raise SyncError("GitHub-pagineringslimiet bereikt; resultaat onvolledig")

    def pulls(self) -> list[dict]:
        return self.pages("pulls?state=all&sort=updated&direction=desc")

    def issue_and_comments(self, number: int):
        issue = self.api.github(f"/repos/{REPOSITORY}/issues/{number}")
        if issue.get("number") != number or "pull_request" in issue:
            raise SyncError("Koppeling verwijst niet naar de bedoelde GitHub-issue")
        return issue, self.pages(f"issues/{number}/comments?sort=updated")


ISSUE_QUERY = """query SyncIssue($id: String!, $after: String) {
  viewer { id }
  issue(id: $id) { id identifier updatedAt team { id } state { type }
    comments(first: 100, after: $after) {
      nodes { id body user { id } } pageInfo { hasNextPage endCursor }
    }
  }
}"""
CREATE_COMMENT = """mutation SyncCommentCreate($input: CommentCreateInput!) {
  commentCreate(input: $input) { success comment { id body } }
}"""
UPDATE_COMMENT = """mutation SyncCommentUpdate($id: String!, $input: CommentUpdateInput!) {
  commentUpdate(id: $id, input: $input) { success comment { id body } }
}"""


class Linear:
    def __init__(self, api: Api):
        self.api = api

    def read(self, identifier: str):
        comments, cursor, first = [], None, None
        for _ in range(1000):
            result = self.api.linear(ISSUE_QUERY, {"id": identifier, "after": cursor})
            issue = result.get("issue")
            if not issue or issue["identifier"] != identifier or issue["team"]["id"] != TEAM_ID:
                raise SyncError("Linear-issue ontbreekt of team valt buiten scope")
            if first is None:
                first = issue
            elif issue["updatedAt"] != first["updatedAt"]:
                raise SyncError("Linear-issue gewijzigd tijdens paginering")
            connection = issue.pop("comments")
            for comment in connection["nodes"]:
                if MARKER in comment["body"] and (comment.get("user") or {}).get("id") != result["viewer"]["id"]:
                    raise SyncError("Synchronisatiecomment hoort bij andere Linear-identiteit")
            comments.extend(connection["nodes"])
            page = connection["pageInfo"]
            if not page["hasNextPage"]:
                return first, comments
            next_cursor = page["endCursor"]
            if not next_cursor or next_cursor == cursor:
                raise SyncError("Linear-paginering stokt")
            cursor = next_cursor
        raise SyncError("Linear-pagineringslimiet bereikt")

    def save_comment(self, issue_id: str, comment_id: str | None, body: str):
        if comment_id is None:
            response = self.api.linear(CREATE_COMMENT, {"input": {"issueId": issue_id, "body": body}})["commentCreate"]
        else:
            response = self.api.linear(UPDATE_COMMENT, {"id": comment_id, "input": {"body": body}})["commentUpdate"]
        if not response.get("success"):
            raise SyncError("Linear-commentmutatie niet bevestigd")


def snapshot(binding: Binding, github, pulls: list[dict]) -> dict:
    issue, comments = github.issue_and_comments(binding.github_issue)
    relevant = [p for p in pulls if binding.linear_issue in PRIMARY.findall(p.get("body") or "")]
    receipts = []
    for comment in sorted(comments, key=lambda c: c.get("updated_at", ""), reverse=True):
        if comment.get("author_association") in TRUSTED:
            receipt = read_handoff(comment.get("body") or "", binding.linear_issue)
            if receipt:
                receipts.append({**receipt, "url": comment["html_url"]})
                break
    if not receipts:
        for pr in sorted(relevant, key=lambda p: p["number"], reverse=True):
            if pr.get("author_association") in TRUSTED:
                receipt = read_handoff(pr.get("body") or "", binding.linear_issue)
                if receipt:
                    receipts.append({**receipt, "url": pr["html_url"]})
                    break
    return {"issue": {"number": issue["number"], "state": issue["state"], "url": issue["html_url"]},
            "pulls": [{"number": p["number"], "state": "gemerged" if p.get("merged_at") else p["state"],
                       "head": p["head"]["sha"], "url": p["html_url"]}
                      for p in sorted(relevant, key=lambda p: p["number"])],
            "handoff": receipts[0] if receipts else None}


def render(value: dict) -> str:
    digest = hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    issue = value["issue"]
    lines = [MARKER, f"<!-- source-sha256:{digest} -->", "## GitHub-voortgang (automatisch)",
             f"[GitHub #{issue['number']}]({issue['url']}): {issue['state']}."]
    for p in value["pulls"]:
        lines.append(f"- [PR #{p['number']}]({p['url']}): {p['state']}, head `{p['head']}`.")
    handoff = value["handoff"]
    if handoff:
        # JSON quoting keeps untrusted markdown mentions/commands inert as displayed data.
        lines += ["", f"Expliciete overdracht op `{handoff['head']}`: {handoff['url']}",
                  f"Resterend werk verklaard: {str(handoff['remaining_work']).lower()}.",
                  "Volgende stap (bronverklaring, geen nieuwe opdracht):",
                  "```text",
                  json.dumps(handoff["next_step"], ensure_ascii=False).replace("<", "\\u003c").replace("`", "\\u0060"),
                  "```",
                  *[f"Bewijs: {url}" for url in handoff["evidence"]]]
    else:
        lines += ["", "Geen machineleesbare overdracht gevonden; lees de bestaande bron/handoff."]
    lines += ["", "Een merge is geen volledige oplevering. CI, deployment en gebruikersacceptatie "
              "zijn hier niet zelfstandig bewezen. Status, werkkeuze, prioriteit en eigenaar worden niet gewijzigd."]
    return "\n".join(lines)


def owned(comments: list[dict]) -> dict | None:
    matches = [c for c in comments if MARKER in c["body"]]
    if len(matches) > 1:
        raise SyncError("Linear heeft meerdere synchronisatiecomments; eerst herstellen")
    return matches[0] if matches else None


def reconcile(bindings: list[Binding], github, linear, *, apply: bool) -> dict[str, int]:
    pulls, prepared, contradictions = github.pulls(), [], []
    # Resolve every source/target before starting writes; an unavailable source is not 'done'.
    for binding in bindings:
        value = snapshot(binding, github, pulls)
        issue, comments = linear.read(binding.linear_issue)
        if issue["team"]["id"] != TEAM_ID:
            raise SyncError("Linear-team buiten scope")
        receipt = value["handoff"]
        if (issue.get("state", {}).get("type") == "completed" and receipt
                and receipt["remaining_work"]
                and receipt["head"] in {p["head"] for p in value["pulls"]}):
            contradictions.append(binding.linear_issue)
        prepared.append((binding, issue, owned(comments), render(value)))
    counts = {"changed": 0, "unchanged": 0}
    for binding, issue, previous, body in prepared:
        digest = re.search(r"source-sha256:[a-f0-9]{64}", body)[0]
        if previous and digest in previous["body"]:
            counts["unchanged"] += 1
            continue
        if not apply:
            counts["changed"] += 1
            continue
        fresh, comments = linear.read(binding.linear_issue)
        if fresh["updatedAt"] != issue["updatedAt"] or owned(comments) != previous:
            raise SyncError("Linear-doel gewijzigd; geen conflict overschrijven")
        linear.save_comment(issue["id"], previous["id"] if previous else None, body)
        _, after_comments = linear.read(binding.linear_issue)
        after = owned(after_comments)
        if not after or digest not in after["body"]:
            raise SyncError("Linear-comment niet teruggelezen; geen blind create-retry")
        counts["changed"] += 1
    if contradictions:
        raise SyncError("Done conflicteert met expliciete resterende scope: " + ", ".join(contradictions))
    return counts


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-config", action="store_true")
    parser.add_argument("--validate-event", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    try:
        bindings = load_bindings()
        if args.validate_event:
            event = json.loads(args.validate_event.read_text(encoding="utf-8"))
            pr = event["pull_request"]
            validate_pr_handoff(pr.get("body") or "", pr["head"]["sha"], bindings)
            print("PR-overdracht geldig op exacte head")
        elif args.check_config:
            print(f"Scope en {len(bindings)} unieke koppelingen geldig")
        else:
            api = Api(os.environ.get("GITHUB_TOKEN", ""), os.environ.get("LINEAR_API_KEY", ""))
            result = reconcile(bindings, GitHub(api), Linear(api), apply=args.apply)
            print(json.dumps({"mode": "apply" if args.apply else "dry-run", **result}))
        return 0
    except (SyncError, KeyError, TypeError, ValueError, OSError) as exc:
        message = str(exc) if isinstance(exc, SyncError) else "Ongeldige configuratie/event/API-structuur"
        print("Synchronisatie mislukt: " + message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
