from datetime import UTC, datetime, timedelta
import unittest

from app.services.adaptive_engine import MasteryState, sm2_update


class AdaptiveEngineTests(unittest.TestCase):
    def test_sm2_update_advances_correct_attempts(self) -> None:
        now = datetime(2026, 9, 2, tzinfo=UTC)
        first = sm2_update(MasteryState(), was_correct=True, now=now)
        second = sm2_update(first, was_correct=True, now=now)
        third = sm2_update(second, was_correct=True, now=now)

        self.assertEqual(first.streak, 1)
        self.assertEqual(first.interval_days, 1)
        self.assertEqual(first.next_review_at, now + timedelta(days=1))
        self.assertEqual(second.streak, 2)
        self.assertEqual(second.interval_days, 6)
        self.assertEqual(third.streak, 3)
        self.assertGreater(third.interval_days, second.interval_days)

    def test_sm2_update_resets_on_incorrect_attempt(self) -> None:
        now = datetime(2026, 9, 2, tzinfo=UTC)
        state = MasteryState(ease_factor=2.5, interval_days=6, streak=2)
        updated = sm2_update(state, was_correct=False, now=now)

        self.assertEqual(updated.streak, 0)
        self.assertEqual(updated.interval_days, 1)
        self.assertEqual(updated.ease_factor, 2.3)
        self.assertEqual(updated.next_review_at, now + timedelta(days=1))


if __name__ == "__main__":
    unittest.main()
