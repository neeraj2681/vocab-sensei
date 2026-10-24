"""Enums shared across layers (domain modules and database models)."""

from enum import StrEnum


class WordStatus(StrEnum):
    NEW = "new"  # never answered
    LEARNING = "learning"
    LEARNED = "learned"  # score reached the threshold; decays weekly
    KNOWN = "known"  # user said they already know it; never quizzed
