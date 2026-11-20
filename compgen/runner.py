# Copyright 2026, UChicago Argonne, LLC
# All Rights Reserved
# Software Name: compgen
# By: Argonne National Laboratory
# OPEN SOURCE LICENSE (MIT)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

# pylint: disable=broad-exception-caught, too-many-branches, too-many-statements, too-many-locals, too-many-return-statements, too-many-lines
"""High-level orchestration for generating structures, meshing, solving, and writing outputs."""

import os
import uuid
import queue
import importlib
import inspect
import logging
import time

import numpy as np
import multiprocess

from compgen import temp, hdfwriter, utils, mesh, filters

logger = logging.getLogger(__name__)


# Readable names for failure stages in the run summary.
_STAGE_LABELS = {
    "filter": "filter error",
    "sculpt": "Sculpt failed",
    "mesher-other": "other mesher error",
    "quality": "mesh check failed",
    "non-finite": "NaN/inf node coordinates",
    "jacobian": "min scaled Jacobian <= 0.1",
    "snap-flat": "snap: face not flat",
    "snap-count": "snap: node counts differ",
    "snap-pairing": "snap: nodes not one-to-one",
    "snap-topology": "snap: face sides differ",
    "snap-move": "snap: move above cap",
    "executor": "solver did not finish",
    "extractor-setup": "grid extractor setup",
    "grid-extraction": "grid extraction",
    "write-output": "writing output",
}


# Sentinels for the two failure modes run_single can report. MESH_FAILED
# (sculpt / post-mesh checks / mesh-prep) is backfilled by drawing a new structure;
# EXEC_FAILED (executor, e.g. MOOSE) consumes a slot and is dropped.
#
# These must survive being pickled back from a multiprocess.Pool worker, so they
# are class instances identified by a `.kind` attribute (NOT bare `object()`
# compared with `is` -- identity does not survive pickling, which silently turned
# parallel failures into phantom "successes").
class _Failure:  # pylint: disable=too-few-public-methods
    """Sentinel marking a failed run_single attempt (pickling-safe).

    `stage` names the step that failed (e.g. "sculpt", "executor"); it only feeds
    the end-of-run summary.
    """

    def __init__(self, kind, stage=None):
        self.kind = kind
        self.stage = stage


MESH_FAILED = _Failure("mesh")
EXEC_FAILED = _Failure("exec")

# Filter errors that cannot be fixed by redrawing: the filter params and the image
# shape both come from the config. Third-party filters opt in via FilterInputError;
# TypeError catches a misspelled entry in a filter's `params`.
_FATAL_FILTER_ERRORS = (filters.FilterInputError, TypeError)


def _is_mesh_failure(r):
    return isinstance(r, _Failure) and r.kind == "mesh"


def _is_exec_failure(r):
    return isinstance(r, _Failure) and r.kind == "exec"


def _run_single_star(args):
    """Unpack a (img, matA, matB, matAB, config) tuple for use with a Pool.

    Returns:
        tuple: (run_single result, wall time in seconds).
    """
    t0 = time.perf_counter()
    res = run_single(*args)
    return res, time.perf_counter() - t0


def _fmt_seconds(sec):
    """Format a duration as e.g. '1h 02m 03.4s', '2m 03.4s' or '3.4s'."""
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h >= 1:
        return f"{int(h)}h {int(m):02d}m {s:04.1f}s"
    if m >= 1:
        return f"{int(m)}m {s:04.1f}s"
    return f"{s:.1f}s"


