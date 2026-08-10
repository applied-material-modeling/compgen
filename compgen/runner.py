# pylint: disable=broad-exception-caught, too-many-branches, too-many-statements, too-many-locals, too-many-return-statements
"""High-level orchestration for generating structures, meshing, solving, and writing outputs."""

import os
import uuid
import queue
import importlib
import logging

import numpy as np
import multiprocess

from compgen import temp, hdfwriter, utils, mesh, filters

logger = logging.getLogger(__name__)


# Sentinels for the two failure modes run_single can report. MESH_FAILED
# (sculpt / quality / mesh-prep) is backfilled by drawing a new structure;
# EXEC_FAILED (executor, e.g. MOOSE) consumes a slot and is dropped.
#
# These must survive being pickled back from a multiprocess.Pool worker, so they
# are class instances identified by a `.kind` attribute (NOT bare `object()`
# compared with `is` -- identity does not survive pickling, which silently turned
# parallel failures into phantom "successes").
class _Failure:  # pylint: disable=too-few-public-methods
    """Sentinel marking a failed run_single attempt (pickling-safe)."""

    def __init__(self, kind):
        self.kind = kind


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
    """Unpack a (img, matA, matB, matAB, config) tuple for use with Pool.imap."""
    return run_single(*args)


def get_object_from_module(name, prefix="compgen"):
    """Dynamically import an object from a module.

    Args:
        name (str): Full path to the object in the format 'module.submodule:object'.

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
        problem (str): Path to a problem definition file.
        config (str): Path to a configuration file.
    """
    config = utils.load_json(config_files)

    log = setup_logging(config)

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
        generator = setup_generator(config["generator"])
    except Exception as e:
        if log:
            logger.error("Error setting up generator: %s", str(e))
        raise e
    if log:
        logger.info("Generator set up successfully")

    try:
        material_a = setup_material(config["material_A"])
        material_b = setup_material(config["material_B"])
        material_ab = setup_material(config.get("material_AB", {}))
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

    number = config["number"]
    nthreads = config.get("nthreads", 1)
    cap = config.get("max_attempts_factor", 3) * number
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
            try:
                img = next(generator)
            except StopIteration:
                return
            except Exception as e:  # pylint: disable=broad-exception-caught
                if log:
                    logger.error(
                        "Generation failed (attempt %d/%d), redrawing: %s",
                        drawn,
                        cap,
                        str(e),
                    )
                continue
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
        for r in out_iter:
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
    for filter_spec in config.get("filtering", []):
        try:
            filter_func = get_object_from_module(filter_spec.get("type"))
            img = filter_func(img, **filter_spec.get("params", {}))
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
            return MESH_FAILED
    if log:
        logger.info("Problem %s: Filtering complete", uid)

    # Move to our temp directory
    with temp.TempDirectory(config) as _:
        # Generate mesh
        if log:
            logger.info("Problem %s: Generating mesh", uid)

        refinement = config.get("generator", {}).get("params", {}).get("refinement", 0)
        try:
            mesh_function = get_object_from_module(config["mesh"]["type"])
            mesh_file = config["mesh_file"]
            mesh_function(
                img,
                mesh_file,
                L=config["L"],
                settings=config,
                refinement=refinement,
                **config["mesh"].get("params", {}),
            )
        except mesh.SculptError as e:
            if log:
                logger.error("Problem %s: SCULPT failed: %s", uid, str(e))
            return MESH_FAILED
        except mesh.MeshQualityError as e:
            if log:
                logger.error("Problem %s: QUALITY CHECK failed: %s", uid, str(e))
            return MESH_FAILED
        except Exception as e:
            if log:
                logger.error("Problem %s: mesh generation error: %s", uid, str(e))
            return MESH_FAILED
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
            return EXEC_FAILED
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
            return EXEC_FAILED

    if log:
        logger.info("Problem %s: Starting to write output files", uid)

    # Material image at the mesh/output resolution N (the generated image is at
    # N * 2**refinement when refining), so the grid projection lands on the N grid.
    # Bool either way: the material field is documented as boolean and every
    # refined run already forced it via the `> 0.5` below.
    grid_img = (
        mesh.downsample_vfrac(img, 2**refinement) > 0.5
        if refinement
        else np.asarray(img, dtype=bool)
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
                    result["unstructured_mesh"], grid_img, config["L"]
                )
            except Exception as e:
                if log:
                    logger.error(
                        "Problem %s: Error extracting grid for subresult %i: %s",
                        uid,
                        idx,
                        str(e),
                    )
                return EXEC_FAILED

        if config.get("output", {}).get("add_density", False):
            vf = np.sum(grid_img) / float(grid_img.size)
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
            return EXEC_FAILED

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


def setup_generator(config_input):
    """Set up a generator based on input specifications.

    Args:
        config_input (dict): Input specifications for the generator.

    Returns:
        object: An instance of the generator.
    """
    gen_cls = get_object_from_module(config_input.get("type"))
    params = dict(config_input.get("params", {}))
    # `refinement` (default 0) is a generator-config knob, not a constructor arg.
    # When > 0 the generator must output the FINE image at N * 2**refinement so the
    # mesher can coarsen it back to N as fractional volume fractions (-ims).
    refinement = params.pop("refinement", 0)
    base_N = params.get("N")
    if base_N is not None and refinement:
        params["N"] = [int(n * 2**refinement) for n in base_N]
    gen = gen_cls(**params)
    gen.refinement = refinement
    gen.base_N = base_N
    return gen


def setup_material(config_input):
    """Set up a material generator based on input specifications.

    Args:
        config_input (dict): Input specifications for the material generator.

    Returns:
        object: An instance of the material generator.
    """
    mat_gen = get_object_from_module(config_input.get("type"))
    return mat_gen(**config_input.get("params", {}))
