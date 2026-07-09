#!/bin/bash
# Test JIT with correct MOOSE syntax

source ~/miniconda3/etc/profile.d/conda.sh
conda activate racoon
module load cray-mpich

# Set up our PATH wrapper
export PATH="$HOME/.local/compiler-wrappers:$PATH"

# Create a test that DEFINITELY forces JIT compilation
cat > /tmp/test_jit_correct.i << 'EOF'
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

[AuxVariables]
  [dummy]
  []
[]

[Materials]
  [test]
    type = DerivativeParsedMaterial
    property_name = test_prop
    expression = 'x^2 + y^2'  # Use caret for power, not *
    outputs = exodus
  []
[]

[Problem]
  solve = false
[]

[Executioner]
  type = Steady
[]

[Outputs]
  exodus = false
  console = true
[]
EOF

echo "=== Testing RACCOON with correct JIT syntax ==="
echo ""

# Run RACCOON
/users/rghill/racoon/raccoon/raccoon-opt -i /tmp/test_jit_correct.i 2>&1

echo ""
echo "=== Check for wrapper logs ==="
ls -la /tmp/*wrapper*.log 2>/dev/null || echo "No wrapper logs found"
