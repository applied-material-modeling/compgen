# MPI Scaling Benchmark

This directory contains scripts for benchmarking MPI scaling performance of RACOON simulations.

## Files

- **benchmark_parallel.py**: Main benchmarking script that tests different MPI rank counts
- **run_benchmark_slurm.sh**: SLURM submission script for running on MADA cluster
- **benchmark_config.json**: Problem configuration (based on fracture_predefined_slurm.json)
- **benchmark_machine_config.json**: Machine configuration (based on machine_config_slurm.json)
- **benchmark_results.txt**: Output file with timing results (created after running)
- **results/**: Directory containing simulation outputs (created after running)

## Usage

### On SLURM Systems (MADA):

```bash
cd demos/benchmarks
sbatch run_benchmark_slurm.sh
```

Monitor your job with:
```bash
squeue -u $USER
```

Check results after completion:
```bash
cat benchmark_results.txt
```

### Interactive/Local Run:

```bash
cd demos/benchmarks
python benchmark_parallel.py
```

## What It Does

The script will:
1. Run the same RACOON fracture simulation 4 times with different MPI configurations:
   - 1 MPI rank
   - 2 MPI ranks
   - 8 MPI ranks
   - 32 MPI ranks

2. Time each execution and record results

3. Save timing data to `benchmark_results.txt`

4. Keep all simulation outputs in `results/` for inspection

## Configuration

The benchmark uses:
- **nthreads = 1**: Sequential structure processing (to isolate MPI performance)
- **number = 1**: Single structure simulation per test
- **Variable MPI ranks**: Tests scaling with 1, 2, 8, and 32 processes

## Understanding Results

The timing results will help you understand:
- Whether your simulations benefit from MPI parallelization
- The optimal number of MPI ranks for your problem size
- If there's overhead or diminishing returns with higher rank counts

Expected behavior:
- **Linear scaling**: Time cuts in half when doubling ranks (ideal)
- **Sublinear scaling**: Some speedup but less than ideal (common)
- **No speedup**: Problem may be too small or communication-bound