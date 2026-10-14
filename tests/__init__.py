"""Repository test helpers, including imports from DEV worker subprocesses.

An explicit package keeps dependency packages named ``tests`` from shadowing
these local helpers when a new interpreter starts outside unittest discovery.
"""
