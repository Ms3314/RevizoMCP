from datetime import date

from sqlalchemy import BigInteger, Boolean, Date, Integer, String, Text, UniqueConstraint
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
