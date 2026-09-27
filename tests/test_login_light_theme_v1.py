"""Login remains light without overwriting the console theme preference.
# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import json
import re
import shutil
import subprocess

import pytest

from src.operations_console_app import _page


@pytest.mark.skipif(shutil.which("node") is None, reason="JavaScript runtime needed for theme behavior")
@pytest.mark.parametrize(
    "path,saved,system_dark,expected",
    [
        ("/login", "dark", True, "light"),
        ("/login", None, True, "light"),
        ("/review", "dark", False, "dark"),
        ("/review", "light", True, "light"),
        ("/review", None, True, "dark"),
    ],
)
def test_login_theme_preserves_console_preference(path, saved, system_dark, expected):
    # Execute the actual head initializer; deny preference access on login.
    page = _page("<h1>Aanmelden</h1>")
    script = re.search(r"<script>([\s\S]*?)</script>", page).group(1)
    payload = json.dumps(dict(script=script, path=path, saved=saved, system_dark=system_dark))
    runner = r"""
const fs = require('fs');
const vm = require('vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const document = {documentElement: {dataset: {}}};
let reads = 0;
const context = {
  document,
  location: {pathname: input.path},
  localStorage: {
    getItem: () => { reads++; return input.saved; },
    setItem: () => { throw new Error('must not overwrite preference'); },
    removeItem: () => { throw new Error('must not remove preference'); }
  },
  matchMedia: () => ({matches: input.system_dark}),
};
vm.runInNewContext(input.script, context);
process.stdout.write(JSON.stringify({theme: document.documentElement.dataset.theme, reads}));
"""
    result = subprocess.run(
        [shutil.which("node"), "-e", runner], input=payload, text=True,
        capture_output=True, check=True, timeout=10,
    )
    actual = json.loads(result.stdout)
    assert actual["theme"] == expected
    assert actual["reads"] == (0 if path == "/login" else 1)
