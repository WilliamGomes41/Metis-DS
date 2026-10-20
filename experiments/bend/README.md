# Bend experiment for Metis DS

This directory is an isolated language/proof experiment (#773). It does not
verify or replace the existing Metis Python code. The identity example proves
only that its Bend function preserves every natural-number input.

## Codespaces

After this change is merged, new Codespaces install Bend 2.0.37 in the editor
workspace through `postCreateCommand`. Existing Codespaces require a container
rebuild, or manual installation below. Installation is not performed in the
offline security runner or the production application. Open a new terminal if
an existing terminal still has the old PATH.

The installer and proof source live in Git; `~/.bend` is recreated in each new
workspace. No binary, credential, or account is needed in the repository.

## Manual installation (Linux, macOS, or WSL)

From this directory:

```sh
# Linux/GNU tar: do not preserve macOS archive ownership in root containers.
case "$(uname -s)" in
  Linux) TAR_OPTIONS='--no-same-owner --warning=no-unknown-keyword' sh install.sh ;;
  *) sh install.sh ;;
esac
export PATH="$HOME/.bend/bin:$PATH"
export BEND_NO_TELEMETRY=1
bend guide
python3 ../../tests/test_bend_experiment.py
```

Add the PATH line to your shell configuration for later sessions. `install.sh`
is the upstream installer from <https://bend-lang.com/install.sh>, captured at
version 2.0.37 on 2026-10-20. It verifies release archive SHA-256 checksums and
installs under `~/.bend` without sudo. Re-running installs the same pinned
version. Updating this version and its checksums is an explicit repository
change; `bend update` may change a workspace installation independently.
The upstream daily version-check request is disabled by `BEND_NO_TELEMETRY=1`
in the configured Codespace and CI. Manual users should set it as shown above.

## Files and checks

- `AGENTS.md` scopes Bend instructions to this experiment.
- `Demo.bend` contains the example function; running it returns `42n`.
- `LAWS.bend` states the law; `PROOF.bend` proves it.
- `tests/test_bend_experiment.py` runs the example and standard proof check,
  then verifies that a temporary incorrect implementation is rejected. The
  source files stay unchanged. These standard-library tests also run without
  pytest; the main Python suite skips them when optional Bend is absent.
- `.github/workflows/bend-proof.yml` runs those checks for relevant changes
  and can also be started manually from Actions.

Run `bend PROOF.bend` before committing Bend changes. Change laws only after
reviewing their intended meaning; do not weaken a law to make a proof pass.
Use parallel calls for suitable independent work. This identity smoke test has
no workload worth parallelizing and makes no performance claim.

For the additional independent BendTT kernel check, install **Lean v4.34.0**
separately and run `bend PROOF.bend --verdict`. That check is not part of this
minimal setup; the standard checker is the CI check. Neither result proves
the correctness of Metis behavior outside the specified Bend law. Native
compilation and GPU execution need additional compiler/CUDA tooling and have
not been exercised by this setup.
