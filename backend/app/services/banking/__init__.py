"""Deterministic banking engine.

Pipeline: ``loader`` → ``categorizer`` / ``recurring`` → ``projection`` →
``options`` → ``engine.build_decision``. Nothing in this package calls an AI
provider; every number the client sees is computed here.
"""
