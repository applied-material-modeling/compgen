#!/bin/bash
# Script to update the g++ wrapper with logging on HPC
# Run this on the HPC system after copying it there

cat > ~/bin/g++-wrapped << 'EOF'
#!/bin/bash
# Log every invocation to debug if libMesh is actually calling this wrapper
echo "$(date '+%Y-%m-%d %H:%M:%S'): g++-wrapped called with args: $*" >> /tmp/g++-wrapped-${SLURM_JOB_ID:-manual}.log
echo "PWD: $PWD" >> /tmp/g++-wrapped-${SLURM_JOB_ID:-manual}.log

# Execute the real g++ with corrected include paths
exec /users/rghill/miniconda3/envs/racoon/bin/g++ \
  -I/users/rghill/miniconda3/envs/racoon/lib/gcc/x86_64-conda-linux-gnu/14.3.0/include/c++ \
  -I/users/rghill/miniconda3/envs/racoon/x86_64-conda-linux-gnu/sysroot/usr/include \
  -L/users/rghill/miniconda3/envs/racoon/lib \
  -Wl,-rpath,/users/rghill/miniconda3/envs/racoon/lib \
  "$@"
EOF

chmod +x ~/bin/g++-wrapped
echo "Updated ~/bin/g++-wrapped with logging"