class _RunStats:  # pylint: disable=too-many-instance-attributes
    """Counters and timings collected by run() for the end-of-run summary."""

    def __init__(self, config_files):
        self.config_files = config_files
        self.t_start = time.perf_counter()
        self.t_compute = None  # set when computations start
        self.number = None
        self.nthreads = None
        self.cap = None
        self.predefined = False
        self.drawn = 0
        self.gen_failures = 0
        self.gen_time = 0.0
        self.worker_errors = 0
        self.failures = {"mesh": {}, "exec": {}}
        self.success_times = []
        self.attempt_time = 0.0
        self.load_cases = 0

    def record(self, result, elapsed):
        """Record one finished run_single attempt."""
        self.attempt_time += elapsed
        if isinstance(result, _Failure):
            stages = self.failures[result.kind]
            stage = result.stage or "unspecified"
            stages[stage] = stages.get(stage, 0) + 1
        else:
            self.success_times.append(elapsed)
            try:
                self.load_cases += len(result)
            except TypeError:
                pass

    def n_failed(self, kind):
        """Total failures of `kind` ("mesh" or "exec")."""
        return sum(self.failures[kind].values())

    def log_summary(self, config, error=None):
        """Write the multi-line summary to the log."""
        # pylint: disable=too-many-locals
        now = time.perf_counter()
        out = config.get("output", {})
        succeeded = len(self.success_times)
        attempts = succeeded + self.n_failed("mesh") + self.n_failed("exec")
        attempts += self.worker_errors

        # A slot is filled by a success or an executor failure (dropped, not
        # redrawn); predefined runs fill one slot per structure whatever happens.
        filled = attempts if self.predefined else succeeded + self.n_failed("exec")
        lost = attempts - succeeded if self.predefined else self.n_failed("exec")
        if error is not None:
            status = f"ABORTED ({type(error).__name__}: {error})"
        elif self.number is None or filled < self.number:
            status = "INCOMPLETE (attempt cap reached or generator exhausted)"
        elif lost:
            status = f"COMPLETE ({lost} structure(s) failed, no result)"
        else:
            status = "COMPLETE"

        def stage_lines(kind):
            """One indented line per failure stage, most frequent first."""
            stages = self.failures[kind]
            rows = sorted(stages.items(), key=lambda kv: (-kv[1], kv[0]))
            return [f"      {_STAGE_LABELS.get(k, k):<28}: {v}" for k, v in rows]

        def share(n):
            return (
                f" of {attempts} ({100 * n / attempts:.0f}%)" if attempts and n else ""
            )

        lines = [
            "=" * 64,
            "compgen run summary",
            "=" * 64,
            f"Status              : {status}",
            f"Config files        : {', '.join(self.config_files)}",
            f"Generator           : {config.get('generator', {}).get('type')}",
            f"Mesher              : {config.get('mesh', {}).get('type')}",
            f"Executor            : {config.get('executor', {}).get('type')}",
        ]
        if out.get("write_files", True):
            lines.append(
                f"Output              : {out.get('output_dir', 'output')}/"
                f"{out.get('output_prefix', 'result')}_*.h5"
            )
        else:
            lines.append("Output              : not written (write_files = false)")
        if self.number is not None:
            mode = "predefined, positional" if self.predefined else "backfilled"
            lines += [
                f"Requested           : {self.number} structures ({mode})",
                f"Threads             : {self.nthreads}",
                f"Attempt cap         : {self.cap}",
            ]
        lines += [
            "-" * 64,
            f"Succeeded           : {succeeded}"
            + (f"/{self.number}" if self.number is not None else "")
            + f" ({self.load_cases} load-case results)",
            f"Structures drawn    : {self.drawn}",
            f"  generation failed : {self.gen_failures}",
            f"  run attempts      : {attempts}",
            f"  mesh failed       : {self.n_failed('mesh')}{share(self.n_failed('mesh'))}"
            + ("" if self.predefined else " -> redrawn"),
            *stage_lines("mesh"),
            f"  executor failed   : {self.n_failed('exec')}{share(self.n_failed('exec'))}"
            " -> dropped",
            *stage_lines("exec"),
            f"  worker errors     : {self.worker_errors}",
            "-" * 64,
            f"Total wall time     : {_fmt_seconds(now - self.t_start)}",
        ]
        if self.t_compute is not None:
            wall = now - self.t_compute
            lines += [
                f"  setup             : {_fmt_seconds(self.t_compute - self.t_start)}",
                f"  computations      : {_fmt_seconds(wall)}",
                f"  structure gen.    : {_fmt_seconds(self.gen_time)}",
            ]
            if self.success_times:
                st = self.success_times
                lines.append(
                    f"Per success         : mean {_fmt_seconds(sum(st) / len(st))}, "
                    f"min {_fmt_seconds(min(st))}, max {_fmt_seconds(max(st))}"
                )
                lines.append(f"Wall time / success : {_fmt_seconds(wall / len(st))}")
            if self.nthreads and self.nthreads > 1 and wall > 0:
                busy = self.attempt_time / (wall * self.nthreads)
                lines.append(f"Worker utilization  : {100 * busy:.0f}%")
        lines.append("=" * 64)
        for line in lines:
            logger.info(line)


