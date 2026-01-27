# compgen

## Summary
compgen is a Python toolkit for generating simulation data for two phase composite materials.  It will generate structures, invoke physics codes to simulate the response for a variety of material properties, and write summaries of the results.

## Install
1. (Optional) Create and activate a virtual environment.
2. Install dependencies:
   - `pip install -r requirements.txt`
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

## Run the tests

First you'll need to update `tests/verification/test_config.json` to let compgen know where your physics codes and meshers are and how to run them on your system.  Then just run
`pytest`
to start the tests.  These check basic correctness of the structure generators and basic results for each type of supported physics.

## Run the demo
The repository includes example configurations and runner scripts.

2D demo:
- `python demo.py`

3D demo:
- `python demo3d.py`

Before running these you'll need to update `demo_config.json` and `demo_config_3d.json`, again to point compgen to your meshers and physics solvers.

Results will be generated in `demo_output` and `3d_demo_output`.