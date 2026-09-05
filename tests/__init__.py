"""Test package. Puts the orchestrator's scripts dir (which holds `auditlib`) on sys.path
so tests can `import auditlib.*` without installation. No live network is used anywhere.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPTS = os.path.join(_ROOT, "skills", "audit-orchestrator", "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
