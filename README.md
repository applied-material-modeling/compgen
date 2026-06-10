# compgen

## Summary
compgen is a Python toolkit for generating simulation data for two phase composite materials.  It will generate structures, invoke physics codes to simulate the response for a variety of material properties, and write summaries of the results.

## Install
1. (Optional) Create and activate a virtual environment.
2. Install the package:
   - `pip install -e .`
3. Install the mesher and physics codes you want to use:
    1. [MOOSE](https://mooseframework.inl.gov/)
    2. [SCULPT](https://www.sandia.gov/files/cubit/documents/SculptSANDReport.pdf)

## Inputs

compgen pipes together several steps to generate results:
1. Generate a composite structure -- the distribution of two materials A and B over a periodic domain.  We use pixelated fixed grids to define this distribution.
2. Make an unstructured finite element mesh of the fixed grid representation, smoothing interfaces.  This might involve first filtering the fixed grid representation, then calling a mesh generator.
3. Setup input files for the physics codes describing the problem physics and boundary conditions.
4. Actually run the physics code.  This might require multiple calls, for example if we're interested in properties in different loading directions.
5. Post process the output from the physics code into a common format.  We use an [HDF5 format](doc/data.md).

compgen provides a simple API (`runner.run`) for doing all of this based on json input files.  You need two input files to invoke the runner:
1. A problem file defining the steps outlined above -- which structure generator, mesh, physics, solver, etc.
2. A system file letting compgen know how to run external tools (meshers and physics codes).

There are examples of each file type to make up the 2D and 3D demos, described below.

## Tests and demos

First set environment variables:
1. `MOOSE_DIR` to the root directory of your moose installation
2. `CUBIT_DIR` to the root directory of your CUBIT directory, if you want to run the demos using sculpt.  This is not necessary for the verification tests.

## Run the tests

Run the tests with `pytest`.  The general tests in the `tests` directory do not require MOOSE and will quick/cheap to run.  The verification tests in `tests/verification` are more expensive and require MOOSE.

## Run the demos

There are complete demos that generate random structures, call MOOSE to solve for some material properties, and store the results.  These demos live in `demos/complete`.  The subdirectories first split
the problems into different physics/types of material properties and then into 2D and 3D examples.