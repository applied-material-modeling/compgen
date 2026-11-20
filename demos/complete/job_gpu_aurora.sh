#!/bin/bash -l
# Copyright 2026, UChicago Argonne, LLC
# All Rights Reserved
# Software Name: compgen
# By: Argonne National Laboratory
# OPEN SOURCE LICENSE (MIT), see LICENSE
#
# Run a compgen demo in MOOSE gpu mode on one Aurora node (12 GPU tiles).
#
# machine_config_aurora_gpu.json (used in place of machine_config.json) runs 12 structures at
# a time, one MOOSE rank per tile. For larger meshes, use fewer concurrent runs with more ranks
# each, e.g. "nthreads": 3 and "gpu": {"ranks_per_run": 4}. nthreads x ranks_per_run must be
# <= 12.
#
# Usage: qsub -A <project> -v DEMO=elasticity/2d demos/complete/job_gpu_aurora.sh
#
#PBS -l select=1
#PBS -l walltime=01:00:00
#PBS -l filesystems=flare
#PBS -l place=scatter
#PBS -q debug
#PBS -N compgen_gpu

# Environment with the GPU build of MOOSE (Kokkos/SYCL, libtorch XPU, NEML2) and its PETSc;
# adjust these for your installation.
source "${COMPGEN_ENV:-/lus/flare/projects/ai4ns-composites/new-packages/activate}"
export MOOSE_DIR="${MOOSE_DIR:-/lus/flare/projects/ai4ns-composites/new-packages/moose}"
export CUBIT_DIR="${CUBIT_DIR:-/lus/flare/projects/ai4ns-composites/new-packages/Cubit-16.08}"

cd "${PBS_O_WORKDIR:-.}"
DEMO="${DEMO:-elasticity/2d}"
physics_dir=$(dirname "demos/complete/${DEMO}")
physics_config=$(ls "${physics_dir}"/*_config.json | grep -v parallel_config)

python - "${DEMO}" "${physics_config}" <<'PYEOF'
import sys
from compgen import runner

demo, physics_config = sys.argv[1:]
runner.run(
    f"demos/complete/{demo}/demo.json",
    physics_config,
    "demos/complete/machine_config_aurora_gpu.json",
)
PYEOF
