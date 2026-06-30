from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
import asyncio
from starlette.concurrency import run_in_threadpool

from app.services.pdf_parser import extract_text_from_pdf

from app.services.parser import (
    parse_resume,
    parse_job_description
)

from app.services.extractor import (
    extract_resume,
    extract_job_description
)

from app.services.analyzer import analyze
from app.services.history import save_analysis

router = APIRouter()


class AnalyzeRequest(BaseModel):
    resume_text: str
    jd_text: str
    resume_name: str = "Uploaded Resume"


@router.post("/upload")
async def upload_resume(file: UploadFile = File(...)):

    try:
        text = await asyncio.wait_for(
            run_in_threadpool(extract_text_from_pdf, file.file),
            timeout=30,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=422,
            detail=(
                "This PDF took too long to process (it may have complex "
                "graphics or be a scanned/image-only PDF). Try exporting "
                "your resume as a simpler PDF, or paste the text directly."
            ),
        )

    return {
        "text": text
    }


@router.post("/analyze")
async def analyze_resume_route(data: AnalyzeRequest):

    # Parse
    parsed_resume = parse_resume(
        data.resume_text
    )

    parsed_jd = parse_job_description(
        data.jd_text
    )

    # Extract
    resume = extract_resume(
        parsed_resume
    )

    jd = extract_job_description(
        parsed_jd
    )

    # Analyze
    result = analyze(
        resume,
        jd
    )

    # Save to history (this was missing — nothing was ever persisted)
    save_analysis(
        data.resume_name,
        result
    )

    return result