#!/usr/bin/env python3
"""
Private sibling: marked-region ownership validation for ``sync_ci_gate_jobs``.

The hosted-job and consumer-``needs`` regions must be structurally owned by
the exact top-level jobs they name; the facade re-exports this module's name.
"""

from __future__ import annotations

from typing import Any

from _sync_ci_gate_catalog import JOB_BEGIN, JOB_END, NEEDS_BEGIN, NEEDS_END
from _sync_ci_gate_core import (
    GeneratorError,
    _all_markers_present,
    _line_index,
    _locate_hosted_job_headers,
    _top_level_job_headers,
)


def _validate_hosted_marker_region(
    lines: list[str],
    headers: list[tuple[int, str]],
    header_locations: dict[str, int],
    job_begin: int,
    job_end: int,
) -> None:
    """
    Prove the hosted-job marker region owns exactly the named top-level jobs.

    The region's job IDs may be stale (registry ci_job rename, F-005);
    display-name ownership keeps the marked-region checks independent of
    generated job text while still requiring exactly the hosted jobs.
    """
    located_starts = _locate_hosted_job_headers(lines, allow_missing=True)
    located_by_index = {index: job_id for index, job_id in headers}
    located_ids = tuple(located_by_index[position] for position in located_starts)
    enclosed_jobs = tuple(job_id for index, job_id in headers if job_begin < index < job_end)
    if enclosed_jobs != located_ids:
        raise GeneratorError(
            "ci.yml: hosted job marker region must contain exactly the named top-level jobs "
            f"in order; got {list(enclosed_jobs)!r}"
        )
    if job_begin + 1 != header_locations[located_ids[0]]:
        raise GeneratorError("ci.yml: hosted job begin marker is not adjacent to its first job")
    last_job_start = header_locations[located_ids[-1]]
    if job_end <= last_job_start:
        raise GeneratorError("ci.yml: hosted job end marker is inside the last generated job")
    next_job_header = next((index for index, _ in headers if index > last_job_start), len(lines))
    if any(line.strip() for line in lines[job_end + 1 : next_job_header]):
        raise GeneratorError("ci.yml: hosted job end marker is not at the job-region boundary")
    if any("GENERATED:" in line for line in lines[job_begin + 1 : job_end]):
        raise GeneratorError("ci.yml: hosted job region contains nested generated markers")


def _validate_needs_marker_regions(
    lines: list[str],
    headers: list[tuple[int, str]],
    header_locations: dict[str, int],
) -> None:
    """Prove every consumer needs region is owned by its top-level job."""
    for consumer, begin in NEEDS_BEGIN.items():
        start = _line_index(lines, begin)[0]
        end = _line_index(lines, NEEDS_END[consumer])[0]
        if consumer not in header_locations:
            raise GeneratorError(f"ci.yml: needs marker consumer job {consumer!r} is missing")
        consumer_start = header_locations[consumer]
        consumer_end = next((index for index, _ in headers if index > consumer_start), len(lines))
        if not consumer_start < start < end < consumer_end:
            raise GeneratorError(
                f"ci.yml: needs marker region for {consumer} is not owned by its top-level job"
            )
        body = [line for line in lines[start + 1 : end] if line.strip()]
        if len(body) != 1 or not body[0].lstrip().startswith("needs:"):
            raise GeneratorError(f"ci.yml: needs marker region for {consumer} is malformed")


def _validate_marked_regions(lines: list[str], gates: list[dict[str, Any]]) -> None:
    if not _all_markers_present(lines):
        raise GeneratorError("ci.yml: generated marker pairs are incomplete or duplicated")
    # Marker regions must be structurally owned by the exact top-level jobs they
    # name.  Line matching alone is insufficient: a marker moved into another
    # job (or into a scalar that happens to contain marker-looking text) must not
    # authorize rewriting that job's bytes.
    jobs_lines = _line_index(lines, "jobs:")
    if len(jobs_lines) != 1:
        raise GeneratorError("ci.yml: expected exactly one top-level jobs section")
    headers = _top_level_job_headers(lines)
    header_locations = {job_id: index for index, job_id in headers}
    job_begin = _line_index(lines, JOB_BEGIN)[0]
    job_end = _line_index(lines, JOB_END)[0]
    if not jobs_lines[0] < job_begin < job_end:
        raise GeneratorError("ci.yml: hosted job markers are not owned by the jobs section")
    _validate_hosted_marker_region(lines, headers, header_locations, job_begin, job_end)
    _validate_needs_marker_regions(lines, headers, header_locations)
