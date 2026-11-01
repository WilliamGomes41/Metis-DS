from pathlib import Path
import re

import yaml


ROOT = Path(__file__).resolve().parents[1]

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs


def test_statechart_preparation_preserves_authority_and_requires_executable_proof() -> None:
    contract = (ROOT / "docs/agents/statechart-integration.md").read_text(encoding="utf-8")
    purpose = contract.split("## Purpose and boundaries\n", 1)[1].split("\n## ", 1)[0]
    installation = contract.split("## Installation prerequisite\n", 1)[1].split("\n## ", 1)[0]
    completion = contract.split("## Completion gate\n", 1)[1].split("\n## ", 1)[0]

    # A model must never replace the existing domain or persistence authority.
    assert "existing Metis domain contracts and Class A/B/C classification remain authoritative" in purpose
    assert "A chart is not a domain-state source of truth" in purpose
    assert "Postgres/Azure remain the authoritative persistence boundary" in purpose
    assert "replay each reported counterexample against code" in purpose

    # Preparation cannot claim installation or code correctness from a checksum/model alone.
    assert "executable pstack statechart skill is not yet installed" in contract
    assert "Do not silently mix revisions" in installation
    assert "python scripts/sync_shared_agent_skills.py --check" in installation
    assert "static checksum check alone does not establish that the executable works" in installation
    for requirement in (
        "installed reproducibly",
        "executable in the intended environment",
        "one real model has been checked against the corresponding implementation",
        "Do not claim model checking proves the deployed code correct",
    ):
        assert requirement in completion


def test_agent_skill_wayfinding_docs_are_present_and_linked() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    expected_docs = (
        "docs/agents/issue-tracker.md",
        "docs/agents/linear-github-handoff.md",
        "docs/agents/triage-labels.md",
        "docs/agents/domain.md",
    )
    for relative_path in expected_docs:
        assert relative_path in agents
        assert (ROOT / relative_path).is_file()

    issue_tracker = (ROOT / "docs/agents/issue-tracker.md").read_text(encoding="utf-8")
    assert "Issues and specs for this repo live as GitHub issues" in issue_tracker

    triage_labels = (ROOT / "docs/agents/triage-labels.md").read_text(encoding="utf-8")
    for label in (
        "needs-triage",
        "needs-info",
        "ready-for-agent",
        "ready-for-human",
        "wontfix",
    ):
        assert label in triage_labels


def test_deployment_protocol_is_mandatory_and_keeps_the_container_route() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Every console deployment MUST follow `docs/agents/deployment-protocol.md`" in agents
    protocol = (ROOT / "docs/agents/deployment-protocol.md").read_text(encoding="utf-8")
    assert "docs/AZURE_RELEASE_RUNBOOK.md" in protocol
    assert (ROOT / "docs/AZURE_RELEASE_RUNBOOK.md").is_file()

    # One route: an exact main commit as a container image, swapped by digest.
    for rule in (
        "scripts/build_azure_release_image.sh",
        "@sha256:",
        "De ZIP-route (`deploy-production.yml`) is niet van toepassing",
        "Wissel nooit op een tag",
        "Alleen een exacte `main`-commit",
        "GO van de projectlead per stap die Azure wijzigt",
        "Zet het rollbackcommando nooit in hetzelfde blok als de wissel",
    ):
        assert rule in protocol

    # Preconditions before the swap, in order.
    order = [protocol.index(step) for step in (
        "Rollbackpunt vastleggen", "release_settings_preflight.py",
        "Geen lopende verwerking", "--runtime-role vvn-metis-console",
        "Image bouwen", "Wisselen op digest", "Verifiëren",
    )]
    assert order == sorted(order)

    # Done needs measured verification and a recorded handoff.
    for evidence in (
        "deployment_verified commit=<sha>", "pg_stat_activity", "request_finished",
        "linear-github-handoff.md", "gemerged + gedeployed + geverifieerd",
    ):
        assert evidence in protocol


def test_handoff_preserves_github_authority_and_requires_done_evidence() -> None:
    contract = (ROOT / "docs/agents/linear-github-handoff.md").read_text(encoding="utf-8")
    for obligation in (
        "GitHub is de bron van waarheid: code, gedragsbepalende besluiten en bewijs",
        "Linear verwijst naar GitHub en herhaalt het niet. Bij verschil wint GitHub.",
        "Een gedragsbepalend besluit dat alleen in Linear of in chat staat, geldt niet als vastgelegd.",
        "Done = gemerged + (waar nodig) gedeployed + geverifieerd.",
        "een verwijzing naar concreet bewijs",
        "CI- of testrun (PR-nummer en head-SHA)",
        "deployment_verified commit=",
        "handmatige check met wat, wie, wanneer en de gemeten uitkomst",
        "Zonder die verwijzing blijft het werkpakket open.",
    ):
        assert obligation in contract


