#!/bin/bash

#PBS -A AISim4NS 
#PBS -N compgen_raccoon
#PBS -l select=1
#PBS -l walltime=01:00:00
#PBS -k doe
#PBS -l place=scatter
#PBS -q debug
#PBS -l filesystems=home_fs
#PBS -o JOB_${PBS_JOBID}.out
#PBS -e JOB_${PBS_JOBID}.err
#PBS -M bbrunsvik@lanl.gov

### INFO
# Submit this script with: qsub run_pbs.sh
# More info on PBS with Aurora: https://docs.alcf.anl.gov/running-jobs/#qsub-submit-a-job-to-run

# Available filesystems: 
    # resources_available.valid_filesystems = home_fs,flare_fs,daos_user_fs,
    #     daos_perf_fs,daos_ops_fs
### INFO end

### TODO
# - Need to figure out which filesystem we are supposed to use. I think flare is full. 
### TODO end

### TEST
echo "Hello world" 
### TEST end

### Run Compgen 
# # Change to the directory from which the job was submitted
# cd $PBS_O_WORKDIR

# # Initialize the conda environment for python scripts
# module load miniconda3 
# conda activate /home/bbrunsvik/environments/moose/bin

# # The python script will use multiprocess internally to map jobs over the PBS environment
# python aurora_run_fracture_predefined.py