def get_object_from_module(name, prefix="compgen"):
    """Dynamically import an object from a module.

    Args:
        name (str): Object name in the format 'module.object', where `module` is a
            module of the `prefix` package (e.g. 'gen.SpinodalGenerator').
        prefix (str): Package the module is imported from. Defaults to 'compgen'.

    Returns:
        object: The imported object.
    """
    module_name, object_name = name.split(".")
    module = importlib.import_module(prefix + "." + module_name)
    return getattr(module, object_name)


def unique_id(directory=".", prefix="", suffix=""):
    """Generate a unique identifier for a file in a given directory.
    Args:
        directory (str): Directory to check for existing files. Defaults to current directory.
        prefix (str): Prefix for the filename. Defaults to empty string.
        suffix (str): Suffix for the filename. Defaults to empty string.

    Returns:
        str: A unique identifier string.
    """
    while True:
        uid = uuid.uuid4().hex
        test_file = os.path.join(directory, f"{prefix}_{uid}_{suffix}")
        if os.path.isfile(test_file):
            continue
        return uid


class MCRpyInfoFilter(logging.Filter):
    """Logging filter for MCRpy library (no info/debug log)"""

    def filter(self, record):
        if "mcrpy" in record.pathname.lower():
            return record.levelno >= logging.WARNING
        return True


def setup_logging(config):
    """Initialize root logger from config if not already initialized.

    Args:
        config (dict): Configuration dictionary, optionally containing 'log_file'
            and 'log_level'.

    Returns:
        bool: True if logging is enabled (i.e. 'log_file' is present in config).
    """
    if "log_file" not in config:
        return False

    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            filename=config["log_file"],
            level=(
                logging.DEBUG
                if config.get("log_level", "DEBUG") == "DEBUG"
                else logging.INFO
            ),
            format="%(asctime)s %(levelname)s:%(message)s",
        )

    # Apply filter for MCRpy
    if not any(
        isinstance(f, MCRpyInfoFilter) for h in root.handlers for f in h.filters
    ):
        filt = MCRpyInfoFilter()
        for h in root.handlers:
            h.addFilter(filt)

    return True


def run(*config_files):
    """Run a set of computations defined by input files

    Args:
        *config_files (str): Paths to JSON configuration files, merged in order
            (later files override earlier ones), e.g. a problem definition file
            followed by machine and solver configuration files.

    Returns:
        list: One entry per structure: the list of load-case results, or a negative
            failure code.
    """
    config = utils.load_json(config_files)

    log = setup_logging(config)
    stats = _RunStats(config_files)
    error = None
    try:
        return _run(config, config_files, log, stats)
    except BaseException as e:
        error = e
        raise
    finally:
        if log:
            stats.log_summary(config, error)


