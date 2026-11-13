# HDF5 format for training data

Training data is stored in an HDF5 format.  This document outlines the structure of these files and describes what the data means.  You'll want to read the writeup on the mathematical structure of homogenization problems to understand the terms "stimuli" and "response" and "generalized" versus "field" information.

## Tensor storage format

All tensor data is stored as a group in the HDF5 files with a string attribute "type" giving the tensor type:
- "scalar": a scalar
- "vector": a vector, stored as a (2,), for 2D, or (3,), for 3D, base shape
- "symmetric_rank_two_tensor": a symmetric rank two tensor, stored as a flattened tensor of components in the order "xx", "yy", "xy" in 2D and "xx", "yy", "zz", "yz", "xz", "xy".
- "rank_two_tensor": a general rank two tensor, stored as a (2,2), for 2D, or (3,3), for 3D, base shape.

A "shape" subgroup which gives the base shape of tensor.  The actual data is stored as a `(ntime, ...,) + base_shape` tensor, where the first dimension stores time steps, the intermediate dimensions are the spatial distribution of the data, for example an `(nx,ny,nz)` grid, the `base_shape` gives the actual tensor dimension.

***Important: Coordinates are generated with the numpy/pytorch `meshgrid` function with `indexing = 'ij'`.  This means that the x-values are the first axis in the array, the y-values the second, and the z-values the third.  For plotting 2D arrays you'll likely want to transpose the matrix before plotting with the standard `'xy'` convention, where rows (first index) are y and columns (second index) are x.***

And finally a "data" subgroup which gives the actual tensor data.

The intermediate dimensions are optional, for global data, like the generalized stimuli and responses, are not distributed over space.

If the data is constant over time (like the distribution of material A and B) then the first dimension will have length 1, but still be present.

## HDF5 structure

The rest of this document is hierarchical, just like the HDF5 files.  Each subsection is a group name, with the subsequent text describing what that group stores.

### Top-level attributes

- "index": the load-case index of this file (an integer). Each structure produces one file per load case, and the index matches the `_<index>.h5` suffix of the file name.
- "density": the volume-averaged density of the composite. Only present when `output.add_density` is set in the configuration.

### Generalized

The generalized, homogenized stimuli and response information from the simulation.

#### Responses

Each generalized response, stored in the tensor format described above.

#### Stimuli

Each generalized stimuli, stored in the tensor format described above.

### Grid

The problem setup and field variable solutions projected onto a fixed grid.

#### Cell fields

The full-field data from the simulations.  The intermediate, spatial dimensions of the tensor will have shape `(nx,ny)` in 2D or `(nx,ny,nz)` in 3D, with the dimensions indicating the number of grid cells in each dimension.

This subgroup has two (2D) or three (3D) attributes called `lx`, `ly`, and (for 3D) `lz` giving the physical size of the problem domain.

##### Material

A boolean tensor giving the distribution of material A (value `True`/`1`) and B (value `False`/`0`).  Unlike the other fields, it has no time dimension: its shape is `(nx,ny)` in 2D or `(nx,ny,nz)` in 3D.

##### Material reprojected

The same data as [material](#material), but reprojected onto the fixed grid from the unstructured grid data.  This field is only present if the [unstructured mesh](#unstructured-mesh) group is present, indicating the actual simulation used an unstructured mesh.  As the material distribution remains constant with time, the length of the first (time) dimension will be `1`.

##### Responses

The full field response fields, projected onto the fixed grid, using the format for tensor data described above.

##### Stimuli

The full field stimuli fields, projected onto the fixed grid, using the format for tensor data described above.

### Loads

The load parameters of this file's load case, given as float attributes of this group.  Only present for physics that step through a list of load parameters, currently the plastic physics:
- 2D plastic: "theta", the in-plane load direction in radians.
- 3D plastic: "theta" and "phi", the load direction in spherical angles, in radians.

For the other physics the load case is identified by the top-level "index" attribute alone.

### Material properties

A description of the material properties of each phase.  These will be highly dependent on the problem physics.  At least for now, the material properties are all assumed to be scalars.

#### A

The material properties of phase "A", given as float attributes of this subgroup.

#### B

The material properties of phase "B", given as float attributes of this subgroup.


#### AB

The material properties of the interface, given as float attributes of this subgroup.

### Physics

This section is a copy of the input data structured used to drive the physics tool simulations.  There should not be a reason for people working with the training data to look at the subgroups contined by this group, but they are included for archival purposes.

However, this group has a few key attributes that might be useful in training:
- "dimension": The problem dimension as an integer
- "name": The name of the physics template that produced these results.  Options are:
    * elastic: Simulations probing the composite's effective elastic tensor
    * plastic: Simulations of the composite's elastic-plastic response under a stress ramp along a load direction
    * thermal_conductivity: Simulations probing the composite's effective thermal conductivity
    * thermal_conductivity_with_interface: The same, with an interface conductance between the phases
    * thermal_expansion: Simulations probing the composite's coefficient of thermal expansion
- "type": Either "steady" or "transient".  "steady" means the simulation results came from a steady state simulation.  In practice, this means all the results fields will have a time dimension of `(2,)` with the first item being the initial conditions for the simulation (which may be zero) and the second item being the steady state simulation results.

#### Responses

A description of the response variables.  Each response variable is summarized in a common format with a subgroup.  The subgroup key is the variable name.  The subgroup has two attributes:

- "dim": the physical dimension of the field.  This should match the problem dimension.
- "type": the tensor type, following the conventions listed [above](#tensor-storage-format).

The subgroup then has two further subgroups:

- "field_components": has attributes numbered consecutively, with zero indexing, giving the names in the simulations of each field component.
- "postprocessor_components": has attributes numbered conseecutively, with zero indexing, giving the names in the simulations of each generalized/homogenized field variable.

The responses subgroup divides the results into "responses" and "stimuli" subgroups.

### Unstructured mesh

The results stored in an unstructured grid format.  This subgroup is optional, if the original simulations used a fixed grid then this subgroup won't be present.

We assume that the element type is a linear quad in 2D, defined by 4 nodes, and a linear hex in 3D, defined by 8 nodes.  The format for node numbering follows the Exodus II convention, described [here](https://sandialabs.github.io/seacas-docs/exodusII-new.pdf).

#### connectivity

The element connectivity, this will be an `(n_elem, 4)` tensor in 2D and a `(n_elem, 8)` tensor in 3D.

#### coords

The nodal coordinates, this will bbe an `(n_node, 2)` tensor in 2D and a `(n_node, 3)` tensor in 3D.

#### Element fields

The material distribution, response fields, and stimuli fields stored in the same way described as for the [structured grid](#cell-fields) results.  The only difference is the intermediate tensor dimensions will now have shape `n_elem` rather than the shape of the grid.
