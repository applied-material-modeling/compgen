#!/bin/bash
# Create mpicxx wrapper to redirect to conda's g++ for JIT compilation

mkdir -p ~/.local/compiler-wrappers

cat > ~/.local/compiler-wrappers/mpicxx << 'EOF'
#!/bin/bash
# Wrapper for mpicxx that redirects to conda's g++ with correct include paths
# This is needed because libMesh's JIT compiler is hardcoded to use "mpicxx"

# Log this call
echo "$(date '+%Y-%m-%d %H:%M:%S'): mpicxx wrapper called with args: $*" >> /tmp/mpicxx-wrapper-${SLURM_JOB_ID:-manual}.log
echo "PWD: $PWD" >> /tmp/mpicxx-wrapper-${SLURM_JOB_ID:-manual}.log
echo "---" >> /tmp/mpicxx-wrapper-${SLURM_JOB_ID:-manual}.log

# Use conda's g++ instead of Cray/Intel compiler
# Add the correct include paths for GCC's C++ standard library
exec /users/rghill/miniconda3/envs/racoon/bin/g++ \
  -I/users/rghill/miniconda3/envs/racoon/lib/gcc/x86_64-conda-linux-gnu/14.3.0/include/c++ \
  -I/users/rghill/miniconda3/envs/racoon/x86_64-conda-linux-gnu/sysroot/usr/include \
  -L/users/rghill/miniconda3/envs/racoon/lib \
  -Wl,-rpath,/users/rghill/miniconda3/envs/racoon/lib \
  "$@"
EOF

chmod +x ~/.local/compiler-wrappers/mpicxx

echo "Created mpicxx wrapper at ~/.local/compiler-wrappers/mpicxx"
echo ""
echo "This wrapper will redirect libMesh's JIT compiler from Cray/Intel mpicxx"
echo "to conda's g++ with the correct C++ header paths."
