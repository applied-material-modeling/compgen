#!/usr/bin/env python3
"""
Extract 'Runtime: ... minutes' values from a simulation log file
and plot a histogram of the runtimes (in minutes).
"""

import re
from pathlib import Path

import matplotlib.pyplot as plt

# Directory containing this script
SCRIPT_DIR = Path(__file__).resolve().parent

# Path to the log file
LOG_PATH =  "/lus/flare/projects/ai4ns-composites/brennan/fracture_simulations/logs/random_brb/demo_aurora_x4703c6s3b0n0.log" # "/lus/flare/projects/ai4ns-composites/brennan/fracture_simulations/logs/demo_aurora_x4113c0s0b0n0.log"

# Precompile the regex for speed.
# Matches: "Runtime: 11846.77 seconds (197.45 minutes)"
RUNTIME_RE = re.compile(
    r"Runtime:\s*([\d.]+)\s*seconds\s*\(([\d.]+)\s*minutes\)"
)


def extract_runtimes_minutes(log_path):
    """
    Efficiently scan the log file line-by-line and extract runtime
    values (in minutes) using a precompiled regex.
    """
    minutes = []

    with open(log_path, "r", errors="ignore") as f:
        for line in f:
            # Quick pre-filter avoids running regex on every single line
            if "Runtime:" not in line:
                continue

            match = RUNTIME_RE.search(line)
            if match:
                minutes.append(float(match.group(2)))

    return minutes


def plot_histogram(minutes, bins=50, filename="runtime_histogram.png"):
    # Save the figure in the same directory as this script
    save_path = SCRIPT_DIR / filename

    plt.figure(figsize=(10, 6))
    plt.hist(minutes, bins=bins, color="steelblue", edgecolor="black")
    plt.xlabel("Runtime (minutes)")
    plt.ylabel("Count")
    plt.title(f"Distribution of Problem Runtimes (n={len(minutes)})")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    print(f"Figure saved to: {save_path}")
    plt.show()


def main():
    print(f"Loading and parsing: {LOG_PATH}")
    minutes = extract_runtimes_minutes(LOG_PATH)

    if not minutes:
        print("No runtime entries found. Check the log format or path.")
        return

    print(f"Found {len(minutes)} runtime entries.")
    print(
        f"Min: {min(minutes):.2f} min, "
        f"Max: {max(minutes):.2f} min, "
        f"Mean: {sum(minutes) / len(minutes):.2f} min"
    )

    plot_histogram(minutes)


if __name__ == "__main__":
    main()