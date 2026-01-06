import json
import os
import uuid
import importlib
import logging

import numpy as np
import multiprocess

from compgen import temp, hdfwriter

logger = logging.getLogger(__name__)


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


def run(problem, config):
    """Run a set of computations defined by input files

    Args:
        problem (str): Path to a problem definition file.
        config (str): Path to a configuration file.
    """
    problem_data = json.load(open(problem, "r"))
    config_data = json.load(open(config, "r"))

    log = False
    if "log_file" in config_data:
        log = True
        logging.basicConfig(
            filename=config_data["log_file"],
            level=(
                logging.DEBUG
                if config_data.get("log_level", "DEBUG") == "DEBUG"
                else logging.INFO
            ),
            format="%(asctime)s %(levelname)s:%(message)s",
        )

    if log:
        logger.info(
            "Starting to run problem with definition file %s and config file %s",
            problem,
            config,
        )

    # Create the output directory if it doesn't exist
    output_info = problem_data.get("output", {})
    output_dir = output_info.get("output_dir", "output")
    os.makedirs(output_dir, exist_ok=True)
    if log:
        logger.info("Output directory set to %s", output_dir)

    # Setup material and structure generator
    if log:
        logger.info("Setting up generator and materials")
    try:
        generator = setup_generator(problem_data["generator"])
    except Exception as e:
        if log:
            logger.error("Error setting up generator: %s", str(e))
        raise e
    if log:
        logger.info("Generator set up successfully")

    try:
        material_a = setup_material(problem_data["material_A"])
        material_b = setup_material(problem_data["material_B"])
        material_ab = setup_material(problem_data.get("material_AB", {}))
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
        generator, material_a, material_b, material_ab, range(problem_data["number"])
    )

    with multiprocess.Pool(problem_data.get("nthreads", 1)) as pool:
        results = pool.map(
            lambda x: run_single(x[0], x[1], x[2], x[3], problem_data, config_data),
            composite,
        )


def run_single(img, material_A, material_B, material_AB, problem, config):
    """Run a single computation defined by input files and an image.

    Args:
        img (np.ndarray): Input image for the computation.
        material_A (dict): Material A properties
        material_B (dict): Material B properties
        material_AB (dict): Material interface properties
        problem (dict): Problem configuration.
        config (dict): Configuration settings.
    """
    log = config.get("log_file", False) is not False
    if log:
        logger.info("Starting a new computation on an image of shape %s", img.shape)

    # Get unique ID
    output_dir = problem.get("output", {}).get("output_dir", "output")
    output_prefix = problem.get("output", {}).get("output_prefix", "result")
    uid = unique_id(directory=output_dir, prefix=output_prefix, suffix="0.h5")
    if log:
        logger.info("Generated unique ID %s for output files", uid)

    # Filter
    if log:
        logger.info("Problem %s: Applying filters to image", uid)
    for filter in problem.get("filtering", []):
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
            return -1
    if log:
        logger.info("Problem %s: Filtering complete", uid)

    # Move to our temp directory
    pwd = os.getcwd()
    temp_dir = temp.make_temp_directory(config)
    if log:
        logger.info("Problem %s: Changing to temporary directory %s", uid, temp_dir)
    os.chdir(temp_dir)

    # Generate mesh
    if log:
        logger.info("Problem %s: Generating mesh", uid)

    try:
        mesh_function = get_object_from_module(problem["mesh"]["type"])
        mesh_file = problem["mesh_file"]
        mesh_function(
            img,
            mesh_file,
            settings=config,
            **problem["mesh"].get("params", {}),
        )
    except Exception as e:
        if log:
            logger.error("Problem %s: Error generating mesh: %s", uid, str(e))
        os.chdir(pwd)
        return -1
    if log:
        logger.info("Problem %s: Mesh generation complete", uid)
    # Run
    if log:
        logger.info("Problem %s: Running executor", uid)

    try:
        executor = get_object_from_module(problem["executor"]["type"])
        res = executor(
            problem["executor"]["physics"],
            mesh_file,
            material_properties={"A": material_A, "B": material_B, "AB": material_AB},
            settings=config,
            **problem["executor"].get("params", {}),
        )
    except Exception as e:
        if log:
            logger.error("Problem %s: Error running executor: %s", uid, str(e))
        os.chdir(pwd)
        return -1
    if log:
        logger.info("Problem %s: Executor run complete", uid)
    # Move back
    if log:
        logger.info("Problem %s: Returning to original directory %s", uid, pwd)
    os.chdir(pwd)

    # Get the extractor
    try:
        extractor = get_object_from_module(problem["output"]["grid_extractor"]["type"])
    except Exception as e:
        if log:
            logger.error(
                "Problem %s: Error setting up grid extractor %s: %s",
                uid,
                problem["output"]["grid_extractor"]["type"],
                str(e),
            )
        return -1

    if log:
        logger.info("Problem %s: Starting to write output files", uid)

    # Actually write the output
    for i, result in enumerate(res):
        try:
            result["grid"] = extractor(
                result["unstructured_mesh"], img, problem["lx"], problem["ly"]
            )
        except Exception as e:
            if log:
                logger.error(
                    "Problem %s: Error extracting grid for subresult %i: %s",
                    uid,
                    i,
                    str(e),
                )
            return -1

        if problem.get("output", {}).get("add_density", False):
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

        try:
            with open(
                os.path.join(output_dir, f"{output_prefix}_{uid}_{i}.h5"), "wb"
            ) as f:
                hdfwriter.write_hdf5(f, result)
        except Exception as e:
            if log:
                logger.error(
                    "Problem %s: Error writing output file for subresult %i: %s",
                    uid,
                    i,
                    str(e),
                )
            return -1

        if log:
            logger.info(
                "Problem %s: Wrote output file %s for subresult %i",
                uid,
                os.path.join(output_dir, f"{output_prefix}_{uid}_{i}.h5"),
                i,
            )
    if log:
        logger.info("Problem %s: All output files written successfully", uid)
        logger.info("Problem %s: Completed computation successfully", uid)
    return 0


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
