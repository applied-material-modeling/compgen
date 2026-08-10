"""Shared pytest configuration for the test suite."""

import os

# Force CPU for the test suite. TensorFlow's GPU XLA JIT fails to compile the
# Exp op in mcrpy's descriptor path (TwoPointCorrelations), which breaks the
# reconstruction tests. CPU execution is correct and deterministic. This must
# run before TensorFlow is imported, so it lives at the top of conftest.py.
# Use setdefault so a GPU run is still possible via CUDA_VISIBLE_DEVICES=0 pytest.
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
