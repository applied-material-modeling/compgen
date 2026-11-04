# Aurora checklist - random-material sweep

Total samples produced = (select nodes) x (number in config_fracture.json).
For the one-node debug run: select=1 x number=8 = 8 samples (subject to the one-hour walltime).

- `fracture/aurora/2d_random/config_fracture.json`:
	- Set `number` (samples PER NODE) for the total you want (total = select x number).
	- Set `output.output_dir`.
	- Optionally adjust material sampling ranges (see fracture_random_ranges.md).
	  Note: `l` is `{"fixed": ...}` and shared between A/B - keep it mesh-resolved.
- `fracture/aurora/2d_random/config_machine.json`:
	- Set log dir in the `log_file` entry (currently .../logs/random/).
- `fracture/aurora/2d_random/submit_job.sh`:
	- select = number of nodes.
	- walltime = proper time.
	- -q proper queue (debug for the small run; prod/capacity for larger).
	- -A proper project/allocation.
	- JOB_#.out and JOB_#.err specify job number (if you add -o/-e).
- Before submitting the full run, try `fracture/aurora/2d_random/submit_job_debug.sh`:
	- This requests one node for one hour on the `debug` queue.
	- The run may stop when the one-hour walltime is reached; that is expected for this check.
- `fracture/aurora/2d_random/dummy_dsh.sh`:
	- Change the log directory (currently .../logs/random/).
- racoon.py:
	- Timeout for how long raccoon will run. In development. Currently at 24 hours. timeout=86400
- After the run:
	- Confirm `select x number` unique fracture_random_*.h5 files landed in output_dir.
	- Each .h5 has a `material_properties` group recording the drawn A/B/AB values.
	- Check a healthy fraction actually fractured (inspect_h5.py / plot_results.py).
	  If too few crack, narrow the `psic` range or raise `end_time` (5% strain now).
