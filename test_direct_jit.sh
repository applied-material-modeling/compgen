#!/bin/bash
# Test if we can manually trigger a JIT compilation to see what compiler it uses

source ~/miniconda3/etc/profile.d/conda.sh
conda activate racoon
module load cray-mpich

# Set up our PATH wrapper
export PATH="$HOME/.local/compiler-wrappers:$PATH"

# Create a minimal test that forces JIT compilation
cat > /tmp/test_jit_minimal.i << 'EOF'
[Mesh]
  type = GeneratedMesh
  dim = 2
  nx = 2
  ny = 2
[]

[Variables]
  [u]
  []
[]

[Materials]
  [test]
    type = ADDerivativeParsedMaterial
    property_name = test_prop
    expression = 'x*x + y*y'  # Simple expression that requires JIT
    coupled_variables = 'u'
  []
[]

[Problem]
  solve = false
[]

[Executioner]
  type = Steady
[]

[Outputs]
  console = true
[]
EOF

echo "=== Testing RACCOON with JIT material ==="
echo "PATH includes wrapper: $PATH"
echo "Running RACCOON..."
echo ""

# Run with strace to see what compiler it tries to execute
/users/rghill/racoon/raccoon/raccoon-opt -i /tmp/test_jit_minimal.i 2>&1 | head -50

echo ""
echo "=== Check for wrapper logs ==="
ls -la /tmp/*wrapper*.log 2>/dev/null || echo "No wrapper logs found"
if [ -f /tmp/path-g++-wrapper-manual.log ]; then
    echo "Wrapper was called:"
    cat /tmp/path-g++-wrapper-manual.log
fi