def _run(config, config_files, log, stats):
    """Body of run(); fills `stats` as it goes."""
    if log:
        logger.info("")
        logger.info(
            "Running compgen with configuration files: %s", ", ".join(config_files)
        )

    # Create the output directory if it doesn't exist
    write_files = config.get("output", {}).get("write_files", True)
    if write_files:
        output_info = config.get("output", {})
        output_dir = output_info.get("output_dir", "output")
        os.makedirs(output_dir, exist_ok=True)
        if log:
            logger.info("Output directory set to %s", output_dir)

    # Setup material and structure generator
    if log:
        logger.info("Setting up generator and materials")
    try:
        generator = setup_generator(config["generator"], config.get("dim"))
    except Exception as e:
        if log:
            logger.error("Error setting up generator: %s", str(e))
        raise e
    if log:
        logger.info("Generator set up successfully")

    n_gen, n_mesh, n_out = check_resolutions(config, generator)
    if log:
        logger.info(
            "Resolutions over the domain [0, L]: image N=%d -> N_mesh=%d -> N_out=%d",
            n_gen,
            n_mesh,
            n_out,
        )
        copies = orthogonal_copies(config)
        if copies > 1:
            logger.info(
                "make_orthogonal: the generated cell is mirrored into %d copies per "
                "side that fill the domain [0, L=%g]. Generator parameters (N=%d and "
                "every length) and filter lengths refer to the unreplicated cell, of "
                "side L/%d = %g; L, mesh.params.N and output N refer to the domain.",
                copies,
                config["L"],
                n_gen // copies,
                copies,
                config["L"] / copies,
            )

    try:
        material_a = setup_material(config["material_A"])
        material_b = setup_material(config["material_B"])
        # The interface material is only used by interface physics; default to an
        # empty one so other configs can omit it.
        material_ab = setup_material(
            config.get(
                "material_AB",
                {"type": "materials.FixedMaterialGenerator", "params": {}},
            )
        )
    except Exception as e:
        if log:
            logger.error("Error setting up materials: %s", str(e))
        raise e
    if log:
        logger.info("Materials set up successfully")

    # Resolve the filter chain up front: a bad `type` is a config error that would
    # otherwise fail identically on every draw, in a worker where it looks retryable.
    try:
        for filter_spec in config.get("filtering", []):
            get_object_from_module(filter_spec.get("type"))
    except Exception as e:
        if log:
            logger.error("Error resolving filters: %s", str(e))
        raise e

    if log:
        logger.info("Starting computations")
    stats.t_compute = time.perf_counter()

    number = config["number"]
    nthreads = config.get("nthreads", 1)
    # Predefined structures (e.g. FromNumpyGenerator) are a fixed list, not a
    # stream: redrawing after a mesh failure would wrap around and duplicate an
    # earlier structure. Draw each one exactly once instead.
    predefined = getattr(generator, "predefined", False)
    cap = number if predefined else config.get("max_attempts_factor", 3) * number
    stats.number, stats.nthreads, stats.cap = number, nthreads, cap
    stats.predefined = predefined
    if log:
        logger.info("Using %d threads for computation", nthreads)

    # Lazy, capped task source: draws (img, matA, matB, matAB) tuples on demand.
    # Materials are pulled in lockstep, only when a task is emitted. Generation
    # failures are swallowed and still count against the shared cap, so a flaky
    # generator can't loop forever.
    mats = zip(material_a, material_b, material_ab)

    def tasks():
        drawn = 0
        while drawn < cap:
            drawn += 1
            t0 = time.perf_counter()
            try:
                img = next(generator)
            except StopIteration:
                return
            except Exception as e:  # pylint: disable=broad-exception-caught
                stats.drawn += 1
                stats.gen_failures += 1
                stats.gen_time += time.perf_counter() - t0
                if log:
                    logger.error(
                        "Generation failed (attempt %d/%d), redrawing: %s",
                        drawn,
                        cap,
                        str(e),
                    )
                continue
            stats.drawn += 1
            stats.gen_time += time.perf_counter() - t0
            try:
                mat = next(mats)
            except StopIteration:
                return
            yield (img, mat[0], mat[1], mat[2], config)

    # Consume results until `number` meshes have succeeded (i.e. result is not
    # MESH_FAILED). MESH_FAILED keeps the source draining (implicit retry);
    # EXEC_FAILED still consumes a slot but is dropped from the output.
    def consume(out_iter):
        collected = []
        succeeded = 0
        for r, elapsed in out_iter:
            stats.record(r, elapsed)
            if _is_mesh_failure(r):
                continue
            collected.append(r)
            succeeded += 1
            if succeeded >= number:
                break
        if succeeded < number and log:
            logger.error(
                "Only %d/%d meshes succeeded within %d attempts.",
                succeeded,
                number,
                cap,
            )
        return collected

    # Pool path: bounded-window backfill. We keep at most `nthreads` tasks in
    # flight and, crucially, never let (successes + in_flight) exceed `number`.
    # That invariant guarantees that by the time we have `number` successes there
    # are zero tasks still running, so the pool drains via close()/join() with
    # nothing to kill.
    #
    # We deliberately avoid the old `imap_unordered` + early-break + terminate()
    # pattern: imap_unordered prefetches several extra structures, and
    # terminate()-ing those overshoot workers while they are mid-`psculpt` /
    # `mpiexec` orphans those subprocesses (they can spin forever, holding the
    # terminal) and skips TempDirectory cleanup (leaked temp dirs). The cost here
    # is reduced parallelism over the final few structures, when fewer than
    # `nthreads` results are still needed.
    def run_pool():
        task_iter = tasks()
        done_q = queue.Queue()
        collected = []
        succeeded = 0
        in_flight = 0
        exhausted = False
        pool = multiprocess.Pool(nthreads)

        def submit_one():
            nonlocal in_flight, exhausted
            try:
                t = next(task_iter)
            except StopIteration:
                exhausted = True
                return False
            pool.apply_async(
                _run_single_star,
                (t,),
                callback=lambda r: done_q.put((True, r)),
                error_callback=lambda e: done_q.put((False, e)),
            )
            in_flight += 1
            return True

        def refill():
            # Keep the window full while a free worker exists AND the result is
            # still needed (preserves succeeded + in_flight <= number).
            while (
                in_flight < nthreads
                and succeeded + in_flight < number
                and not exhausted
            ):
                if not submit_one():
                    break

        try:
            refill()
            while in_flight > 0 and succeeded < number:
                ok, payload = done_q.get()
                in_flight -= 1
                if ok:
                    payload, elapsed = payload
                    stats.record(payload, elapsed)
                else:
                    stats.worker_errors += 1
                if ok and not _is_mesh_failure(payload):
                    # success or EXEC_FAILED (EXEC_FAILED consumes a slot, dropped later)
                    collected.append(payload)
                    succeeded += 1
                elif not ok:
                    # A worker exception arrives here rather than propagating, so
                    # the non-retryable one has to be re-raised explicitly (the
                    # handler below tears the pool down).
                    if isinstance(payload, _FATAL_FILTER_ERRORS):
                        raise payload
                    if log:
                        logger.error(
                            "Unexpected worker error (treated as a mesh failure): %s",
                            str(payload),
                        )
                refill()
        except BaseException:
            # On any error, kill outstanding work rather than leaking it.
            pool.terminate()
            pool.join()
            raise
        # Normal completion: in_flight is 0 here, so this neither blocks nor kills.
        pool.close()
        pool.join()

        if succeeded < number and log:
            logger.error(
                "Only %d/%d meshes succeeded within %d attempts.",
                succeeded,
                number,
                cap,
            )
        return collected

    # Predefined: results stay positional (one per input structure, -1 for a
    # failure), as on main and as documented in demos/run_predefined_structures.py.
    if predefined:
        if nthreads == 1:
            collected = [_run_single_star(t) for t in tasks()]
        else:
            with multiprocess.Pool(nthreads) as pool:
                collected = pool.map(_run_single_star, list(tasks()))
        for r, elapsed in collected:
            stats.record(r, elapsed)
        return [-1 if isinstance(r, _Failure) else r for r, _ in collected]

    if nthreads == 1:
        collected = consume(_run_single_star(t) for t in tasks())
    else:
        collected = run_pool()

    # Drop executor failures (mesh succeeded but solve failed -> not backfilled).
    return [r for r in collected if not _is_exec_failure(r)]


