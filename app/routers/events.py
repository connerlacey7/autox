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


@router.get("/seasons")
async def list_seasons(db: AsyncSession = Depends(get_db)):
    result = await db.execute(text("SELECT id, year FROM seasons ORDER BY year DESC"))
    rows = result.fetchall()
    return [dict(row._mapping) for row in rows]

@router.get("/")
async def list_events(season_id: int = None, db: AsyncSession = Depends(get_db)):
    if season_id:
        result = await db.execute(
            text("SELECT id, season_id, event_num, event_date, site FROM events WHERE season_id = :sid ORDER BY event_num"),
            {"sid": season_id}
        )
    else:
        result = await db.execute(
            text("SELECT id, season_id, event_num, event_date, site FROM events ORDER BY season_id, event_num")
        )
    rows = result.fetchall()
    return [dict(row._mapping) for row in rows]
