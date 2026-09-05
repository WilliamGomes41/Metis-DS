from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
DELTA = ROOT / "docs" / "PROTOCOL_V2_24_CONSOLE_RETRIEVAL_DEPLOY_SPLIT_DELTA.md"
APPROVAL = ROOT / "data" / "assurance" / "protocol_v2_24_approval.json"

FORBIDDEN_PACKAGES = frozenset({"numpy", "sklearn", "scipy", "scikit-learn"})
FORBIDDEN_RETRIEVAL_MODULES = frozenset(
    {
        "embedding_provider_v1",
        "semantic_vector_retrieval_v1",
        "hybrid_retrieval_v1",
        "provider_vector_retrieval_v1",
        "product_api_v1",
        "safe_retrieval_v1",
    }
)
CONSOLE_ENTRYPOINTS = (
    SRC / "console_asgi.py",
    SRC / "operations_console_v1.py",
    SRC / "operations_console_app.py",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _module_name_from_src(path: Path) -> str:
    return path.stem


def _imported_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".")[0] if module else ""
            if root:
                names.add(root)
            if module:
                names.add(module)
                names.add(module.split(".")[-1])
            if root == "src" and module.startswith("src."):
                names.add(module.split(".", 1)[1].split(".")[0])
            elif node.level and node.module:
                names.add(node.module.split(".")[0])
    return names


def _walk_console_import_graph() -> set[str]:
    seen_files: set[Path] = set()
    names: set[str] = set()
    queue = list(CONSOLE_ENTRYPOINTS)
    while queue:
        path = queue.pop()
        if path in seen_files or not path.is_file():
            continue
        seen_files.add(path)
        imported = _imported_names(path)
        names.update(imported)
        for raw in imported:
            candidate = raw.split(".")[-1]
            local = SRC / f"{candidate}.py"
            if local.is_file() and local not in seen_files:
                queue.append(local)
    return names


def test_v224_approval_manifest_matches_protocol_bytes() -> None:
    manifest = json.loads(APPROVAL.read_text(encoding="utf-8"))
    assert manifest["protocol_version"] == "2.24.0"
    assert manifest["protocol_path"] == "docs/PROTOCOL_V2_24_CONSOLE_RETRIEVAL_DEPLOY_SPLIT_DELTA.md"
    assert manifest["protocol_sha256"] == _sha256_file(DELTA)
    assert manifest["commit_sha"] == "pending_after_merge"
    assert manifest["approval_date"] == "2026-09-03"
    assert manifest["approval_authority"] == "project_owner"
    assert manifest["conformance_effect"] == "does_not_override_gate_status"


def test_v224_delta_exists_and_is_the_live_baseline() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")

    assert DELTA.is_file()
    assert "**Status:** Approved for project use" in delta
    assert "**Protocol delta version:** 2.24.0" in delta
    assert "docs/PROTOCOL_V2_24_CONSOLE_RETRIEVAL_DEPLOY_SPLIT_DELTA.md" in root_protocol
    assert root_protocol.count("De geldende normatieve baseline is Protocol v2.26.0") == 1
    assert "plus Protocol v2.23.0 plus Protocol v2.22.0 plus Protocol v2.21.0 plus Protocol v2.20.0 plus Protocol v2.19.0 plus Protocol v2.18.0 plus Protocol v2.17.0 plus Protocol v2.16.0 plus Protocol v2.15.0 plus Protocol v2.13.0 plus Protocol v2.12.0 plus Protocol v2.11.0" in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.23.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.22.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.21.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.20.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.19.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.18.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.17.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.16.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.15.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.14.0" not in root_protocol
    assert "De geldende normatieve baseline is Protocol v2.13.0" not in root_protocol
    assert "Protocol v2.24.0" in roadmap


def test_v224_does_not_redesign_the_four_layers_or_write_v214() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "This delta MUST NOT invent a fifth layer" in delta
    assert "MUST NOT collapse those four" in delta
    assert "source/evidence → canonical knowledge → governance → product" in delta
    assert "This file is not Protocol v2.14" in delta
    assert "This delta MUST NOT write Protocol v2.14" in delta
    assert "vier lagen" in root_protocol
    assert "Protocol v2.14 wordt in deze delta niet geschreven" in root_protocol
    assert "LOCKED als het volgende protocol (v2.14), niet deze PR" in roadmap
    assert "MUST NOT Protocol v2.14 worden geschreven" in roadmap


