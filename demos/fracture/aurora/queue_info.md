# Aurora Queue Information

The following queue limits and routing information are transcribed from the
Aurora queue information page. Queue availability and limits can change; check
the current system documentation before submitting a large or long-running
job.

## Queues available to `qsub`

These are the queues that can be specified directly with `qsub -q <queue>`:

| Queue | Minimum nodes | Maximum nodes | Minimum walltime | Maximum walltime | Notes |
|---|---:|---:|---:|---:|---|
| `debug` | 1 | 2 | 5 min | 1 hr | 64 nodes non-exclusively; maximum 1 job running, accruing, or queued per user |
| `debug-scaling` | 2 | 256 | 5 min | 1 hr | Maximum 1 job running, accruing, or queued per user |
| `prod` | 256 | 10,624 | 5 min | 24 hrs | Routing queue for small, medium, and large jobs; see the execution-queue table below |
| `capacity` | 1 | 16 | 5 min | 7 days (168 hrs) | Maximum 512 nodes across all jobs; maximum 5 jobs queued or running; maximum 2 jobs running per user |
| `visualization` | 1 | 32 | 5 min | 8 hrs | By request only; non-exclusive nodes |

## `prod` routing queues

`prod` is the routing queue for production jobs. Do **not** submit directly to
the execution queues below; submit to `prod` and the system routes the job to
an appropriate queue.

| Execution queue | Minimum nodes | Maximum nodes | Minimum walltime | Maximum walltime | Notes |
|---|---:|---:|---:|---:|---|
| `small` | 256 | 1,024 | 5 min | 12 hrs | Routed from `prod` |
| `medium` | 1,025 | 1,999 | 5 min | 18 hrs | Routed from `prod` |
| `large` | 2,000 | 10,624 | 5 min | 24 hrs | Routed from `prod` |
| `backfill-small` | 256 | 1,024 | 5 min | 12 hrs | Low priority; negative project balance |
| `backfill-medium` | 1,025 | 1,999 | 5 min | 18 hrs | Low priority; negative project balance |
| `backfill-large` | 2,000 | 10,624 | 5 min | 24 hrs | Low priority; negative project balance; theoretical maximum; stable maximum node count may vary |

## Practical choices for fracture jobs

| Use case | Queue to request | Relevant limits |
|---|---|---|
| Short debug or setup check | `debug` | 1–2 nodes, up to 1 hour |
| Larger short scaling test | `debug-scaling` | 2–256 nodes, up to 1 hour |
| Production job using fewer than 256 nodes | `capacity` | 1–16 nodes, up to 7 days; subject to capacity and per-user limits |
| Production job using 256 or more nodes | `prod` | 256–10,624 nodes, up to 24 hours; routed by node count and walltime |
| Visualization | `visualization` | 1–32 non-exclusive nodes, up to 8 hours; request access if needed |

## PBS examples

Request a one-node debug job:

```bash
#PBS -l select=1
#PBS -l walltime=01:00:00
#PBS -q debug
```

Request a small production-capacity job:

```bash
#PBS -l select=16
#PBS -l walltime=7:00:00
#PBS -q capacity
```

Request a production job with at least 256 nodes:

```bash
#PBS -l select=256
#PBS -l walltime=12:00:00
#PBS -q prod
```

For the existing fracture submission scripts, `select` is the number of
Aurora nodes and `walltime` must fit within the selected queue's limits. The
current 2D fixed and 3D fixed scripts use `prod`; the debug scripts use
`debug`.
