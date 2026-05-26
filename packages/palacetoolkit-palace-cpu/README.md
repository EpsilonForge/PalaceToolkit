# palacetoolkit-palace-cpu

Platform wheel package that ships a prebuilt CPU-default Palace executable for PalaceToolkit.

## Build flow

1. Build Palace with the CPU-default profile.
2. Stage the resulting executable and shared libraries:
   - `tools/stage_palace_binary.sh /path/to/palace /path/to/libdir`
   - This populates:
     - `src/palacetoolkit_palace_cpu/bin/palace`
     - `src/palacetoolkit_palace_cpu/lib/*`
3. Build wheel:
   - `python -m build`

## Notes

- This package is intended to be built in CI per platform/architecture.
- PalaceToolkit discovers this binary automatically via importlib resources.
