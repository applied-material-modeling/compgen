# Items to address before completing the simulation

## Resolution

- [ ] Determine the appropriate structure resolution for the final simulations.
- [ ] Confirm the effect of removing `gen.make_orthogonal` from both cases.
  - The generator remains at `N: [256, 256]`.
  - With the orthogonal filter, the structure was expanded to approximately
    `512 x 512` by mirroring each direction.
  - Without the filter, the structure is `256 x 256`: half the linear
    resolution in each direction and one-quarter the total number of 2D
    structure samples/elements.
- [ ] Check whether the resulting `256 x 256` mesh adequately resolves the
  ellipses, interfaces, and fracture process zone.
- [ ] If necessary, increase `N` while keeping the orthogonal filter disabled,
  and compare the resulting cost and physical resolution.

## Volume fraction

- [ ] Determine the appropriate volume fraction `vf` for the final simulations.
- [ ] Confirm whether the current value, `vf: 0.2`, is the intended fraction of
  material A or whether it should be changed.
- [ ] Verify the realized volume fraction after ellipse generation and the mean
  filter, since the generated binary structure may not match the target value
  exactly.
- [ ] Use the same volume-fraction decision consistently for both `case1` and
  `case2`, unless the cases are intentionally meant to represent different
  microstructures.