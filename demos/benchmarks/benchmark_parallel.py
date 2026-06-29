#!/usr/bin/env python
"""
Benchmark script to test MPI scaling performance for RACOON simulations.

This script runs the same simulation with different numbers of MPI ranks
and records the execution time for each configuration.

Usage:
    cd demos/benchmarks
    python benchmark_parallel.py
"""

import sys
import os
import json
import time
from datetime import datetime

# Add parent directory to path to import compgen
sys.path.append("../..")

from compgen import runner


def load_and_modify_config(base_config_path, rank_count):
    """
    Load a config file and modify the MPI rank count.
    
    Args:
        base_config_path (str): Path to the base configuration file
        rank_count (int): Number of MPI ranks to use
        
    Returns:
        dict: Modified configuration dictionary
    """
    with open(base_config_path, 'r') as f:
        config = json.load(f)
    
    # Modify the MPI ranks
    if "mpi" not in config:
        config["mpi"] = {}
    config["mpi"]["ranks"] = str(rank_count)
    
    return config


def write_benchmark_results(results, output_file="benchmark_results.txt"):
    """
    Write benchmark results to a text file.
    
    Args:
        results (list): List of tuples (rank_count, execution_time)
        output_file (str): Path to output file
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with open(output_file, 'a') as f:
        f.write("=" * 60 + "\n")
        f.write(f"Benchmark Run: {timestamp}\n")
        f.write("=" * 60 + "\n")
        f.write(f"{'MPI Ranks':<12} | {'Execution Time (seconds)':<30}\n")
        f.write("-" * 60 + "\n")
        
        for rank_count, exec_time in results:
            if exec_time is not None:
                f.write(f"{rank_count:<12} | {exec_time:<30.2f}\n")
            else:
                f.write(f"{rank_count:<12} | {'FAILED':<30}\n")
        
        f.write("\n")


def run_benchmark(rank_counts=[1, 2, 8, 32]):
    """
    Run benchmark tests with different MPI rank counts.
    
    Args:
        rank_counts (list): List of MPI rank counts to test
        
    Returns:
        list: List of tuples (rank_count, execution_time)
    """
    print("=" * 70)
    print("MPI Scaling Benchmark for RACOON Simulations")
    print("=" * 70)
    print()
    
    results = []
    
    for rank_count in rank_counts:
        print(f"Running benchmark with {rank_count} MPI rank(s)...")
        print("-" * 70)
        
        try:
            # Load and modify the machine config
            machine_config = load_and_modify_config(
                "benchmark_machine_config.json", 
                rank_count
            )
            
            # Write temporary modified config
            temp_config_path = f"temp_machine_config_{rank_count}.json"
            with open(temp_config_path, 'w') as f:
                json.dump(machine_config, f, indent=4)
            
            # Time the execution
            start_time = time.time()
            
            # Run the simulation
            runner.run("benchmark_config.json", temp_config_path)
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            print(f"✓ Completed in {execution_time:.2f} seconds")
            print()
            
            results.append((rank_count, execution_time))
            
            # Clean up temporary config file
            os.remove(temp_config_path)
            
        except Exception as e:
            print(f"✗ Failed with error: {str(e)}")
            print()
            results.append((rank_count, None))
            
            # Try to clean up temporary config if it exists
            temp_config_path = f"temp_machine_config_{rank_count}.json"
            if os.path.exists(temp_config_path):
                os.remove(temp_config_path)
    
    return results


def main():
    """Main function to run the benchmark suite."""
    print()
    print("Starting MPI scaling benchmark...")
    print()
    
    # Define the rank counts to test
    rank_counts = [1, 2, 8, 32]
    
    # Run the benchmarks
    results = run_benchmark(rank_counts)
    
    # Write results to file
    write_benchmark_results(results)
    
    # Print summary
    print("=" * 70)
    print("Benchmark Summary")
    print("=" * 70)
    print(f"{'MPI Ranks':<12} | {'Execution Time (seconds)':<30}")
    print("-" * 70)
    
    for rank_count, exec_time in results:
        if exec_time is not None:
            print(f"{rank_count:<12} | {exec_time:<30.2f}")
        else:
            print(f"{rank_count:<12} | {'FAILED':<30}")
    
    print()
    print("Results written to: benchmark_results.txt")
    print("Simulation outputs saved in: results/")
    print()


if __name__ == "__main__":
    main()