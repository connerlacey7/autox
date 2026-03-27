from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_db

router = APIRouter(prefix="/drivers", tags=["drivers"])

@router.get("/")
async def list_drivers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("SELECT id, first_name, last_name, member_number, region FROM drivers ORDER BY last_name, first_name")
    )
    rows = result.fetchall()
    return [dict(row._mapping) for row in rows]

@router.get("/{driver_id}")
async def get_driver(driver_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("SELECT id, first_name, last_name, member_number, region FROM drivers WHERE id = :did"),
        {"did": driver_id}
    )
    row = result.fetchone()
    return dict(row._mapping) if row else {}