def test_v224_architecture_sentence_locked_verbatim() -> None:
    sentence = "Runtime-scheiding mag veranderen; protocol- en publicatiegrenzen niet."
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert sentence in delta
    assert sentence in root_protocol
    assert sentence in roadmap
    assert sentence in changelog


def test_v224_split_deploy_package_not_product_idea() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "split the deploy package, not the product idea" in delta
    assert "Two doors already exist" in delta
    assert "Tonight B1 died because one `requirements.txt` vendored numpy/sklearn/scipy into `vvn-metis-console`" in delta
    assert "split the deploy package, not the product idea" in root_protocol
    assert "split het deploy-pakket, niet het productidee" in root_protocol
    assert "split het deploy-pakket, niet het productidee" in roadmap
    assert "split the deploy package, not the product idea" in changelog


def test_v224_console_zip_must_not_vendor_sklearn_stack() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "Azure deploy package MUST NOT vendor numpy, sklearn, scipy, or scikit-learn" in delta
    assert "Console ZIP MAY include FastAPI, gunicorn, uvicorn, python-multipart, PyMuPDF, jsonschema, azure-identity, azure-storage-blob" in delta
    assert "G2 client remains fail-closed" in delta
    assert "Oryx `output.tar.zst` of a fat vendor tree on B1 is refused" in delta
    assert "136MB tar extract" in delta
    assert "MUST NOT numpy, sklearn, scipy of scikit-learn vendoren" in root_protocol
    assert "136MB tar-extract" in root_protocol
    assert "MUST NOT numpy, sklearn, scipy of scikit-learn vendoren" in roadmap
    assert "MUST NOT vendor numpy, sklearn, scipy, or scikit-learn" in changelog
    assert "136MB tar extract" in changelog


def test_v224_console_asgi_must_not_import_retrieval_at_process_start() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    assert "`console_asgi` MUST NOT import `embedding_provider` / vector retrieval / hybrid retrieval at process start" in delta
    assert "console_asgi MUST NOT embedding_provider / vector retrieval / hybrid retrieval importeren bij process start" in root_protocol


def test_v224_product_api_not_same_worker_and_not_live_this_wave() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "Product API MUST NOT be deployed in the same App Service worker as the Review console" in delta
    assert "MUST NOT go live in this wave" in delta
    assert "No new App Service in this PR" in delta
    assert "`LocalCharTfidfEmbeddingProvider` stays in the repo" in delta
    assert "Product API MUST NOT in dezelfde App Service-worker als de Review-console" in root_protocol
    assert "MUST NOT in deze golf live" in root_protocol
    assert "Geen nieuwe App Service in deze PR" in root_protocol
    assert "LocalCharTfidfEmbeddingProvider" in roadmap


def test_v224_split_does_not_open_publish_or_g2() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "this split opens `publish()` or G2" in delta
    assert "This split does not open `publish()` or G2" in delta
    assert "G2 remains BLOCKED" in delta or "G2 is still BLOCKED" in delta
    assert "deze split opent `publish()` of G2 niet" in root_protocol
    assert "G2 blijft BLOCKED" in root_protocol
    assert "deze split opent publish() of G2 niet" in roadmap
    assert "this split does not open publish() or G2" in changelog


def test_v224_shared_across_doors_and_not_accounts_or_unpublished() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "Shared across doors: PROTOCOL, freeze bytes (SHA-256), and later G2 published objects" in delta
    assert "MUST NOT share unpublished review store or console login accounts as API entitlement" in delta
    assert "Console accounts are not API tenants" in delta
    assert "Unpublished review snapshots are not shared with the Product API" in delta
    assert "Gedeeld over deuren: PROTOCOL, freeze-bytes (SHA-256) en later G2-gepubliceerde objecten" in root_protocol
    assert "MUST NOT unpublished review-store of console-loginaccounts als API-entitlement delen" in root_protocol
    assert "console-accounts zijn geen API-tenants" in root_protocol
    assert "Gedeeld over deuren" in roadmap


