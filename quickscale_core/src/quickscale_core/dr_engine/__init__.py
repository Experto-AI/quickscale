"""Centrally owned DR engine for QuickScale.

Platform-level disaster-recovery orchestration extracted from the embeddable
backups module. See docs/technical/decisions.md § Disaster Recovery Engine
Boundary Contract (F5 / M10) for the authoritative target boundary.

Layers
------
primitives
    Snapshot and archive primitives (F5.2a) — Django-free.
recovery
    Restore/orchestration contracts and helpers (F5.2b) — Django-free.
verification
    Snapshot verification and rollback-pin lifecycle (F5.2b) — Django-free.
adapter
    Explicit typed boundary (F5.3) between CLI orchestration and the
    Django-backed DR services.  Replaces the hidden docker-exec /
    management-command / env-var / stdout-JSON protocol with a
    registered-function API called through the ``dr_adapter_call``
    management command bridge.
"""
