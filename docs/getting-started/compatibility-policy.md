# Compatibility Policy

This document defines the support contract between palace-toolkit and the
packaged Palace CPU binary.

## Stable Channel

- Stable `palace-toolkit` releases target stable `palacetoolkit-palace-cpu` releases.
- Binary wheels are built in GitHub Actions and attached to release tags
  `palace-cpu-v*`.
- Main `palace-toolkit` package artifacts are built from release tags `v*`.
- Stable behavior is defined by the matching stable binary line.

## Default Install Workflow

- Recommended install command:

  ```bash
  pip install palace-toolkit
  ```

- On Linux x86_64, this resolves the matching prebuilt
  `palacetoolkit-palace-cpu` wheel from GitHub Releases.
- Recommended post-install smoke test:

  ```bash
  palace-toolkit-check
  ```

## Local Clone Workflow (contributors)

- A local editable workflow is still supported for contributors and power users:

  ```bash
  ./tools/install_local_editable.sh
  ```

## Nightly and Custom Source Builds

- Source builds are opt-in and best-effort:

  ```bash
  PALACETOOLKIT_BUILD_PALACE=1 PALACETOOLKIT_CLONE_NIGHTLY=1 pip install -e .
  ```

- Custom CMake option sets (CUDA/HIP/MAGMA/etc.) are user-managed and outside
  stable compatibility guarantees.

## Support Scope

- Fully supported:
  - Stable PalaceToolkit + matching stable binary wheel.
  - Local clone install using the GA-built wheel path.
- Best-effort:
  - Nightly/custom source builds.
  - User-modified Palace build flags.
