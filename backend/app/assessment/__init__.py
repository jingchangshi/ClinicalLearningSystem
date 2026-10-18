"""Independent online assessment domain (separate from Training).

Modules in this package must never import the Training scoring, tutor, LLM,
competency or recommendation services; ``tests/test_assessment_isolation.py``
enforces that on the import graph.
"""
