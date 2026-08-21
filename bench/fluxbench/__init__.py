"""fluxbench — does flux actually beat the alternatives?

A benchmark harness that runs the *same* multi-task project through several
Claude Code setups (arms) and measures each one on the metrics flux's plan.md
promises to move: context per request, cache-write share, tool errors,
redundant re-reads, Bash output volume, wall time, and dollars per task.

The arms differ in exactly three ways and nothing else: which files are seeded
into the repo, which plugin directories load, and the sequence of prompts each
task is driven with. Model, effort, permissions, tool allow-list, the starting
tree and the grading suite are identical for everyone -- see fairness.md.
"""

__all__ = ["metrics", "spec", "driver", "grade", "runner", "report"]