def run_single(img, material_A, material_B, material_AB, config):
    """Run a single computation defined by input files and an image.

    Args:
        img (np.ndarray): Input image for the computation.
        material_A (dict): Material A properties
        material_B (dict): Material B properties
        material_AB (dict): Material interface properties
        config (dict): Problem configuration.
    """
    log = setup_logging(config)
    if log:
        logger.info("Starting a new computation on an image of shape %s", img.shape)

    write_files = config.get("output", {}).get("write_files", True)

    # Get unique ID
    if write_files:
        output_dir = config.get("output", {}).get("output_dir", "output")
        output_prefix = config.get("output", {}).get("output_prefix", "result")
        uid = unique_id(directory=output_dir, prefix=output_prefix, suffix="0.h5")
        if log:
            logger.info("Generated unique ID %s for output files", uid)
    else:
        uid = "no_output"
        if log:
            logger.info("No output files will be written for this computation")

    # Filter
    if log:
        logger.info("Problem %s: Applying filters to image", uid)
    refs = filter_refs(config, img.shape[0])
    for filter_spec in config.get("filtering", []):
        try:
            filter_func = get_object_from_module(filter_spec.get("type"))
            img = filter_func(img, **filter_params(filter_func, filter_spec, refs))
        except _FATAL_FILTER_ERRORS as e:
            # Deterministic: bad params (TypeError) or an input the config fixes
            # for every draw. Redrawing fails identically, so abort rather than
            # spend the retry budget. Logged unconditionally so it is visible
            # without a configured log_file.
            logger.error(
                "Problem %s: filter %s failed deterministically (%s); aborting run",
                uid,
                filter_spec.get("type"),
                str(e),
            )
            raise
        except Exception as e:
            if log:
                logger.error(
                    "Problem %s: Error applying filter %s: %s",
                    uid,
                    filter_spec.get("type"),
                    str(e),
                )
            return _Failure("mesh", "filter")
    if log:
        logger.info("Problem %s: Filtering complete", uid)

    # Move to our temp directory
    with temp.TempDirectory(config) as _:
        # Generate mesh
        if log:
            logger.info("Problem %s: Generating mesh", uid)

        try:
            mesh_function = get_object_from_module(config["mesh"]["type"])
            mesh_file = config["mesh_file"]
            mesh_function(
                img,
                mesh_file,
                L=config["L"],
                settings=config,
                **config["mesh"].get("params", {}),
            )
        except mesh.SculptError as e:
            if log:
                logger.error("Problem %s: SCULPT failed: %s", uid, str(e))
            return _Failure("mesh", "sculpt")
        except mesh.MeshQualityError as e:
            if log:
                logger.error("Problem %s: MESH CHECK failed: %s", uid, str(e))
            return _Failure("mesh", getattr(e, "reason", "quality"))
        except Exception as e:
            if log:
                logger.error("Problem %s: mesh generation error: %s", uid, str(e))
            return _Failure("mesh", "mesher-other")
        if log:
            logger.info("Problem %s: Mesh generation complete", uid)

        # Run
        if log:
            logger.info("Problem %s: Running executor", uid)

        try:
            executor = get_object_from_module(config["executor"]["type"])
            res = executor(
                config["executor"]["physics"],
                mesh_file,
                material_properties={
                    "A": material_A,
                    "B": material_B,
                    "AB": material_AB,
                },
                settings=config,
                problem_id=uid,
                **config["executor"].get("params", {}),
            )
        except Exception as e:
            # NOTE: executor (e.g. MOOSE) failures are intentionally NOT part of
            # the mesh/quality retry-backfill in run(): a structure that meshed
            # fine but whose solve failed is dropped (consumes a slot), not
            # re-generated. Folding executor failures into the backfill could be a
            # future improvement.
            if log:
                logger.error("Problem %s: Error running executor: %s", uid, str(e))
            return _Failure("exec", "executor")
        if log:
            logger.info("Problem %s: Executor run complete", uid)

    # Get the extractor
    if config.get("output", {}) == {} or "grid_extractor" not in config["output"]:
        if log:
            logger.info("Problem %s: No grid extraction requested.", uid)
        extractor = None
    else:
        try:
            extractor = get_object_from_module(
                config["output"]["grid_extractor"]["type"]
            )
        except Exception as e:
            if log:
                logger.error(
                    "Problem %s: Error setting up grid extractor %s: %s",
                    uid,
                    config["output"]["grid_extractor"]["type"],
                    str(e),
                )
            return _Failure("exec", "extractor-setup")

    if log:
        logger.info("Problem %s: Starting to write output files", uid)

    # The extractor projects onto N_out (default N_mesh) and resamples the
    # meshed image `img` to that grid itself.
    extractor_params = dict(
        config.get("output", {}).get("grid_extractor", {}).get("params", {})
    )
    extractor_params["N"] = output_resolution(
        config, mesh_resolution(config, img.shape[0])
    )

    # Actually write the output
    for i, result in enumerate(res):
        # Index the output file by the load/load-case index reported by the
        # executor (falling back to enumeration order) so the file suffix keeps
        # a 1-to-1 correspondence with the load case even when some are skipped.
        idx = result.get("index", i) if isinstance(result, dict) else i
        if extractor is not None:
            try:
                result["grid"] = extractor(
                    result["unstructured_mesh"], img, config["L"], **extractor_params
                )
            except Exception as e:
                if log:
                    logger.error(
                        "Problem %s: Error extracting grid for subresult %i: %s",
                        uid,
                        idx,
                        str(e),
                    )
                return _Failure("exec", "grid-extraction")

        if config.get("output", {}).get("add_density", False):
            # Material-A fraction of the mesh actually solved, as exported;
            # without a grid, fall back to the meshed image.
            if extractor is not None:
                material = result["grid"]["cell_fields"]["material"]["data"]
            else:
                material = np.asarray(img, dtype=bool)
            vf = float(np.mean(material))
            rho = vf * material_A.get("density", 0) + (1 - vf) * material_B.get(
                "density", 0
            )
            result["density"] = rho
            if log:
                logger.info(
                    "Problem %s: Added density %f to output for subresult %i",
                    uid,
                    rho,
                    idx,
                )

        if not write_files:
            if log:
                logger.info(
                    "Problem %s: Skipping writing output files as per configuration",
                    uid,
                )
            continue

        try:
            with open(
                os.path.join(output_dir, f"{output_prefix}_{uid}_{idx}.h5"), "wb"
            ) as f:
                hdfwriter.write_hdf5(f, result)
        except Exception as e:
            if log:
                logger.error(
                    "Problem %s: Error writing output file for subresult %i: %s",
                    uid,
                    idx,
                    str(e),
                )
            return _Failure("exec", "write-output")

        if log:
            logger.info(
                "Problem %s: Wrote output file %s for subresult %i",
                uid,
                os.path.join(output_dir, f"{output_prefix}_{uid}_{idx}.h5"),
                idx,
            )
    if log:
        logger.info("Problem %s: All output files written successfully", uid)
        logger.info("Problem %s: Completed computation successfully", uid)

    return res


