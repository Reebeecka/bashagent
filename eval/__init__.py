"""Evaluation harness. Imports bashagent; bashagent never imports this package.

``make eval`` compares command strings and does not execute them.
``make validate-tasks`` runs hand-written behavior references in one container
at a time. It never runs a destructive command, and it never runs a command
that came from a model.
"""
