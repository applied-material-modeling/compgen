"""Select a smaller, time-aligned set of transient simulation frames."""

from __future__ import annotations

import numbers

import numpy as np


def validate_max_frames(max_frames: int) -> int:
    if isinstance(max_frames, bool) or not isinstance(max_frames, numbers.Integral):
        raise TypeError("frame_sampling.max_frames must be an integer")
    max_frames = int(max_frames)
    if max_frames < 2:
        raise ValueError(
            "frame_sampling.max_frames must be at least 2 so the first and last "
            "frames can both be retained"
        )
    return max_frames


def select_frame_indices(times: np.ndarray, max_frames: int) -> np.ndarray:
    """Select actual frames nearest to evenly spaced target times.

    The first and last frames are always retained. When reduction is needed,
    dynamic programming finds the ordered, unique set of frame indices that
    minimizes the total absolute distance from evenly spaced target times.
    """
    max_frames = validate_max_frames(max_frames)
    times = np.asarray(times, dtype=np.float64)

    if times.ndim != 1 or times.size == 0:
        raise ValueError(
            "Frame sampling requires a nonempty one-dimensional time array"
        )
    if not np.all(np.isfinite(times)):
        raise ValueError("Frame sampling requires finite time values")
    if np.any(np.diff(times) < 0.0):
        raise ValueError("Frame sampling requires monotonically increasing time values")

    frame_count = times.size
    if frame_count <= max_frames:
        return np.arange(frame_count, dtype=np.int64)

    targets = np.linspace(times[0], times[-1], max_frames)
    costs = np.full((max_frames, frame_count), np.inf, dtype=np.float64)
    predecessors = np.full((max_frames, frame_count), -1, dtype=np.int64)
    costs[0, 0] = 0.0

    for target_index in range(1, max_frames):
        previous_costs = costs[target_index - 1]
        prefix_best_cost = np.empty(frame_count, dtype=np.float64)
        prefix_best_index = np.empty(frame_count, dtype=np.int64)
        best_cost = np.inf
        best_index = -1

        for frame_index, cost in enumerate(previous_costs):
            if cost < best_cost:
                best_cost = cost
                best_index = frame_index
            prefix_best_cost[frame_index] = best_cost
            prefix_best_index[frame_index] = best_index

        if target_index == max_frames - 1:
            candidate_indices = (frame_count - 1,)
        else:
            first_candidate = target_index
            last_candidate = frame_count - max_frames + target_index
            candidate_indices = range(first_candidate, last_candidate + 1)

        for frame_index in candidate_indices:
            predecessor = prefix_best_index[frame_index - 1]
            if predecessor < 0:
                continue
            costs[target_index, frame_index] = prefix_best_cost[frame_index - 1] + abs(
                times[frame_index] - targets[target_index]
            )
            predecessors[target_index, frame_index] = predecessor

    selected = np.empty(max_frames, dtype=np.int64)
    selected[-1] = frame_count - 1
    for target_index in range(max_frames - 1, 0, -1):
        selected[target_index - 1] = predecessors[target_index, selected[target_index]]

    if selected[0] != 0 or np.any(np.diff(selected) <= 0):
        raise RuntimeError("Failed to construct an ordered frame selection")
    return selected


def sample_result_frames(result: dict, max_frames: int) -> dict:
    """Return a result dictionary containing at most ``max_frames`` frames."""
    if "time" not in result:
        raise ValueError("Frame sampling requires the top-level time array")

    times = np.asarray(result["time"], dtype=np.float64)
    selected = select_frame_indices(times, max_frames)
    original_frame_count = times.size

    def sample_value(value, path=()):
        if not isinstance(value, dict):
            return value

        if {"type", "shape", "data"}.issubset(value):
            sampled_tensor = dict(value)
            tensor_data = np.asarray(value["data"])
            if tensor_data.ndim == 0:
                raise ValueError(
                    f"Transient tensor {'/'.join(path)} has scalar data without a "
                    "frame axis"
                )
            if tensor_data.shape[0] == original_frame_count:
                sampled_tensor["data"] = tensor_data[selected]
            elif tensor_data.shape[0] != 1:
                raise ValueError(
                    f"Transient tensor {'/'.join(path)} has {tensor_data.shape[0]} "
                    f"frames, expected 1 or {original_frame_count}"
                )
            return sampled_tensor

        return {key: sample_value(child, path + (key,)) for key, child in value.items()}

    sampled_result = sample_value(result)
    sampled_result["time"] = times[selected]
    sampled_result["frame_sampling"] = {
        "method": "nearest_evenly_spaced_time",
        "original_frame_count": int(original_frame_count),
        "retained_frame_count": int(selected.size),
        "target_frame_count": int(validate_max_frames(max_frames)),
        "reduction_applied": bool(selected.size < original_frame_count),
        "original_frame_indices": selected,
    }
    return sampled_result
