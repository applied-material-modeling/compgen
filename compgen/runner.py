import os
import uuid
import importlib
import logging

import numpy as np
import multiprocess

from compgen import frame_sampling, generalized, temp, hdfwriter, utils

logger = logging.getLogger(__name__)


def validate_frame_sampling_settings(output_settings):
    """Validate and return the optional output frame-sampling settings."""
    sampling_settings = output_settings.get("frame_sampling")
    if sampling_settings is None:
        return None

    if not isinstance(sampling_settings, dict):
        raise TypeError("output.frame_sampling must be a JSON object")
    allowed_keys = {"max_frames", "write_full_result"}
    unknown_keys = set(sampling_settings) - allowed_keys
    if unknown_keys:
        raise ValueError(
            "Unknown output.frame_sampling setting(s): "
            + ", ".join(sorted(unknown_keys))
        )
    if "max_frames" not in sampling_settings:
        raise ValueError("output.frame_sampling.max_frames is required")
    frame_sampling.validate_max_frames(sampling_settings["max_frames"])

    write_full_result = sampling_settings.get("write_full_result", False)
    if not isinstance(write_full_result, bool):
        raise TypeError("output.frame_sampling.write_full_result must be a boolean")
    return sampling_settings


def write_result_files(filename, result, output_settings):
    """Write the configured full and/or frame-sampled HDF5 result files."""
    # Fracture results carry the fields needed for homogenized quantities; when
    # present, inject them and enable float32 downcast + compression on write.
    compress = generalized.has_fracture_fields(result)
    if compress:
        generalized.inject_fracture_generalized(result)

    sampling_settings = validate_frame_sampling_settings(output_settings)
    if sampling_settings is None:
        hdfwriter.write_hdf5(filename, result, compress=compress)
        return [filename]

    written_files = []
    if sampling_settings.get("write_full_result", False):
        stem, extension = os.path.splitext(filename)
        full_filename = f"{stem}_all_frames{extension}"
        hdfwriter.write_hdf5(full_filename, result, compress=compress)
        written_files.append(full_filename)

    sampled_result = frame_sampling.sample_result_frames(
        result, sampling_settings["max_frames"]
    )
    hdfwriter.write_hdf5(filename, sampled_result, compress=compress)
    written_files.append(filename)
    return written_files


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


def run(*config_files):
    """Run a set of computations defined by input files

    Args:
        problem (str): Path to a problem definition file.
        config (str): Path to a configuration file.
    """
    config = utils.load_json(config_files)
    validate_frame_sampling_settings(config.get("output", {}))

    log = False
    if "log_file" in config:
        log = True
        logging.basicConfig(
            filename=config["log_file"],
            level=(
                logging.DEBUG
                if config.get("log_level", "DEBUG") == "DEBUG"
                else logging.INFO
            ),
            format="%(asctime)s %(levelname)s:%(message)s",
        )

    if log:
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

    if log:
        logger.info("Starting computations")

    # The full iterator
    composite = zip(
        generator, material_a, material_b, material_ab, range(config["number"])
    )

    nthreads = config.get("nthreads", 1)
    if log:
        logger.info("Using %d threads for computation", nthreads)

    if nthreads == 1:
        results = list(
            map(
                lambda x: run_single(x[0], x[1], x[2], x[3], config),
                composite,
            )
        )
    else:
        with multiprocess.Pool(config.get("nthreads", 1)) as pool:
            results = pool.map(
                lambda x: run_single(x[0], x[1], x[2], x[3], config),
                composite,
            )

    return results


def run_single(img, material_A, material_B, material_AB, config):
    """Run a single computation defined by input files and an image.

    Args:
        img (np.ndarray): Input image for the computation.
        material_A (dict): Material A properties
        material_B (dict): Material B properties
        material_AB (dict): Material interface properties
        config (dict): Problem configuration.
    """
    log = config.get("log_file", False) is not False
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
    for filter in config.get("filtering", []):
        try:
            filter_func = get_object_from_module(filter.get("type"))
            img = filter_func(img, **filter.get("params", {}))
        except Exception as e:
            if log:
                logger.error(
                    "Problem %s: Error applying filter %s: %s",
                    uid,
                    filter.get("type"),
                    str(e),
                )
            import traceback

            traceback.print_exc()
            return -1
    if log:
        logger.info("Problem %s: Filtering complete", uid)

    # # DEBUG: Output image of the spinodal structure
    # import matplotlib.pyplot as plt
    # plt.imshow(img, cmap='gray')
    # plt.title("Spinodal Structure")
    # plt.savefig(f"{uid}_spinodal_debug.png")
    # plt.close()
    # if log:
    #     logger.info("Saved spinodal debug image to %s_spinodal_debug.png", uid)

    # # DEBUG: Stop prematurely so it doesn't run the expensive meshing/simulation
    # return 0

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
        except Exception as e:
            if log:
                logger.error("Problem %s: Error generating mesh: %s", uid, str(e))
            import traceback

            traceback.print_exc()
            return -1
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
                **config["executor"].get("params", {}),
            )
        except Exception as e:
            if log:
                logger.error("Problem %s: Error running executor: %s", uid, str(e))
            import traceback

            traceback.print_exc()
            return -1
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
            import traceback

            traceback.print_exc()
            return -1

    if log:
        logger.info("Problem %s: Starting to write output files", uid)

    # Actually write the output
    for i, result in enumerate(res):
        if extractor is not None:
            try:
                result["grid"] = extractor(
                    result["unstructured_mesh"], img, config["L"]
                )
            except Exception as e:
                if log:
                    logger.error(
                        "Problem %s: Error extracting grid for subresult %i: %s",
                        uid,
                        i,
                        str(e),
                    )
                import traceback

                traceback.print_exc()
                return -1

        if config.get("output", {}).get("add_density", False):
            vf = np.sum(img) / float(img.size)
            rho = vf * material_A.get("density", 0) + (1 - vf) * material_B.get(
                "density", 0
            )
            result["density"] = rho
            if log:
                logger.info(
                    "Problem %s: Added density %f to output for subresult %i",
                    uid,
                    rho,
                    i,
                )

        if not write_files:
            if log:
                logger.info(
                    "Problem %s: Skipping writing output files as per configuration",
                    uid,
                )
            continue

        output_filename = os.path.join(output_dir, f"{output_prefix}_{uid}_{i}.h5")
        try:
            written_files = write_result_files(
                output_filename,
                result,
                config.get("output", {}),
            )
        except Exception as e:
            if log:
                logger.error(
                    "Problem %s: Error writing output file for subresult %i: %s",
                    uid,
                    i,
                    str(e),
                )
            import traceback

            traceback.print_exc()
            return -1

        if log:
            for written_file in written_files:
                logger.info(
                    "Problem %s: Wrote output file %s for subresult %i",
                    uid,
                    written_file,
                    i,
                )
    if log:
        logger.info("Problem %s: All output files written successfully", uid)
        logger.info("Problem %s: Completed computation successfully", uid)

    return res


def setup_generator(input):
    """Set up a generator based on input specifications.

    Args:
        input (dict): Input specifications for the generator.

    Returns:
        object: An instance of the generator.
    """
    gen = get_object_from_module(input.get("type"))
    return gen(**input.get("params", {}))


def setup_material(input):
    """Set up a material generator based on input specifications.

    Args:
        input (dict): Input specifications for the material generator.

    Returns:
        object: An instance of the material generator.
    """
    mat_gen = get_object_from_module(input.get("type"))
    return mat_gen(**input.get("params", {}))
