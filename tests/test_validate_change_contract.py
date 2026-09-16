from scripts.validate_change_contract import validate_change_contract


def base_contract(**overrides: str) -> str:
    values = {
        "Change class": "B",
        "Promise": "Every implementation PR is checked before normal CI.",
        "Proof": "Valid passes; invalid fails.",
        "Touches lifecycle invariants": "no",
        "Rewrite risk": "none",
    }
    values.update(overrides)
    return "\n".join(f"{key}: {value}" for key, value in values.items())


def test_valid_class_b_contract_passes():
    assert validate_change_contract(base_contract()) == []


def test_missing_promise_fails():
    errors = validate_change_contract(base_contract(Promise=""))
    assert "missing or placeholder field: Promise" in errors


def test_missing_proof_fails():
    errors = validate_change_contract(base_contract(Proof=""))
    assert "missing or placeholder field: Proof" in errors


def test_invalid_class_and_rewrite_risk_fail():
    errors = validate_change_contract(
        base_contract(**{"Change class": "D", "Rewrite risk": "medium"})
    )
    assert "Change class must be exactly A, B, or C" in errors
    assert "Rewrite risk must be exactly none or high" in errors


def test_high_risk_requires_rewrite_mitigation_fields():
    errors = validate_change_contract(base_contract(**{"Rewrite risk": "high"}))
    assert "high rewrite risk requires field: Rewrite target" in errors
    assert "high rewrite risk requires field: Rollback/recovery plan" in errors
    assert "high rewrite risk requires field: Adversarial proof matrix" in errors


def test_class_a_requires_lifecycle_fields():
    errors = validate_change_contract(
        base_contract(**{"Change class": "A", "Touches lifecycle invariants": "yes"})
    )
    assert "Class A requires lifecycle field: Lifecycle entity" in errors
    assert "Class A requires lifecycle field: Lifecycle transition" in errors
    assert "Class A requires lifecycle field: Required black-box scenario" in errors


def test_markdown_pr_template_field_format_is_accepted():
    text = """\
- **Change class**: B
- **Promise**: A bounded behavior works end to end.
- **Proof**: The acceptance test passes.
- **Touches lifecycle invariants**: no
- **Rewrite risk**: none
"""
    assert validate_change_contract(text) == []
