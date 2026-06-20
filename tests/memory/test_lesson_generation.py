from __future__ import annotations
"""Tests for packages.memory.lesson_generation - LessonGenerator."""

import uuid

import pytest

from packages.memory.lesson_generation import CandidateLesson, LessonGenerator


class TestLessonGenerator:
    def setup_method(self):
        self.generator = LessonGenerator()

    @pytest.mark.asyncio
    async def test_generate_from_reflections_with_pattern(self):
        reflections = [
            {"pattern": "timeout_error", "detail": "DB timeout", "run_id": "r1"},
            {"pattern": "timeout_error", "detail": "API timeout", "run_id": "r2"},
            {"pattern": "timeout_error", "detail": "Cache timeout", "run_id": "r3"},
        ]
        lessons = await self.generator.generate_from_reflections(reflections, min_occurrences=2)
        assert len(lessons) == 1
        assert lessons[0].category == "pattern_recognition"

    @pytest.mark.asyncio
    async def test_generate_from_reflections_below_threshold(self):
        reflections = [
            {"pattern": "rare_pattern", "detail": "once", "run_id": "r1"},
        ]
        lessons = await self.generator.generate_from_reflections(reflections, min_occurrences=2)
        assert len(lessons) == 0

    @pytest.mark.asyncio
    async def test_generate_from_errors(self):
        errors = [
            {"type": "timeout", "message": "DB timeout", "run_id": "r1"},
            {"type": "timeout", "message": "API timeout", "run_id": "r2"},
        ]
        lessons = await self.generator.generate_from_errors(errors)
        assert len(lessons) == 1
        assert lessons[0].category == "error_prevention"

    @pytest.mark.asyncio
    async def test_generate_from_errors_single(self):
        errors = [{"type": "timeout", "message": "once", "run_id": "r1"}]
        lessons = await self.generator.generate_from_errors(errors)
        assert len(lessons) == 0

    @pytest.mark.asyncio
    async def test_generate_from_successes(self):
        successes = [
            {"strategy": "parallel_fetch", "detail": "fast", "run_id": "r1"},
            {"strategy": "parallel_fetch", "detail": "reliable", "run_id": "r2"},
        ]
        lessons = await self.generator.generate_from_successes(successes)
        assert len(lessons) == 1
        assert lessons[0].category == "best_practice"

    @pytest.mark.asyncio
    async def test_generate_from_successes_single(self):
        successes = [{"strategy": "only_once", "detail": "d", "run_id": "r1"}]
        lessons = await self.generator.generate_from_successes(successes)
        assert len(lessons) == 0

    def test_get_lesson(self):
        lesson = CandidateLesson(title="t", description="d", category="c")
        self.generator._lessons[lesson.lesson_id] = lesson
        found = self.generator.get_lesson(lesson.lesson_id)
        assert found is not None

    def test_get_lesson_not_found(self):
        assert self.generator.get_lesson(uuid.uuid4()) is None

    def test_approve_lesson(self):
        lesson = CandidateLesson(title="t", description="d", category="c")
        self.generator._lessons[lesson.lesson_id] = lesson
        result = self.generator.approve_lesson(lesson.lesson_id)
        assert result is True
        assert lesson.status == "approved"

    def test_reject_lesson(self):
        lesson = CandidateLesson(title="t", description="d", category="c")
        self.generator._lessons[lesson.lesson_id] = lesson
        result = self.generator.reject_lesson(lesson.lesson_id)
        assert result is True
        assert lesson.status == "rejected"

    def test_approve_nonexistent(self):
        assert self.generator.approve_lesson(uuid.uuid4()) is False

    def test_reject_nonexistent(self):
        assert self.generator.reject_lesson(uuid.uuid4()) is False

    def test_get_summary(self):
        l1 = CandidateLesson(title="t1", description="d", category="c", status="candidate")
        l2 = CandidateLesson(title="t2", description="d", category="c", status="approved")
        self.generator._lessons[l1.lesson_id] = l1
        self.generator._lessons[l2.lesson_id] = l2
        summary = self.generator.get_summary()
        assert summary["total"] == 2
        assert summary["candidates"] == 1
        assert summary["approved"] == 1

    def test_list_lessons_filtered(self):
        l1 = CandidateLesson(title="t1", description="d", category="c", status="candidate")
        l2 = CandidateLesson(title="t2", description="d", category="c", status="approved")
        self.generator._lessons[l1.lesson_id] = l1
        self.generator._lessons[l2.lesson_id] = l2
        candidates = self.generator.list_lessons(status="candidate")
        assert len(candidates) == 1
