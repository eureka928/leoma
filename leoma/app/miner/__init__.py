"""Miner CLI commands for Leoma.

Provides commands for:
- push: Deploy I2V model to Chutes
- commit: Commit model info to blockchain
"""

from leoma.app.miner.main import commit_command, push_command


__all__ = ["push_command", "commit_command"]
