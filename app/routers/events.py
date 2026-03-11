from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_db

router = APIRouter(prefix="/events", tags=["events"])

@router.post("/seasons")
async def create_season(year: int, db: AsyncSession = Depends(get_db)):
    await db.execute(
        text("INSERT INTO seasons (year) VALUES (:year)"),
        {"year": year}
    )
    result = await db.execute(text("SELECT LAST_INSERT_ID()"))
    new_id = result.scalar()
    await db.commit()
    return {"id": new_id, "year": year}

@router.post("/")
async def create_event(season_id: int, event_num: int, event_date: str, site: str, db: AsyncSession = Depends(get_db)):
    await db.execute(
        text("INSERT INTO events (season_id, event_num, event_date, site) VALUES (:sid, :enum, :date, :site)"),
        {"sid": season_id, "enum": event_num, "date": event_date, "site": site}
    )
    result = await db.execute(text("SELECT LAST_INSERT_ID()"))
    new_id = result.scalar()
    await db.commit()
    return {"id": new_id, "season_id": season_id, "event_num": event_num}
