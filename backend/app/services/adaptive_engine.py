from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True)
class MasteryState:
    ease_factor: float = 2.5
    interval_days: int = 0
    next_review_at: datetime | None = None
    streak: int = 0


def sm2_update(
    mastery_row: MasteryState,
    was_correct: bool,
    now: datetime | None = None,
) -> MasteryState:
    current_time = now or datetime.now(UTC)

    if not was_correct:
        return replace(
            mastery_row,
            ease_factor=max(1.3, mastery_row.ease_factor - 0.2),
            interval_days=1,
            next_review_at=current_time + timedelta(days=1),
            streak=0,
        )

    streak = mastery_row.streak + 1
    ease_factor = min(3.0, mastery_row.ease_factor + 0.1)
    if streak == 1:
        interval_days = 1
    elif streak == 2:
        interval_days = 6
    else:
        interval_days = max(1, round(mastery_row.interval_days * ease_factor))

    return replace(
        mastery_row,
        ease_factor=ease_factor,
        interval_days=interval_days,
        next_review_at=current_time + timedelta(days=interval_days),
        streak=streak,
    )
