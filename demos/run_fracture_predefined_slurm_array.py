import json
import os
from pathlib import Path
import sys
import tempfile

import numpy as np


DEMO_DIR = Path(__file__).resolve().parent
REPOSITORY_DIR = DEMO_DIR.parent
sys.path.insert(0, str(REPOSITORY_DIR))

from compgen import runner


def load_config(path):
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def write_config(path, config):
    with path.open("w", encoding="utf-8") as stream:
        json.dump(config, stream, indent=4)


def main():
    task_id = int(os.environ.get("SLURM_ARRAY_TASK_ID", "0"))
    array_job_id = os.environ.get("SLURM_ARRAY_JOB_ID", "manual")
    runs_per_task = int(os.environ.get("COMPGEN_RUNS_PER_TASK", "1"))
    threads_per_task = int(os.environ.get("COMPGEN_THREADS_PER_TASK", "1"))
    base_seed = int(os.environ.get("COMPGEN_BASE_SEED", "20260720"))
    random_seed = base_seed + task_id * runs_per_task

    if runs_per_task < 1:
        raise ValueError("COMPGEN_RUNS_PER_TASK must be at least 1")
    if threads_per_task < 1 or threads_per_task > runs_per_task:
        raise ValueError(
            "COMPGEN_THREADS_PER_TASK must be between 1 and "
            "COMPGEN_RUNS_PER_TASK"
        )

    problem_config = load_config(DEMO_DIR / "fracture_predefined_slurm.json")
    machine_config = load_config(DEMO_DIR / "machine_config_slurm.json")

    problem_config["number"] = runs_per_task
    problem_config["nthreads"] = threads_per_task
    problem_config["generator"]["params"]["random_seed"] = random_seed

    # Multiple independent mpiexec instances share this node. Disable each
    # launcher's private binding policy and let Slurm's job cpuset and the
    # operating system schedule the ranks across the reserved physical cores.
    machine_config["sculpt"]["mpi_extra_args"] = ["--bind-to", "none"]
    machine_config["mpi"]["extra_args"] = ["--bind-to", "none"]

    output_dir = Path(
        os.environ.get("COMPGEN_OUTPUT_DIR", str(DEMO_DIR / "output"))
    ).resolve()
    log_dir = Path(
        os.environ.get("COMPGEN_LOG_DIR", str(DEMO_DIR / "logs"))
    ).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    problem_config["output"]["output_dir"] = str(output_dir)
    machine_config["log_file"] = str(
        log_dir / f"compgen_{array_job_id}_{task_id}.log"
    )

    # The fracture generator uses NumPy's global RNG, while the structure
    # generator uses the explicit random_seed stored in its configuration.
    np.random.seed(random_seed)

    slurm_tmpdir = os.environ.get("SLURM_TMPDIR")
    temporary_parent = (
        slurm_tmpdir
        if slurm_tmpdir and os.path.isdir(slurm_tmpdir)
        else None
    )
    with tempfile.TemporaryDirectory(
        prefix=f"compgen-{array_job_id}-{task_id}-",
        dir=temporary_parent,
    ) as temporary_directory:
        temporary_path = Path(temporary_directory)
        problem_path = temporary_path / "problem.json"
        machine_path = temporary_path / "machine.json"
        write_config(problem_path, problem_config)
        write_config(machine_path, machine_config)

        print(
            f"Starting array task {task_id}: {runs_per_task} simulations, "
            f"{threads_per_task} workers, random seed {random_seed}",
            flush=True,
        )
        results = runner.run(str(problem_path), str(machine_path))

    if any(isinstance(result, int) and result == -1 for result in results):
        raise RuntimeError(f"CompGen array task {task_id} failed")

    print(f"CompGen array task {task_id} completed successfully", flush=True)


if __name__ == "__main__":
    main()
