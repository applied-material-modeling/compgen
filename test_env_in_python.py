#!/usr/bin/env python3
"""Test script to verify environment variables are accessible in Python"""
import os
import sys

print("=== Testing environment access in Python ===")
print(f"Python: {sys.executable}")
print(f"CONDA_PREFIX: {os.environ.get('CONDA_PREFIX', 'NOT SET')}")
print(f"LIBMESH_CXX: {os.environ.get('LIBMESH_CXX', 'NOT SET')}")
print(f"LIBMESH_CXXFLAGS: {os.environ.get('LIBMESH_CXXFLAGS', 'NOT SET')}")

if 'CONDA_PREFIX' in os.environ:
    conda_prefix = os.environ['CONDA_PREFIX']
    print(f"\nChecking conda g++:")
    gxx_path = f"{conda_prefix}/bin/g++"
    import os.path
    print(f"  Path: {gxx_path}")
    print(f"  Exists: {os.path.exists(gxx_path)}")

    if os.path.exists(gxx_path):
        import subprocess
        try:
            version = subprocess.check_output([gxx_path, "-dumpversion"], text=True).strip()
            print(f"  Version: {version}")
        except Exception as e:
            print(f"  ERROR getting version: {e}")
