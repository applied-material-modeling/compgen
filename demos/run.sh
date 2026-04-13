#!/bin/bash

# Submit this script with: sbatch run.sh

#SBATCH --time=00:01:00
#SBATCH -N 4
#SBATCH --job-name=example_test
#SBATCH --output=JOB_%j.out
#SBATCH --error=JOB_%j.err
#SBATCH --mail-user=rghill@lanl.gov
#SBATCH --mail-type=BEGIN
#SBATCH --mail-type=END
#SBATCH --mail-type=FAIL
#SBATCH --signal=23@60
#SBATCH --reservation=debug
##SBATCH --qos=standard

# module purge
# module load PrgEnv-intel
# module swap cray-mpich/8.1.28.1 cray-mpich/8.1.25
# module list

# export PATH=/usr/projects/packages/erougier/HOSS_FSIS_2020/cray:$PATH
# export LD_LIBRARY_PATH=/usr/projects/packages/erougier/HOSS_FSIS_2020/cray:$LD_LIBRARY_PATH
# export PATH=/usr/projects/packages/erougier/HOSScom:$PATH
# export LD_LIBRARY_PATH=/usr/projects/packages/erougier/HOSScom:$LD_LIBRARY_PATH

echo HI > test.txt

#srun -n 433 HOSS_rls