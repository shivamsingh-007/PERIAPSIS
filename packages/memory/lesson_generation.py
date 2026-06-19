from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from packages.logging.structured import get_logger

logger = get_logger("lesson_generation")


class CandidateLesson(BaseModel):
    lesson_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    title: str
    description: str
    category: str
    confidence: float = 0.0
    evidence: list[str] = Field(default_factory=list)
    source_runs: list[str] = Field(default_factory=list)
    suggested_action: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "candidate"


class LessonGenerator:
    def __init__(self):
        self._lessons: dict[uuid.UUID, CandidateLesson] = {}
        self._patterns: list[dict] = []

    async def generate_from_reflections(
        self,
        reflections: list[dict],
        min_occurrences: int = 2,
    ) -> list[CandidateLesson]:
        pattern_counts: dict[str, list[dict]] = {}

        for reflection in reflections:
            pattern = reflection.get("pattern", "")
            if pattern:
                if pattern not in pattern_counts:
                    pattern_counts[pattern] = []
                pattern_counts[pattern].append(reflection)

        candidates = []
        for pattern, occurrences in pattern_counts.items():
            if len(occurrences) >= min_occurrences:
                lesson = self._create_lesson_from_pattern(pattern, occurrences)
                candidates.append(lesson)
                self._lessons[lesson.lesson_id] = lesson

        return candidates

    async def generate_from_errors(
        self,
        errors: list[dict],
    ) -> list[CandidateLesson]:
        error_groups: dict[str, list[dict]] = {}
        for error in errors:
            error_type = error.get("type", "unknown")
            if error_type not in error_groups:
                error_groups[error_type] = []
            error_groups[error_type].append(error)

        candidates = []
        for error_type, group in error_groups.items():
            if len(group) >= 2:
                lesson = CandidateLesson(
                    title=f"Avoid repeated {error_type} errors",
                    description=f"Observed {len(group)} instances of {error_type} errors across runs",
                    category="error_prevention",
                    confidence=min(0.9, len(group) * 0.2),
                    evidence=[e.get("message", "") for e in group[:5]],
                    source_runs=[e.get("run_id", "") for e in group[:5]],
                    suggested_action=f"Add validation or guard for {error_type} before execution",
                )
                candidates.append(lesson)
                self._lessons[lesson.lesson_id] = lesson

        return candidates

    async def generate_from_successes(
        self,
        successes: list[dict],
    ) -> list[CandidateLesson]:
        strategy_counts: dict[str, list[dict]] = {}
        for success in successes:
            strategy = success.get("strategy", "")
            if strategy:
                if strategy not in strategy_counts:
                    strategy_counts[strategy] = []
                strategy_counts[strategy].append(success)

        candidates = []
        for strategy, occurrences in strategy_counts.items():
            if len(occurrences) >= 2:
                lesson = CandidateLesson(
                    title=f"Effective strategy: {strategy}",
                    description=f"Strategy '{strategy}' succeeded {len(occurrences)} times",
                    category="best_practice",
                    confidence=min(0.95, 0.5 + len(occurrences) * 0.1),
                    evidence=[o.get("detail", "") for o in occurrences[:5]],
                    source_runs=[o.get("run_id", "") for o in occurrences[:5]],
                    suggested_action=f"Consider using '{strategy}' as default for similar tasks",
                )
                candidates.append(lesson)
                self._lessons[lesson.lesson_id] = lesson

        return candidates

    def _create_lesson_from_pattern(self, pattern: str, occurrences: list[dict]) -> CandidateLesson:
        return CandidateLesson(
            title=f"Pattern: {pattern}",
            description=f"Recurring pattern observed {len(occurrences)} times",
            category="pattern_recognition",
            confidence=min(0.9, len(occurrences) * 0.15),
            evidence=[o.get("detail", str(o))[:200] for o in occurrences[:5]],
            source_runs=[o.get("run_id", "") for o in occurrences[:5]],
            suggested_action=f"Address recurring pattern: {pattern}",
        )

    def get_lesson(self, lesson_id: uuid.UUID) -> CandidateLesson | None:
        return self._lessons.get(lesson_id)

    def list_lessons(self, status: str | None = None) -> list[CandidateLesson]:
        lessons = list(self._lessons.values())
        if status:
            lessons = [l for l in lessons if l.status == status]
        return lessons

    def approve_lesson(self, lesson_id: uuid.UUID) -> bool:
        lesson = self._lessons.get(lesson_id)
        if lesson:
            lesson.status = "approved"
            return True
        return False

    def reject_lesson(self, lesson_id: uuid.UUID) -> bool:
        lesson = self._lessons.get(lesson_id)
        if lesson:
            lesson.status = "rejected"
            return True
        return False

    def get_summary(self) -> dict:
        lessons = list(self._lessons.values())
        return {
            "total": len(lessons),
            "candidates": sum(1 for l in lessons if l.status == "candidate"),
            "approved": sum(1 for l in lessons if l.status == "approved"),
            "rejected": sum(1 for l in lessons if l.status == "rejected"),
        }


lesson_generator = LessonGenerator()
