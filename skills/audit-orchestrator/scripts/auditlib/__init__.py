"""auditlib — shared, standard-library-only engine for the brand-ai-readiness-audit marketplace.

Physically hosted under the entrypoint skill (audit-orchestrator) but located at
runtime by every skill's runner via `bootstrap.find_auditlib()`, so each skill can
run standalone AND be composed by the orchestrator. No third-party dependencies.
"""

__all__ = ["http", "htmlparse", "report"]
