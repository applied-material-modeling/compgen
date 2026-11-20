#!/usr/bin/env bash
# Copyright 2026, UChicago Argonne, LLC
# All Rights Reserved
# Software Name: compgen
# By: Argonne National Laboratory
# OPEN SOURCE LICENSE (MIT), see LICENSE
#
# Pin each MPI rank of one MOOSE run to its own GPU device, then exec the command.
#
#   device = COMPGEN_DEVICE_OFFSET + <node-local rank>
#
# and the device is exposed through the environment variable named by
# COMPGEN_VISIBLE_DEVICES_ENV (default ZE_AFFINITY_MASK on Intel GPUs; CUDA_VISIBLE_DEVICES or
# ROCR_VISIBLE_DEVICES elsewhere). compgen sets both variables so concurrent runs on one node
# use disjoint device blocks. Modeled on Aurora's gpu_tile_compact.sh.
#
# Usage: mpiexec -n N bash gpu_bind.sh <command> [args...]

offset=${COMPGEN_DEVICE_OFFSET:-0}
var=${COMPGEN_VISIBLE_DEVICES_ENV:-ZE_AFFINITY_MASK}

local_rank=${PALS_LOCAL_RANKID:-${MPI_LOCALRANKID:-${OMPI_COMM_WORLD_LOCAL_RANK:-${SLURM_LOCALID:-0}}}}

export "${var}=$((offset + local_rank))"

# Intel GPUs: disable implicit scaling so each device is exactly one tile
export EnableImplicitScaling=0

exec "$@"
