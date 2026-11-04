# Fracture simulations

Choose the computer first, then the simulation type:

## Aurora

Aurora batch-job cases are under [`aurora/`](aurora/):

- 2D fixed material: [`aurora/2d_fixed/`](aurora/2d_fixed/)
- 2D random material: [`aurora/2d_random/`](aurora/2d_random/)
- 3D fixed material: [`aurora/3d_fixed/`](aurora/3d_fixed/)

Each case contains its fracture/machine JSON configs and PBS launch scripts. Use [`aurora/queue_info.md`](aurora/queue_info.md) for queue and resource limits.

## ES

ES cases are under [`ES/`](ES/):

- 2D predefined fracture: [`ES/2d/`](ES/2d/)
- 2D predefined fracture with MD test: [`ES/2d_md_test/`](ES/2d_md_test/)
- 3D predefined fracture: [`ES/3d/`](ES/3d/)

Use the `HOW_TO_RUN.md` or `README.md` in the selected case. Results and plotting tools are in that case’s `simulations/` and `plotting/` directories when present.