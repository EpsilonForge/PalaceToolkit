#!/usr/bin/env python3
"""Patch MFEM CMakeLists.txt for MinGW/Windows builds.

Runs in the MFEM source directory (cwd set by ExternalProject's PATCH_COMMAND).
Does two things:

1. Stubs out ``examples/CMakeLists.txt`` so no example targets are built.
   CMake 4.x's Ninja generator rejects duplicate target names that arise
   from MFEM's example subdirectory.

2. Strips ``add_dependencies()`` lines referencing the ``check`` target
   from the top-level ``CMakeLists.txt``.  The ``check`` target depends on
   example targets that no longer exist after step 1, which would cause
   a fatal CMake error at configure time.
"""

import os

# 1. Stub out examples/CMakeLists.txt
os.makedirs("examples", exist_ok=True)
with open("examples/CMakeLists.txt", "w", newline="\n") as f:
    f.write("cmake_minimum_required(VERSION 3.16)\nreturn()\n")

# 2. Remove add_dependencies lines that reference 'check'
with open("CMakeLists.txt", "r") as f:
    lines = f.readlines()

filtered = [
    line
    for line in lines
    if not ("add_dependencies" in line and "check" in line)
]

with open("CMakeLists.txt", "w") as f:
    f.writelines(filtered)

print(f"fix_mfem.py: removed {len(lines) - len(filtered)} add_dependencies/check lines")
