from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine
from app.models import Base
from app.routes.history import router as history_router

from app.routes.analyzer import router as analyzer_router

Base.metadata.create_all(bind=engine)
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    analyzer_router,
    prefix="/api"
)

app.include_router(
    history_router,
    prefix="/api"
)

@app.get("/")
def home():
    return {
        "message": "ATS Backend Running"
    }