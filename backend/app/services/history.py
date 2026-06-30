import json

from app.database import SessionLocal
from app.models import AnalysisHistory


def save_analysis(
    resume_name,
    result
):

    db = SessionLocal()

    try:

        history = AnalysisHistory(

            resume_name=resume_name,

            ats_score=result.overall_score,

            skills_score=result.skills.score,

            experience_score=result.experience.score,

            education_score=result.education.score,

            certification_score=result.certifications.score,

            project_score=result.projects.score,

            matched_skills=json.dumps(
                result.skills.matched
            ),

            missing_skills=json.dumps(
                result.skills.missing
            ),

            suggestions=json.dumps(
                result.suggestions
            )

        )

        db.add(history)

        db.commit()

    finally:

        db.close()