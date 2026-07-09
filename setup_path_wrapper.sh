#!/bin/bash
# Create wrapper scripts that intercept compiler calls via PATH

# Create a directory for our wrappers
mkdir -p ~/.local/compiler-wrappers

# Create a g++ wrapper that logs and fixes includes
cat > ~/.local/compiler-wrappers/g++ << 'EOF'
#!/bin/bash
echo "$(date '+%Y-%m-%d %H:%M:%S'): PATH g++ wrapper called with args: $*" >> /tmp/path-g++-wrapper-${SLURM_JOB_ID:-manual}.log
echo "Called from: $(caller)" >> /tmp/path-g++-wrapper-${SLURM_JOB_ID:-manual}.log
echo "PWD: $PWD" >> /tmp/path-g++-wrapper-${SLURM_JOB_ID:-manual}.log
echo "---" >> /tmp/path-g++-wrapper-${SLURM_JOB_ID:-manual}.log

# Execute the real conda g++ with corrected include paths
exec /users/rghill/miniconda3/envs/racoon/bin/g++ \
  -I/users/rghill/miniconda3/envs/racoon/lib/gcc/x86_64-conda-linux-gnu/14.3.0/include/c++ \
  -I/users/rghill/miniconda3/envs/racoon/x86_64-conda-linux-gnu/sysroot/usr/include \
  -L/users/rghill/miniconda3/envs/racoon/lib \
  -Wl,-rpath,/users/rghill/miniconda3/envs/racoon/lib \
  "$@"
EOF

# Also create gcc and c++ wrappers in case libMesh tries those
cat > ~/.local/compiler-wrappers/gcc << 'EOF'
#!/bin/bash
echo "$(date '+%Y-%m-%d %H:%M:%S'): PATH gcc wrapper called with args: $*" >> /tmp/path-gcc-wrapper-${SLURM_JOB_ID:-manual}.log
exec /users/rghill/miniconda3/envs/racoon/bin/gcc "$@"
EOF

cat > ~/.local/compiler-wrappers/c++ << 'EOF'
#!/bin/bash
echo "$(date '+%Y-%m-%d %H:%M:%S'): PATH c++ wrapper called with args: $*" >> /tmp/path-c++-wrapper-${SLURM_JOB_ID:-manual}.log
exec /users/rghill/miniconda3/envs/racoon/bin/c++ \
  -I/users/rghill/miniconda3/envs/racoon/lib/gcc/x86_64-conda-linux-gnu/14.3.0/include/c++ \
  -I/users/rghill/miniconda3/envs/racoon/x86_64-conda-linux-gnu/sysroot/usr/include \
  -L/users/rghill/miniconda3/envs/racoon/lib \
  -Wl,-rpath,/users/rghill/miniconda3/envs/racoon/lib \
  "$@"
EOF

chmod +x ~/.local/compiler-wrappers/g++
chmod +x ~/.local/compiler-wrappers/gcc
chmod +x ~/.local/compiler-wrappers/c++

echo "Created compiler wrappers in ~/.local/compiler-wrappers/"
echo ""
echo "Add this to your Slurm script BEFORE running Python:"
echo "export PATH=\"\$HOME/.local/compiler-wrappers:\$PATH\""
