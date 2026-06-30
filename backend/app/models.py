from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Text,
    TIMESTAMP,
    func
)

from sqlalchemy.orm import declarative_base

Base = declarative_base()


class AnalysisHistory(Base):

    __tablename__ = "analysis_history"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    resume_name = Column(
        String(255)
    )

    ats_score = Column(
        Float
    )

    skills_score = Column(
        Float
    )

    experience_score = Column(
        Float
    )

    education_score = Column(
        Float
    )

    certification_score = Column(
        Float
    )

    project_score = Column(
        Float
    )

    matched_skills = Column(
        Text
    )

    missing_skills = Column(
        Text
    )

    suggestions = Column(
        Text
    )

    created_at = Column(
        TIMESTAMP,
        server_default=func.now()
    )