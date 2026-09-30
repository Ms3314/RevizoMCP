from datetime import date, datetime, timezone

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Problem(Base):
    __tablename__ = "problems"
    __table_args__ = (UniqueConstraint("user_id", "problem_id", name="uq_user_problem"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1, index=True)
    problem_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    problem_link: Mapped[str] = mapped_column(String, nullable=False, default="")
    difficulty: Mapped[str] = mapped_column(String, nullable=False, default="medium")
    problem_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    last_solved: Mapped[date | None] = mapped_column(Date, nullable=True)
    solved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    topics: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    mistakes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    interval_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    repetitions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        return f"<Problem {self.problem_id!r} solved={self.solved} rep={self.repetitions}>"


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1, index=True)
    problem_pk: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("problems.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attempt_date: Mapped[date] = mapped_column(Date, nullable=False)
    solved: Mapped[bool] = mapped_column(Boolean, nullable=False)
    mistakes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    mistake_tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # LeetCode's unique submission id, when this attempt IS a synced submission.
    # NULL for manual attempts (sittings reported in chat, non-LeetCode problems).
    # The unique constraint doubles as the sync-dedup index.
    lc_submission_id: Mapped[str | None] = mapped_column(String, nullable=True, unique=True)

    def __repr__(self) -> str:
        return f"<Attempt problem={self.problem_pk} date={self.attempt_date} solved={self.solved}>"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    supabase_sub: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    email: Mapped[str] = mapped_column(String, nullable=False, default="")
    display_name: Mapped[str] = mapped_column(String, nullable=False, default="")
    leetcode_username: Mapped[str] = mapped_column(String, nullable=False, default="")
    leetcode_session: Mapped[str] = mapped_column(Text, nullable=False, default="")
    last_synced_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)

    def __repr__(self) -> str:
        return f"<User {self.email!r} sub={self.supabase_sub[:8]}>"


class LeetCodeProblem(Base):
    """A LeetCode problem imported for one Revizo user."""

    __tablename__ = "leetcode_problems"
    __table_args__ = (UniqueConstraint("user_id", "slug", name="uq_user_leetcode_slug"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    difficulty: Mapped[str] = mapped_column(String, nullable=False, default="medium")
    topics: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    problem_pk: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("problems.id", ondelete="SET NULL"), nullable=True
    )
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class LeetCodeSyncState(Base):
    """Per-account checkpoint for incremental LeetCode imports."""

    __tablename__ = "leetcode_sync_state"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    username: Mapped[str] = mapped_column(String, nullable=False, default="")
    solved_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OAuthClient(Base):
    __tablename__ = "oauth_clients"

    client_id: Mapped[str] = mapped_column(String, primary_key=True)
    redirect_uris: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    client_name: Mapped[str] = mapped_column(String, nullable=False, default="")
    created_at: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)


class Strategy(Base):
    """Per-user session strategy: how many revisions vs backlog problems to suggest."""

    __tablename__ = "strategies"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    revisions_per_session: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    backlog_per_session: Mapped[int] = mapped_column(Integer, nullable=False, default=2)

    def __repr__(self) -> str:
        return f"<Strategy user={self.user_id} rev={self.revisions_per_session} back={self.backlog_per_session}>"
