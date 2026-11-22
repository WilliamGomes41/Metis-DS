from pathlib import Path
import re
import shlex

import yaml


ROOT = Path(__file__).resolve().parents[1]

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs


def test_skill_selection_links_stitch_fork_without_loosening_existing_triggers() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    guide = agents.split("## Skills\n", 1)[1]
    rows = {line.split("|")[1].strip(): line for line in guide.splitlines() if line.startswith("| [")}
    assert "MUST read and apply" in next(v for k, v in rows.items() if "Impeccable" in k)
    assert "Explicit requests" in next(v for k, v in rows.items() if "pstack" in k)
    assert "Only on an explicit request" in next(v for k, v in rows.items() if "Matt Pocock" in k)
    stitch = next(v for k, v in rows.items() if "Stitch" in k)
    assert "https://github.com/WilliamGomes41/stitch-skills" in stitch
    assert "before implementing" in stitch
    assert "docs/agents/shared-skills.md#external-stitch-plugin" in stitch
    assert "Emil Kowalski" in guide
    assert "read-only" in next(v for k, v in rows.items() if "Emil Kowalski" in k)
    shared = (ROOT / "docs/agents/shared-skills.md").read_text()
    external = shared.split("## External Stitch plugin\n", 1)[1].split("\n## ", 1)[0]
    for boundary in ("geen kopie in Metis", "Stitch MCP-/accountverbinding",
                     "claim geen Stitch-generatie", "synthetische data"):
        assert boundary in external
    for relative in re.findall(r"\]\((?!https://)([^)]+)\)", guide):
        assert (ROOT / relative.split('#', 1)[0]).is_file(), relative


def test_root_navigation_and_verification_commands_resolve_to_real_targets() -> None:
    agents = (ROOT / "AGENTS.md").read_text()
    for relative in re.findall(r"\]\((?!https://)([^)]+)\)", agents):
        path, _, anchor = relative.partition('#')
        target = ROOT / path
        assert target.is_file(), relative
        if anchor:
            headings = re.findall(r"^#+ (.+)$", target.read_text(), re.M)
            slugs = {re.sub(r'[^\w\s-]', '', h.lower()).replace(' ', '-') for h in headings}
            assert anchor in slugs, relative
    commands = agents.split('```sh\n', 1)[1].split('```', 1)[0].splitlines()
    scripts = set()
    for command in commands:
        if not command.strip():
            continue
        args = shlex.split(command)
        assert args[0] == 'python'
        if args[1] == '-m':
            assert args[2] in {'compileall', 'pytest'}
            for arg in args[3:]:
                if arg.startswith('tests/'):
                    assert (ROOT / arg).is_file(), arg
        else:
            assert (ROOT / args[1]).is_file(), command
            scripts.add(args[1])
    assert {'scripts/repository_preflight.py', 'scripts/release_control_preflight.py',
            'scripts/check_architecture_boundaries.py'} <= scripts
    assert 'bash scripts/test_postgres.sh' in agents
    assert (ROOT / 'scripts/test_postgres.sh').is_file()


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
        "De ZIP-route (`deploy-production.yml`) is technisch begrensd tot `PYTHON|3.13`",
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


def test_non_workflow_rights_are_a_stop_gate_before_cutover_and_deployment() -> None:
    cutover = (ROOT / 'docs/AZURE_STEP9_CUTOVER_RUNBOOK.md').read_text(encoding='utf-8')
    gate_title = '### STOP: rechten buiten workflow nog niet bewezen'
    gate = cutover.split(gate_title, 1)[1].split('## 4.', 1)[0]
    assert cutover.index(gate_title) < cutover.index('## 4.')
    for requirement in (
        'workflow-PASS is geen toestemming', '`public`', '`api_access`',
        'rechtenprofiel', 'GRANT-regels', 'runtime-identiteit',
        'lees- en schrijfbewerkingen', 'geïsoleerde database',
        'Ontbreekt het rechtenprofiel of het verificatiebewijs: STOP',
        'Pas geen\nworkflowflag aan en voer geen image-wissel uit',
    ):
        assert requirement in gate

    release = (ROOT / 'docs/AZURE_RELEASE_RUNBOOK.md').read_text(encoding='utf-8')
    stop = 'STOP bij ontbrekend non-workflow-rechtenbewijs'
    assert release.index(stop) < release.index('## 2. Image bouwen')
    assert 'AZURE_STEP9_CUTOVER_RUNBOOK.md#stop-rechten-buiten-workflow-nog-niet-bewezen' in release

    protocol = (ROOT / 'docs/agents/deployment-protocol.md').read_text(encoding='utf-8')
    step = next(line for line in protocol.splitlines() if line.startswith('| 4 |'))
    assert all(value in step for value in ('`public`', '`api_access`', 'runtime-identiteit', 'STOP'))


def test_pr_template_and_agents_use_closing_keywords_and_live_label() -> None:
    template = (ROOT / ".github/pull_request_template.md").read_text(encoding="utf-8")
    for rule in ("`Closes #N` + `Fixes MET-N`", "`Part of MET-N` + `Refs #N`",
                 "geen `met-N` in de branchnaam"):
        assert rule in template
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "A merge alone does not prove deployment or acceptance." in agents
    assert "Done in Linear = merged on main; deployment/acceptance = label `live`" in agents
    sync_doc = (ROOT / "docs/agents/linear-github-sync.md").read_text(encoding="utf-8")
    assert "al gemergde PR" in sync_doc and "waarschuwing" in sync_doc


def test_handoff_preserves_github_authority_and_requires_done_evidence() -> None:
    contract = (ROOT / "docs/agents/linear-github-handoff.md").read_text(encoding="utf-8")
    for obligation in (
        "GitHub is de bron van waarheid: code, gedragsbepalende besluiten en bewijs",
        "Linear verwijst naar GitHub en herhaalt het niet. Bij verschil wint GitHub.",
        "Een gedragsbepalend besluit dat alleen in Linear of in chat staat, geldt niet als vastgelegd.",
        "Done = gemerged op main met `Closes #N` en `Fixes MET-N`.",
        "Deploy en live verificatie zijn het label `live`",
        "geen voorwaarde voor Done",
        "`Part of MET-N` + `Refs #N`",
        "geen `met-N` in de branchnaam",
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
    owner = 'docs/agents/continuous-development.md'
    assert owner + '#class-b-program-design-gate' in agents
    model = (ROOT / owner).read_text(encoding='utf-8')

    required_contract = (
        "#### Class B program-design gate",
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
        assert phrase in model


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
    owner = 'docs/agents/abstraction-boundaries.md'
    assert owner in agents and 'single-candidate-creator rule' in agents
    contract = (ROOT / owner).read_text(encoding='utf-8')
    section = contract.split("## Hard invariant: one deterministic candidate creator before human review", 1)[1].split("\n## ", 1)[0]
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
