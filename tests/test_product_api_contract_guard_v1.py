import copy

import pytest

from scripts.product_api_contract import ContractCompatibilityError, assert_backward_compatible

pytestmark = [
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


def spec():
    return {"paths": {"/v1/example": {"post": {
        "parameters": [{"in": "query", "name": "limit", "required": False,
                        "schema": {"type": "integer"}}],
        "requestBody": {"required": False, "content": {"application/json": {"schema": {
            "type": "object", "properties": {
                "name": {"type": "string"},
                "count": {"type": "integer"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "mode": {"type": "string"},
            },
        }}}},
        "responses": {},
    }}}}


@pytest.mark.parametrize("key,value,field", [
    ("minLength", 1, "name"), ("maxLength", 10, "name"),
    ("minimum", 1, "count"), ("maximum", 10, "count"),
    ("minItems", 1, "tags"), ("maxItems", 10, "tags"),
    ("enum", ["A", "B"], "mode"),
])
def test_new_request_constraint_is_breaking_even_when_old_constraint_absent(key, value, field):
    old = spec()
    new = copy.deepcopy(old)
    new["paths"]["/v1/example"]["post"]["requestBody"]["content"]["application/json"]["schema"]["properties"][field][key] = value
    with pytest.raises(ContractCompatibilityError, match="enum narrowed" if key == "enum" else f"{key} tightened"):
        assert_backward_compatible(old, new)


@pytest.mark.parametrize("key,field", [("minLength", "name"), ("minItems", "tags")])
def test_explicit_zero_lower_bound_is_equivalent_to_absent_constraint(key, field):
    old = spec()
    new = copy.deepcopy(old)
    new["paths"]["/v1/example"]["post"]["requestBody"]["content"]["application/json"]["schema"]["properties"][field][key] = 0
    assert_backward_compatible(old, new)


def test_narrowed_existing_enum_and_nested_item_constraint_are_breaking():
    old = spec()
    old["paths"]["/v1/example"]["post"]["requestBody"]["content"]["application/json"]["schema"]["properties"]["mode"]["enum"] = ["A", "B"]
    new = copy.deepcopy(old)
    properties = new["paths"]["/v1/example"]["post"]["requestBody"]["content"]["application/json"]["schema"]["properties"]
    properties["mode"]["enum"] = ["A"]
    properties["tags"]["items"]["minLength"] = 2
    with pytest.raises(ContractCompatibilityError, match="enum narrowed"):
        assert_backward_compatible(old, new)


@pytest.mark.parametrize("change,expected", [
    ("security", "security requirement changed"),
    ("optional_parameter", "optional parameter"),
    ("new_required_parameter", "new required parameter"),
    ("required_body", "request body became required"),
])
def test_new_authentication_or_required_inputs_are_breaking(change, expected):
    old = spec()
    new = copy.deepcopy(old)
    operation = new["paths"]["/v1/example"]["post"]
    if change == "security":
        operation["security"] = [{"VVNApiKeyBearer": []}]
    elif change == "optional_parameter":
        operation["parameters"][0]["required"] = True
    elif change == "new_required_parameter":
        operation["parameters"].append({"in": "header", "name": "X-New", "required": True, "schema": {"type": "string"}})
    else:
        operation["requestBody"]["required"] = True
    with pytest.raises(ContractCompatibilityError, match=expected):
        assert_backward_compatible(old, new)
