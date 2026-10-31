"""Response/request schemas for the JSON API consumed by the React SPA.

Kept in sync with web/src/api/types.ts (the SPA is the only consumer).
"""

from pydantic import BaseModel, Field


class ProblemOut(BaseModel):
    problem_id: str
    problem_link: str
    difficulty: str
    problem_description: str
    topics: list[str] = Field(default_factory=list)
    solved: bool
    last_solved: str | None = None  # ISO date
    interval_days: int
    repetitions: int
    mistakes: str
    watch_out: str | None = None


class AttemptOut(BaseModel):
    date: str
    solved: bool
    mistakes: str
    tags: list[str] = Field(default_factory=list)


class ByDifficulty(BaseModel):
    easy: int = 0
    medium: int = 0
    hard: int = 0


class Stats(BaseModel):
    total: int
    solved: int
    backlog: int
    due_today: int
    by_difficulty: ByDifficulty


class DueCard(BaseModel):
    p: ProblemOut
    watch_out: str | None = None
    when: str  # "never attempted" | "Nd overdue" | "due today"


class WeakPoint(BaseModel):
    tag: str
    count: int
    last_seen: str
    recent_problems: list[str] = Field(default_factory=list)
    pct: int


class DashboardRow(BaseModel):
    p: ProblemOut
    due: bool
    history: list[AttemptOut] = Field(default_factory=list)


class DashboardData(BaseModel):
    stats: Stats
    due: list[DueCard] = Field(default_factory=list)
    weak_points: list[WeakPoint] = Field(default_factory=list)
    rows: list[DashboardRow] = Field(default_factory=list)
    today_long: str
    filters: dict = Field(default_factory=dict)


class SessionUser(BaseModel):
    id: int
    email: str
    display_name: str


class AddProblemIn(BaseModel):
    title: str
    link: str = ""
    difficulty: str = "medium"
    topics: str = ""  # comma-separated, mirrors the old form
    description: str = ""


class LeetCodeStatus(BaseModel):
    connected: bool
    username: str
    notice: str | None = None


class LeetCodeSettingsIn(BaseModel):
    username: str
    session_cookie: str = ""


class StudyPlanSettingsIn(BaseModel):
    revisions_per_session: int
    backlog_per_session: int


class SolveIn(BaseModel):
    solved: bool = True
    mistakes: str | None = None
    mistake_tags: list[str] | None = None
