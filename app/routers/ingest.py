from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.ingest.csv_parser import parse_csv

router = APIRouter(prefix="/ingest", tags=["ingest"])

@router.post("/csv")
async def ingest_csv(
    event_id:int,
    file:UploadFile=File(...),
    db: AsyncSession = Depends(get_db)
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code = 400, detail = "File must be a csv")
    
    contents = await file.read()
    result = await parse_csv(contents, event_id, db)
    return result