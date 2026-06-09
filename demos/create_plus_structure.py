import numpy as np
import matplotlib.pyplot as plt
import sys
sys.path.append("..")
from compgen import gen

# 1. Create the base 128x128 image
# Since make_orthogonal mirrors the image into a 256x256 grid,
# the bottom-right corner of this 128x128 quadrant becomes the absolute center of the final image.
n = 128
base = np.ones((n, n), dtype=bool) # True = Aluminum (Matrix)

# We want to draw a centered '+' cross of SiC (False).
# To do this, we draw half-bars along the bottom and right edges of our 128x128 base image.
bar_thickness = 20  # Half-thickness (will mirror to 40 pixels thick in the 256x256 image)
bar_length = 80     # Half-length (will mirror to 160 pixels long)

# Horizontal arm of the cross (along the bottom edge)
base[n - bar_thickness : n, n - bar_length : n] = False

# Vertical arm of the cross (along the right edge)
base[n - bar_length : n, n - bar_thickness : n] = False

# Save to test_structures.npy with shape (1, 128, 128)
# FromNumpyGenerator expects shape: (n_structures, Nx, Ny)
data = base[np.newaxis, :, :]
np.save("test_structures.npy", data)
print("Successfully saved test_structures.npy with shape:", data.shape)

# Let's preview exactly what it will look like after make_orthogonal mirroring!
final_image = gen.make_orthogonal(base)

plt.figure(figsize=(6, 6))
plt.imshow(final_image.T, cmap="gray") # Transposed to match physical X-Y orientation
plt.title("Final 256x256 '+' Composite\n(White = Aluminum Matrix, Black = SiC Cross)")
plt.savefig("plus_structure_preview.png")
print("Saved preview image to plus_structure_preview.png")
