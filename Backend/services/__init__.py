"""
Backend.services — YouAI Service Layer
=======================================
High-level orchestration services that coordinate LLMs, memory,
social fetching, authentication, and system-level operations.

Modules:
    twin_orchestrator  — Core Digital Twin profiling and data pipeline
    auth_connector     — Account credential collection and browser session vault
    watchdog           — Self-repair supervisor that restarts and patches Start.py
    reset_manager      — Application and memory reset utilities
"""