def filter_params(filter_func, filter_spec, refs):
    """The filter's config params, plus each reference in `refs` (``n_gen``,
    ``n_mesh``, per unreplicated cell) that the filter takes and the config
    doesn't set.

    ``n_gen`` is the reference for length fractions (`mean_filter`,
    `defeature`), ``n_mesh`` for margins in mesh cells (`make_periodic`).
    """
    params = dict(filter_spec.get("params", {}))
    try:
        accepted = inspect.signature(filter_func).parameters
    except (TypeError, ValueError):
        accepted = {}
    for name, value in refs.items():
        if name in accepted and name not in params:
            params[name] = value
    return params


def filter_refs(config, n_gen):
    """References passed to the filters, per unreplicated (generated) cell of
    `n_gen` pixels per side: ``{"n_gen": ..., "n_mesh": ...}``.

    ``n_mesh`` is ``mesh.params.N`` (over the domain) divided by the
    `make_orthogonal` copies per side, possibly fractional. Lengths and
    margins then keep their size whether a filter runs before or after
    `make_orthogonal`.
    """
    copies = orthogonal_copies(config)
    n_mesh = mesh_resolution(config, copies * n_gen)
    n_mesh_cell = n_mesh // copies if n_mesh % copies == 0 else n_mesh / copies
    return {"n_gen": n_gen, "n_mesh": n_mesh_cell}


