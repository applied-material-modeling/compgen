#!/bin/bash
# Update raccoon-wrapper to use mpicxx wrapper for JIT

cat > ~/bin/raccoon-wrapped << 'EOF'
#!/bin/bash
# Wrapper script for RACCOON that ensures JIT compiler is configured

# Detect conda environment
if [ -z "$CONDA_PREFIX" ]; then
    echo "ERROR: CONDA_PREFIX not set. Activate conda environment first." >&2
    exit 1
fi

# DON'T set LIBMESH_CXX or LIBMESH_CXXFLAGS here
# Instead, ensure our mpicxx wrapper is first in PATH
export PATH="$HOME/.local/compiler-wrappers:$PATH"

# Debug output
echo "[RACCOON Wrapper] PATH set to include compiler wrappers" >&2
echo "[RACCOON Wrapper] which mpicxx: $(which mpicxx)" >&2

# Execute the real RACCOON with all arguments
exec /users/rghill/racoon/raccoon/raccoon-opt "$@"
EOF

chmod +x ~/bin/raccoon-wrapped
echo "Updated raccoon-wrapped to use PATH-based mpicxx wrapper"
