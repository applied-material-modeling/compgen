import numpy as np

ncrack = 8

# bounding box
lb = 0
ub = 1

# crack length
L_avg = 0.1
L_cov = 0.3
L = np.random.normal(L_avg, L_cov * L_avg, ncrack)

# sample crack center
xc = np.random.uniform(lb, ub, (ncrack, 2))

# sample crack orientation
q = np.random.uniform(0, 2 * np.pi, ncrack)

# starting and ending points of crack
x1 = xc + 0.5 * L[:, np.newaxis] * np.column_stack((np.cos(q), np.sin(q)))
x2 = xc - 0.5 * L[:, np.newaxis] * np.column_stack((np.cos(q), np.sin(q)))


def clip_segment_to_box(p0, p1, lb, ub, eps=1e-12):
    """Clip segment p(t)=p0+t*(p1-p0), t in [0,1], to axis-aligned box [lb, ub]^2."""
    d = p1 - p0
    t0 = 0.0
    t1 = 1.0

    for axis in range(2):
        if abs(d[axis]) < eps:
            if p0[axis] < lb or p0[axis] > ub:
                return None
            continue

        inv_da = 1.0 / d[axis]
        t_enter = (lb - p0[axis]) * inv_da
        t_exit = (ub - p0[axis]) * inv_da
        if t_enter > t_exit:
            t_enter, t_exit = t_exit, t_enter

        t0 = max(t0, t_enter)
        t1 = min(t1, t_exit)

        if t0 > t1 + eps:
            return None

    q0 = p0 + t0 * d
    q1 = p0 + t1 * d
    return q0, q1


def periodic_split_segment(p0, p1, lb, ub, eps=1e-10):
    """
    Split a segment across periodic boundaries and return all in-box pieces.
    """
    w = ub - lb

    seg_min_x = min(p0[0], p1[0])
    seg_max_x = max(p0[0], p1[0])
    seg_min_y = min(p0[1], p1[1])
    seg_max_y = max(p0[1], p1[1])

    kx_min = int(np.ceil((lb - seg_max_x) / w))
    kx_max = int(np.floor((ub - seg_min_x) / w))
    ky_min = int(np.ceil((lb - seg_max_y) / w))
    ky_max = int(np.floor((ub - seg_min_y) / w))

    pieces = []
    for kx in range(kx_min, kx_max + 1):
        for ky in range(ky_min, ky_max + 1):
            shift = np.array([kx * w, ky * w])
            clipped = clip_segment_to_box(p0 + shift, p1 + shift, lb, ub)
            if clipped is None:
                continue
            a, b = clipped
            # skip degenerate intersections (e.g., touch at a corner only)
            if np.linalg.norm(b - a) <= eps:
                continue
            pieces.append((a, b))

    # Remove duplicates from numerical round-off.
    unique = []
    for a, b in pieces:
        found = False
        for ua, ub_ in unique:
            same_dir = np.allclose(a, ua, atol=eps) and np.allclose(b, ub_, atol=eps)
            opp_dir = np.allclose(a, ub_, atol=eps) and np.allclose(b, ua, atol=eps)
            if same_dir or opp_dir:
                found = True
                break
        if not found:
            unique.append((a, b))
    return unique


# project onto periodic RVE by splitting boundary-crossing cracks
segments = []
for i in range(ncrack):
    segments.extend(periodic_split_segment(x1[i], x2[i], lb, ub))

x1_periodic = np.array([s[0] for s in segments])
x2_periodic = np.array([s[1] for s in segments])
z = np.zeros(len(segments))

print(f"Sampled cracks: {ncrack}")
print(f"Periodic crack segments: {len(segments)}")
print(f"x1 = '{' '.join(f'{v:.8f}' for v in x1_periodic[:, 0])}'")
print(f"y1 = '{' '.join(f'{v:.8f}' for v in x1_periodic[:, 1])}'")
print(f"x2 = '{' '.join(f'{v:.8f}' for v in x2_periodic[:, 0])}'")
print(f"y2 = '{' '.join(f'{v:.8f}' for v in x2_periodic[:, 1])}'")
print(f"z1 = '{' '.join(f'{v:.8f}' for v in z)}'")
print(f"z2 = '{' '.join(f'{v:.8f}' for v in z)}'")