def test_v224_one_shared_kernel_no_second_law() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "The temporary deploy split MUST NOT become two systems" in delta
    assert "PROTOCOL, object formats, freeze rules, and publish logic are one shared kernel" in delta
    assert "Console MUST NOT interpret review/object/freeze/publish rules differently from Product API" in delta
    assert "No second law in the API" in delta
    assert "tijdelijke deploy-split MUST NOT twee systemen worden" in root_protocol
    assert "één gedeelde kernel" in root_protocol
    assert "Geen tweede wet in de API" in root_protocol
    assert "één gedeelde kernel" in roadmap
    assert "No second law in the API" in changelog


def test_v224_dependency_drift_package_boundaries_are_law() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "Shared kernel modules MUST NOT import numpy, sklearn, scipy, or scikit-learn" in delta
    assert "A console import of shared code MUST NOT pull those in" in delta
    assert "Package boundaries are law" in delta
    assert "tests in this protocol PR MUST fail if `console_asgi` / `operations_console_*` import graph includes" in delta
    assert "Gedeelde kernelmodules MUST NOT numpy, sklearn, scipy of scikit-learn importeren" in root_protocol
    assert "Pakketgrenzen zijn wet" in root_protocol
    assert "Package boundaries are law" in changelog


def test_v224_data_boundary_technically_enforceable() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "data boundary MUST be technically enforceable" in delta
    assert "separate access, credentials, and storage rights" in delta
    assert "Unpublished review store and researcher console accounts MUST NOT be reachable with Product API credentials" in delta
    assert "“We don’t do that” is not enough" in delta or '"We don\'t do that" is not enough' in delta
    assert "Do not build the API App Service in this PR" in delta
    assert "MUST de datagrens technisch afdwingbaar zijn" in root_protocol
    assert "MUST NOT bereikbaar zijn met Product API-credentials" in root_protocol
    assert "«We doen dat niet» is niet genoeg" in root_protocol
    assert "technically enforceable" in changelog


def test_v224_thin_b1_must_not_accrete_subscriber_retrieval() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "thin B1 console MUST NOT accrete subscriber/retrieval features as “one more small thing”" in delta
    assert "Functional boundary: review work (ingest, tree, Beoordeel, unpublished delete, four-eyes) in the console runtime" in delta
    assert "Retrieval and subscriber functions outside that runtime" in delta
    assert "dunne B1-console MUST NOT subscriber-/retrievalfuncties aangroeien als «nog één klein ding»" in root_protocol
    assert "Functionele grens: reviewwerk (ingest, boom, Beoordeel, unpublished delete, four-eyes) in de console-runtime" in root_protocol
    assert "one more small thing" in changelog


def test_v224_console_classification_is_rules_not_sklearn() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    assert "Console classification remains closed taxonomy + context-aware splitter (rules), not sklearn" in delta
    assert "Consoleclassificatie blijft gesloten taxonomie + context-bewuste splitter (regels), niet sklearn" in root_protocol


def test_v224_keeps_two_products_and_cli_review_queue() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "`service_app.py` AND `product_api_v1.py` are two products" in delta
    assert "Do not silent-delete CLI review-queue" in delta
    assert "Console remains the researcher duty queue" in delta
    assert "service_app.py EN product_api_v1.py blijven" in root_protocol
    assert "twee producten, geen leftovers" in root_protocol
    assert "MUST NOT CLI review-queue stilzwijgend verwijderen" in root_protocol
    assert "Console is de onderzoeker-plichtwachtrij" in root_protocol
    assert "service_app.py" in roadmap
    assert "product_api_v1.py" in roadmap
    assert "review-queue" in roadmap


