"""
Pure scoring engine for Paid2Pick — no Django dependency.

This is the irreplaceable domain IP (see SCORING_SPEC.md at the repo root).
Keeping it framework-free makes it trivially testable and portable.
"""
from .engine import accustat, grade
from .enums import BetType, Market, Outcome

__all__ = ["grade", "accustat", "BetType", "Market", "Outcome"]
