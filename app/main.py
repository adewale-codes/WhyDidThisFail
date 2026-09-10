from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

load_dotenv()

from .models import DiagnoseRequest, DiagnoseResponse
from .services.diagnose import diagnose

app = FastAPI(
    title="WhyDidThisFail?",
    description="Detects, parses, and diagnoses failures from raw log text.",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/diagnose", response_model=DiagnoseResponse)
def diagnose_endpoint(req: DiagnoseRequest) -> dict:
    if not req.log or not req.log.strip():
        raise HTTPException(status_code=400, detail="`log` must not be empty.")

    try:
        return diagnose(req.log, req.format_hint)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