def orthogonal_copies(config):
    """Copies per side of the generated cell in the domain: 2 per
    `make_orthogonal` in the config's `filtering`, else 1."""
    n = sum(
        str(f.get("type", "")).endswith("make_orthogonal")
        for f in config.get("filtering", [])
    )
    return 2**n


def mesh_resolution(config, n_gen):
    """``N_mesh``: ``mesh.params.N``, or ``n_gen`` if unset."""
    n = config.get("mesh", {}).get("params", {}).get("N")
    return n_gen if n is None else int(n)


def output_resolution(config, n_mesh):
    """``N_out``: ``output.grid_extractor.params.N``, or ``n_mesh`` if unset."""
    out = config.get("output") or {}
    n = out.get("grid_extractor", {}).get("params", {}).get("N")
    return n_mesh if n is None else int(n)


# Warn when N_out < N_mesh / this: the nearest-centroid projection then skips
# most mesh cells instead of averaging them.
_ALIAS_RATIO = 2


def check_resolutions(config, generator):
    """Check ``dim``, ``L`` and the three resolutions at load time.

    ``N_gen`` comes from the generator (``generator.params.N``, or the data for
    e.g. FromNumpyGenerator) times the ``make_orthogonal`` copies per side:
    the pixels per side of the meshed image. ``N_mesh`` comes from
    ``mesh.params.N`` (default ``N_gen``), ``N_out`` from
    ``output.grid_extractor.params.N`` (default ``N_mesh``). The copies fill
    the same domain ``[0, L]``: the generator parameters keep referring to the
    unreplicated cell, while ``L``, ``N_mesh`` and ``N_out`` refer to the
    domain.

    Raises:
        ValueError: bad ``dim``/``L``/``N``, a generator of another dimension,
            or ``N_gen < N_mesh``.

    Returns:
        tuple: ``(n_gen, n_mesh, n_out)`` over the domain (``n_gen`` includes
        the ``make_orthogonal`` copies).
    """
    dim = config.get("dim")
    if dim not in (2, 3):
        raise ValueError(f"config `dim` must be 2 or 3, got {dim!r}")
    L = config.get("L")
    if isinstance(L, bool) or not isinstance(L, (int, float)) or L <= 0:
        raise ValueError(
            f"config `L` must be a positive number (square/cubic cell), got {L!r}"
        )
    shape = list(getattr(generator, "N", None) or [])
    if len(shape) != dim:
        raise ValueError(
            f"generator makes {len(shape)}D structures {shape}, config `dim` is {dim}"
        )
    n_gen = int(shape[0]) * orthogonal_copies(config)
    n_mesh = mesh_resolution(config, n_gen)
    n_out = output_resolution(config, n_mesh)
    for name, n in (
        ("mesh.params.N", n_mesh),
        ("output.grid_extractor.params.N", n_out),
    ):
        if n < 1:
            raise ValueError(f"{name} must be a positive integer, got {n}")
    if n_gen < n_mesh:
        raise ValueError(
            f"image N={n_gen} (generator N times make_orthogonal copies) is below "
            f"mesh N={n_mesh}: the mesh cannot be finer than the image"
        )
    if n_out * _ALIAS_RATIO < n_mesh:
        msg = (
            f"output N={n_out} is far below mesh N={n_mesh}: the nearest-centroid "
            "projection point-samples the mesh and will alias instead of averaging"
        )
        logger.warning(msg)
    return n_gen, n_mesh, n_out


def setup_generator(config_input, dim=None):
    """Set up a generator based on input specifications.

    Args:
        config_input (dict): Input specifications for the generator. A scalar
            ``params.N`` is the size on every axis.
        dim (int): Structure dimension (the config's top-level ``dim``);
            needed with a scalar ``N``.

    Returns:
        object: An instance of the generator.
    """
    gen_cls = get_object_from_module(config_input.get("type"))
    params = dict(config_input.get("params", {}))
    n = params.get("N")
    if n is not None:
        if not isinstance(n, int) or isinstance(n, bool):
            raise ValueError(
                f"generator `N` must be an integer (square/cubic cell), got {n!r}"
            )
        if dim is None:
            raise ValueError("a scalar generator `N` needs the config's `dim`")
        params["N"] = [n] * dim
    return gen_cls(**params)


def setup_material(config_input):
    """Set up a material generator based on input specifications.

    Args:
        config_input (dict): Input specifications for the material generator.

    Returns:
        object: An instance of the material generator.
    """
    mat_gen = get_object_from_module(config_input.get("type"))
    return mat_gen(**config_input.get("params", {}))
