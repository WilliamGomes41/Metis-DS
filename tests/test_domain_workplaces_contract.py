"""Check the handoff's concrete code references without requiring a running app."""
import ast
from pathlib import Path
import re
import unittest

from scripts.validate_change_contract import validate_change_contract


ROOT = Path(__file__).resolve().parents[1]
DOCUMENT = ROOT / "docs/change-contracts/domain-workplaces.md"

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
# Concrete evidence: the handoff resolves to existing owners and POST declarations;
# no runtime module is imported and no source or workflow state is mutated.
class DomainWorkplacesReferences(unittest.TestCase):
    def test_handoff_references_existing_owners_and_post_routes(self):
        text = DOCUMENT.read_text(encoding="utf-8")
        self.assertEqual(validate_change_contract(text), [])
        references = set(re.findall(r"`((?:src|scripts|tests|docs)/[^` ]+)", text))
        self.assertTrue(references)
        for reference in sorted(references):
            path, _, symbol = reference.partition("::")
            if "*" in path:
                continue
            with self.subTest(reference=reference):
                source = ROOT / path
                self.assertTrue(source.is_file(), reference)
                if symbol:
                    declarations = {
                        node.name for node in ast.walk(ast.parse(source.read_text()))
                        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                    }
                    for name in symbol.split("/"):
                        self.assertIn(name.rsplit(".", 1)[-1], declarations)

        post_routes = set()
        for source in (ROOT / "src").rglob("*.py"):
            for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                    continue
                if not node.args or not isinstance(node.args[0], ast.Constant):
                    continue
                if node.func.attr == "post":
                    post_routes.add(node.args[0].value)
                elif node.func.attr == "add_api_route":
                    for keyword in node.keywords:
                        if keyword.arg == "methods" and isinstance(keyword.value, (ast.List, ast.Tuple)):
                            if any(isinstance(item, ast.Constant) and item.value == "POST"
                                   for item in keyword.value.elts):
                                post_routes.add(node.args[0].value)
        documented = set(re.findall(r"\bPOST[ `]+(/[a-zA-Z0-9/_-]+)", text))
        self.assertTrue(documented)
        self.assertEqual(documented - post_routes, set())


if __name__ == "__main__":
    unittest.main()