def test_handoff_yaml_contains_required_context_and_allows_no_decision() -> None:
    contract = (ROOT / "docs/agents/linear-github-handoff.md").read_text(encoding="utf-8")
    template = yaml.safe_load(contract.split("```yaml\n", 1)[1].split("```", 1)[0])
    assert set(template) == {
        "handoff", "github_state", "production_state", "done", "half_done",
        "decision_needed", "next_step", "agreements_in_force", "diagram_update",
        "diagram_reason",
    }
    assert set(template["github_state"]) == {"main", "open_prs"}
    assert set(template["production_state"]) == {"commit", "image", "rollback"}
    assert set(template["decision_needed"]) == {"needed", "what"}
    assert "n.v.t." in template["decision_needed"]["what"]
    assert "Bij `needed: nee` vul je `what: n.v.t.` in" in contract
    assert "Bij `needed: ja` zijn opties en advies verplicht" in contract
    for obligation in (
        "`diagram_update: ja`, met een verwijzing naar de update",
        "`niet relevant`, met een reden",
        "`nee` mag alleen met een reden en een vervolg-issue",
        "Een leeg veld telt als een ontbrekende handoff",
    ):
        assert obligation in contract


def test_class_b_program_design_gate_requires_existing_path_before_code() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    required_contract = (
        "### Class B program-design gate",
        "trace the existing execution path",
        "the existing mechanism and authority",
        "the affected functions, types, and call path",
        "which state may mutate and which state must remain unchanged",
        "the smallest observable proof of the change",
        "before editing production code",
        "investigate first instead of patching",
        "MUST NOT be expanded into lifecycle-grade paperwork",
    )
    for phrase in required_contract:
        assert phrase in agents


def test_dispatcher_is_discoverable_and_preserves_selection_boundaries() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    relative_path = ".agents/skills/skill-dispatcher/SKILL.md"
    assert f"[skill-dispatcher]({relative_path})" in agents
    skill = (ROOT / relative_path).read_text(encoding="utf-8")
    assert skill.startswith("---\nname: skill-dispatcher\ndescription: ")
    assert "gearchiveerde" in skill
    assert "expliciet" in skill
    assert "geen extra toestemming" in skill
    assert "routeer niet recursief" in skill
    interface = (ROOT / relative_path).parent / "agents/openai.yaml"
    assert "$skill-dispatcher" in interface.read_text(encoding="utf-8")


def test_dispatcher_examples_use_current_names_and_explicit_only_boundaries() -> None:
    skill = (ROOT / ".agents/skills/skill-dispatcher/SKILL.md").read_text(encoding="utf-8")
    rows = [line for line in skill.splitlines() if line.startswith("| ")]
    examples = "\n".join(rows)
    assert "`decision-oriented-writing`" in examples
    assert "`literature-review`" in examples
    for name in (
        "codebase-architecture-review",
        "agent-authorization-and-completion-gates",
        "assumption-testing-interview",
    ):
        row = next(line for line in rows if f"`{name}`" in line)
        assert "expliciet" in row
    obsolete = {
        "external-agent-gates", "grill-me", "minto", "via-negativa-redacteur",
        "heldere-uitleg", "literature-review-suite", "concise-text-editor", "clear-explanation",
    }
    assert not obsolete.intersection(re.findall(r"`([^`]+)`", examples))
def test_agents_requires_one_deterministic_candidate_creator_before_review():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    section = agents.split("### Hard invariant: one deterministic candidate creator before human review", 1)[1].split("\n### ", 1)[0]
    for obligation in (
        "deterministic materialisation MUST be the sole KnowledgeCandidate creator",
        "src/vorming/knowledge_materialisation_v1.py::materialise_knowledge_candidates",
        "They MUST NOT independently assign candidate identity",
        "they MUST NOT independently create, rewrite, split, merge, or silently repair a candidate",
        "Rejection MUST preserve source work and recovery findings",
        "every supported pre-review route uses the same creator",
        "This pre-review invariant grants no additional review or publication authority",
        "agents MUST NOT weaken or bypass it autonomously",
    ):
        assert obligation in section
