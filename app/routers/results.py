from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_db

router = APIRouter(prefix="/results", tags=["results"])


@router.get("/event/{event_id}")
async def event_results(event_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("""
        SELECT d.first_name, d.last_name, r.class, r.car_number,
             r.raw_time, r.cones, r.raw_time + (r.cones*2) AS total_time,
             r.pax_index, r.pax_time
        FROM results r
        JOIN drivers d on d.id = r.driver_id
        WHERE r.event_id = :eid
        ORDER BY r.pax_time
        """),
        {"eid": event_id}
    )
    rows = result.fetchall()
    return [dict(row._mapping) for row in rows]

@router.get("/driver/{driver_id}")
async def driver_history(driver_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("""
            SELECT e.event_num, e.event_date, e.site,
                   r.class, r.car_number, r.raw_time, r.cones,
                   r.raw_time + (r.cones * 2) AS total_time, r.pax_time
            FROM results r
            JOIN events e ON e.id = r.event_id
            WHERE r.driver_id = :did
            ORDER BY e.event_date
        """),
        {"did": driver_id}
    )
    rows = result.fetchall()
    return [dict(row._mapping) for row in rows]

@router.get("/standings/{season_id}")
async def season_standings(season_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("""
            SELECT d.first_name, d.last_name,
                   COUNT(r.id) AS events_entered,
                   SUM(
                       (SELECT MIN(r2.pax_time) FROM results r2 WHERE r2.event_id = r.event_id)
                       / r.pax_time * 100
                   ) AS total_pax_points,
                   SUM(
                       (SELECT MIN(r3.raw_time + r3.cones * 2) FROM results r3 WHERE r3.event_id = r.event_id)
                       / (r.raw_time + r.cones * 2) * 100
                   ) AS total_raw_points
            FROM results r
            JOIN drivers d ON d.id = r.driver_id
            JOIN events e ON e.id = r.event_id
            WHERE e.season_id = :sid
            GROUP BY r.driver_id, d.first_name, d.last_name
            ORDER BY total_pax_points DESC
        """),
        {"sid": season_id}
    )
    rows = result.fetchall()
    return [dict(row._mapping) for row in rows]



@router.get("/standings/pax/{season_id}")
async def pax_standings(season_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("""
        WITH season_events AS (
             SELECT COUNT(DISTINCT id) AS total FROM events WHERE season_id = :sid
             ),
        event_scores AS (
             SELECT r.driver_id, d.first_name, d.last_name, r.event_id,
             (SELECT MIN((r2.raw_time + r2.cones * 2) * r2.pax_index) FROM results r2
             WHERE r2.event_id = r.event_id) / ((r.raw_time + r.cones * 2) * r.pax_index) * 100 AS pax_points
             FROM results r
             JOIN drivers d ON d.id = r.driver_id
             JOIN events e ON e.ID = r.event_id
             WHERE e.season_id = :sid
             ),
             ranked AS (
                SELECT *, ROW_NUMBER() OVER (PARTITION BY driver_id ORDER BY pax_points DESC) AS rn
                FROM event_scores
             )
             SELECT driver_id, first_name, last_name, 
                SUM(pax_points) AS total_pax_points,
                COUNT(*) AS events_counted
             FROM ranked, season_events
             WHERE rn <= GREATEST(1, FLOOR(season_events.total / 2) - 1)
             GROUP BY driver_id, first_name, last_name
             ORDER BY  total_pax_points DESC

        """),
       {"sid": season_id}
    )
    rows = result.fetchall()
    return [dict(row._mapping) for row in rows]

@router.get("/standings/raw/{season_id}")
async def raw_standings(season_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("""
        WITH season_events AS (
             SELECT COUNT(DISTINCT id) AS total FROM events WHERE season_id = :sid
             ),
        event_scores AS (
             SELECT r.driver_id, d.first_name, d.last_name, r.event_id,
             (SELECT MIN(r2.raw_time + r2.cones * 2) FROM results r2
             WHERE r2.event_id = r.event_id) / (r.raw_time + r.cones * 2) * 100 AS raw_points
             FROM results r
             JOIN drivers d ON d.id = r.driver_id
             JOIN events e ON e.ID = r.event_id
             WHERE e.season_id = :sid
             ),
             ranked AS (
                SELECT *, ROW_NUMBER() OVER (PARTITION BY driver_id ORDER BY raw_points DESC) AS rn
                FROM event_scores
             )
             SELECT driver_id, first_name, last_name, 
                SUM(raw_points) AS total_raw_points,
                COUNT(*) AS events_counted
             FROM ranked, season_events
             WHERE rn <= GREATEST(1, FLOOR(season_events.total / 2) - 1)
             GROUP BY driver_id, first_name, last_name
             ORDER BY  total_raw_points DESC

        """),
       {"sid": season_id}
    )
    rows = result.fetchall()
    return [dict(row._mapping) for row in rows]

@router.get("/class/{season_id}/{class_name}")
async def class_standings(season_id: int, class_name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("""
        WITH season_events AS (
            SELECT COUNT(DISTINCT id) AS total FROM events WHERE season_id = :sid
        ),
        event_scores AS (
            SELECT r.driver_id, d.first_name, d.last_name, r.event_id,
                (SELECT MIN(r2.raw_time + r2.cones * 2) FROM results r2
                 WHERE r2.event_id = r.event_id AND r2.class = :cls)
                / (r.raw_time + r.cones * 2) * 100 AS class_points
            FROM results r
            JOIN drivers d ON d.id = r.driver_id
            JOIN events e ON e.id = r.event_id
            WHERE e.season_id = :sid AND r.class = :cls
        ),
        ranked AS (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY driver_id ORDER BY class_points DESC) AS rn
            FROM event_scores
        )
        SELECT driver_id, first_name, last_name,
            SUM(class_points) AS total_class_points,
            COUNT(*) AS events_counted
        FROM ranked, season_events
        WHERE rn <= GREATEST(1, FLOOR(season_events.total / 2) - 1)
        GROUP BY driver_id, first_name, last_name
        ORDER BY total_class_points DESC
        """),
        {"sid": season_id, "cls": class_name}
    )
    rows = result.fetchall()
    return [dict(row._mapping) for row in rows]


@router.get("/standings/cones/{season_id}")
async def kone_killer(season_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("""
        SELECT d.first_name, d.last_name,
               SUM(ru.cones) AS total_cones
        FROM runs ru
        JOIN results r ON r.id = ru.result_id
        JOIN drivers d ON d.id = r.driver_id
        JOIN events e ON e.id = r.event_id
        WHERE e.season_id = :sid
        GROUP BY d.first_name, d.last_name
        ORDER BY total_cones DESC
        """),
        {"sid": season_id}
    )
    rows = result.fetchall()
    return [dict(row._mapping) for row in rows]
