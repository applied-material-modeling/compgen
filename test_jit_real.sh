#!/bin/bash
# Test JIT compilation with actual RACCOON materials that trigger it

source ~/miniconda3/etc/profile.d/conda.sh
conda activate racoon
module load cray-mpich

# Verify mpicxx wrapper is first in PATH
export PATH="$HOME/.local/compiler-wrappers:$PATH"
echo "=== PATH check ==="
echo "which mpicxx: $(which mpicxx)"
echo "PATH: $PATH" | head -c 200
echo ""

# Create a test using actual RACCOON JIT materials
cat > /tmp/test_jit_real.i << 'EOF'
[Mesh]
  type = GeneratedMesh
  dim = 2
  nx = 2
  ny = 2
[]

[Variables]
  [d]
  []
[]

[Materials]
  # This DEFINITELY triggers JIT compilation
  [crack_geometric]
    type = CrackGeometricFunction
    property_name = alpha
    expression = d
    phase_field = d
  []

  [degradation]
    type = RationalDegradationFunction
    property_name = g
    phase_field = d
    parameter_names = 'p a2 a3 eta'
    parameter_values = '2.0 -0.5 0 1e-6'
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

echo "=== Testing RACCOON with JIT materials ==="
/users/rghill/racoon/raccoon/raccoon-opt -i /tmp/test_jit_real.i 2>&1 | tee /tmp/jit_test_output.txt

echo ""
echo "=== Check for mpicxx wrapper logs ==="
if ls /tmp/mpicxx-wrapper*.log 1> /dev/null 2>&1; then
    echo "WRAPPER WAS CALLED!"
    cat /tmp/mpicxx-wrapper*.log
else
    echo "No wrapper logs found - mpicxx was not called"
fi

echo ""
echo "=== Check for cmath errors ==="
grep -i "cmath" /tmp/jit_test_output.txt || echo "No cmath errors"
