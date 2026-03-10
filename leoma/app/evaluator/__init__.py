"""Validator evaluator: get task from API, download from S3, run GPT-4o, POST results."""

from leoma.app.evaluator.main import run_evaluator_loop


__all__ = ["run_evaluator_loop"]
