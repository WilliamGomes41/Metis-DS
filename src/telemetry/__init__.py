"""Metis telemetry: the one place every operational signal lands.

Producers stay where the work happens (request diagnostics, console performance,
structured logging, processing trace, publication evidence, publish refusals and
the Storeopdracht). They all feed this hub, which owns the event model, the
correlation context, bounded local storage, safe error fingerprints, analysis,
remediation guidance and the /telemetry page. Operational evidence only: never
domain state, never an authority.
"""
from src.telemetry.errors import exception_evidence
from src.telemetry.hub import HUB, record_event
from src.telemetry.install import install_telemetry

__all__ = ["HUB", "exception_evidence", "install_telemetry", "record_event"]