def test_v224_next_code_is_requirements_split_not_this_pr() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "split console vs retrieval requirements, prove `console_asgi` import graph has no sklearn/numpy, one thin console ZIP" in delta
    assert "Cloud Shell of that ZIP is a later live step, not tonight" in delta
    assert "MUST NOT implement the requirements split in this PR" in delta
    assert "MUST NOT Cloud Shell tonight" in delta
    assert "Two Cloud Shell ZIPs of different SHAs still refused" in delta
    assert "a later thin ZIP of the v2.24 implementation SHA is the one live ZIP" in delta
    assert "PR #82 stays closed/unmerged" in delta
    assert "Wave B still after a healthy console ZIP + ingest" in delta
    assert "volgende code is console- versus retrieval-requirements splitsen" in root_protocol
    assert "MUST NOT requirements-split in deze PR implementeren" in root_protocol
    assert "MUST NOT vannacht Cloud Shell" in root_protocol
    assert "Twee Cloud Shell ZIPs van verschillende SHAs blijven geweigerd" in root_protocol
    assert "PR #82 blijft gesloten/ongemerged" in root_protocol
    assert "volgende code is console- versus retrieval-requirements splitsen" in roadmap
    assert "Protocol v2.24.0" in changelog
    assert "does not implement console, extract or Azure" in changelog
    assert "MUST NOT implement the requirements split in this PR" in changelog


def test_v224_handoff_must_not_be_recreated() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "`HANDOFF.md` MUST NOT be recreated" in delta
    assert "HANDOFF.md MUST NOT opnieuw worden aangemaakt" in root_protocol
    assert "HANDOFF.md" in roadmap
    assert not (ROOT / "HANDOFF.md").exists()


def test_v224_keeps_continentie_evidence_and_every_guideline_law() -> None:
    delta = _read(DELTA)
    root_protocol = _read(ROOT / "PROTOCOL.md")
    roadmap = _read(ROOT / "ROADMAP.md")
    assert "Continentie evidence sentences" in delta or "historical Continentie evidence sentences" in delta
    assert "PROTOCOL.md is every-guideline law" in delta or "PROTOCOL.md is wet voor iedere richtlijn" in root_protocol
    assert "PROTOCOL.md is wet voor iedere richtlijn, niet Continentie-only" in root_protocol
    assert "Continentie-bewijszinnen in v2.16–v2.19 MUST blijven" in root_protocol
    assert "Continentie-bewijszinnen in v2.16–v2.19 MUST blijven" in roadmap


def test_v224_is_c3_spanning_review_surface_owner_approved_and_does_not_reopen_gd03() -> None:
    delta = _read(DELTA)
    governance = _read(ROOT / "docs" / "GOVERNANCE.md")
    assert "**Highest change class:** C3 spanning review-surface / retrieve-safety (split the deploy package, not the product idea; thin console ZIP; MUST NOT vendor numpy/sklearn/scipy into vvn-metis-console; one shared kernel; Product API later, not this wave; split does not open publish/G2)" in delta
    assert "This is not a C5 reopen of four-eyes or publish" in delta
    assert "This delta is owner-approved" in delta
    assert "Named C3 reviewers are not yet staffed" in delta
    assert "Named reviewers are not staffed" in delta
    assert "does not reopen GD-03" in delta
    assert "Metis, the Implementation engineer and the Auditor MUST NOT count as GD-03 reviewers" in delta
    assert "Protocol v2.24.0 is een eigenaarsgoedgekeurde C3-protocoldelta spanning review-surface / retrieve-safety" in governance
    assert "heropent GD-03 niet" in governance
    assert "Benoemde reviewers blijven onbezet" in governance
    gd03 = json.loads((ROOT / "data" / "assurance" / "gd_03_c3_c6_reviewer_matrix.json").read_text(encoding="utf-8"))
    assert gd03["status"] == "ESTABLISHED"


