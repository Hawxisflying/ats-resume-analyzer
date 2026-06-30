from fastapi import APIRouter
from app.database import SessionLocal
from app.models import AnalysisHistory

router = APIRouter()


@router.get("/history")
def get_history():

    db = SessionLocal()

    try:

        rows = (
            db.query(AnalysisHistory)
            .order_by(AnalysisHistory.id.desc())
            .all()
        )

        return rows

    finally:

        db.close()