def test_v224_leaves_v216_through_v223_delta_files_untouched_except_v223_pointer() -> None:
    v216 = (ROOT / "docs" / "PROTOCOL_V2_16_REVIEW_PAGE_RESEARCHER_BAR_DELTA.md").read_bytes()
    v217 = (ROOT / "docs" / "PROTOCOL_V2_17_REVIEW_PAGE_RESEARCHER_SURFACE_DELTA.md").read_bytes()
    v218 = (ROOT / "docs" / "PROTOCOL_V2_18_REVIEW_CARD_EXTRACT_DEDUP_DELTA.md").read_bytes()
    v219 = (ROOT / "docs" / "PROTOCOL_V2_19_REVIEW_DUTY_QUEUE_DELTA.md").read_bytes()
    v220 = (ROOT / "docs" / "PROTOCOL_V2_20_UNPUBLISHED_DOCUMENT_DELETE_DELTA.md").read_bytes()
    v221 = (ROOT / "docs" / "PROTOCOL_V2_21_CONTROLLED_USE_WAVES_DELTA.md").read_bytes()
    v222 = (ROOT / "docs" / "PROTOCOL_V2_22_WAVE_ORDER_C_D_BEFORE_B_DELTA.md").read_bytes()
    v223 = (ROOT / "docs" / "PROTOCOL_V2_23_CODE_SURFACE_SIMPLIFICATION_DELTA.md").read_bytes()
    assert b"**Protocol delta version:** 2.16.0" in v216
    assert b"**Protocol delta version:** 2.17.0" in v217
    assert b"**Protocol delta version:** 2.18.0" in v218
    assert b"**Protocol delta version:** 2.19.0" in v219
    assert b"**Protocol delta version:** 2.20.0" in v220
    assert b"**Protocol delta version:** 2.21.0" in v221
    assert b"**Protocol delta version:** 2.22.0" in v222
    assert b"**Protocol delta version:** 2.23.0" in v223
    new_law = b"thin console ZIP"
    fat_tree = b"136MB tar extract"
    for old in (v216, v217, v218, v219, v220, v221, v222):
        assert new_law not in old
        assert fat_tree not in old
    assert b"Index/conflict pointer: Protocol v2.24.0" in v223
    assert new_law in DELTA.read_bytes()
    assert fat_tree in DELTA.read_bytes()


def test_v224_does_not_reopen_serving_typeset_stamps_chrome_duty() -> None:
    delta = _read(DELTA)
    assert "Do not reopen serving typeset, stamps, chrome, slogans, bronpassage-prose, empty Onderwerp, relation-checkbox adjacency, review-duty / queue presentation, unpublished-snapshot delete, wave A/B/C/D definitions, or the first DELETE cut except as already required" in delta
    assert "The v2.12 closed serving typeset remains UNCHANGED" in delta
    assert "This delta’s bar is the thin console ZIP and one shared kernel" in delta


def test_v224_out_of_scope_matches_owner_lock() -> None:
    delta = _read(DELTA)
    assert "implementing console/extract/Azure" in delta
    assert "implementing the requirements split" in delta
    assert "merging product code" in delta
    assert "G2 PASS" in delta
    assert "Protocol v2.14" in delta
    assert "LLM" in delta
    assert "nurse UI" in delta
    assert "SSH wipe" in delta
    assert "treating Metis / Implementation engineer / Auditor as GD-03 reviewers" in delta
    assert "taking this protocol PR as the Cloud Shell ZIP" in delta
    assert "Cloud Shell tonight" in delta
    assert "merging PR #82" in delta
    assert "recreating `HANDOFF.md`" in delta
    assert "building the API App Service in this PR" in delta


def test_v224_console_import_graph_excludes_forbidden_packages() -> None:
    names = _walk_console_import_graph()
    hits = sorted(name for name in names if name.split(".")[0] in FORBIDDEN_PACKAGES or name in FORBIDDEN_PACKAGES)
    assert hits == [], f"console_asgi / operations_console_* import graph includes forbidden packages: {hits}"


def test_v224_console_import_graph_excludes_retrieval_modules() -> None:
    names = _walk_console_import_graph()
    hits = sorted(FORBIDDEN_RETRIEVAL_MODULES.intersection(names))
    assert hits == [], (
        "console_asgi / operations_console_* import graph includes retrieval/Product API modules: "
        f"{hits}"
    )


def test_v224_shared_kernel_reached_from_console_excludes_forbidden_packages() -> None:
    names = _walk_console_import_graph()
    for name in names:
        root = name.split(".")[0]
        assert root not in FORBIDDEN_PACKAGES, f"shared kernel pulled {name} into the console import graph"
        assert name not in FORBIDDEN_PACKAGES
