from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_db
from app.reports.season_pdf import build_season_pdf

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/season/{season_id}")
async def season_report(season_id: int, db: AsyncSession = Depends(get_db)):
    season_row = await db.execute(
        text("SELECT year FROM seasons WHERE id = :sid"),
        {"sid": season_id}
    )
    season = season_row.fetchone()

    events_row = await db.execute(
        text("SELECT event_num FROM events WHERE season_id = :sid ORDER BY event_num"),
        {"sid": season_id}
    )
    events_completed = [r[0] for r in events_row.fetchall()]

    pax = await db.execute(text("""
        WITH season_events AS (
            SELECT COUNT(DISTINCT e.id) AS total,
                   COALESCE(s.max_counting_events, COUNT(DISTINCT e.id)) AS counting
            FROM events e JOIN seasons s ON s.id = e.season_id WHERE e.season_id = :sid
        ),
        event_scores AS (
            SELECT d.first_name, d.last_name, r.event_id,
                (SELECT MIN((r2.raw_time + r2.cones*2) * r2.pax_index) FROM results r2
                 WHERE r2.event_id = r.event_id)
                / ((r.raw_time + r.cones*2) * r.pax_index) * 100 AS pax_points
            FROM results r
            JOIN drivers d ON d.id = r.driver_id
            JOIN events e ON e.id = r.event_id
            WHERE e.season_id = :sid AND CONCAT(d.first_name, ' ', d.last_name) != 'Common Car'
        ),
        ranked AS (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY first_name, last_name ORDER BY pax_points DESC) AS rn
            FROM event_scores
        )
        SELECT first_name, last_name,
               SUM(pax_points) AS total_pax_points,
               COUNT(*) AS events_counted
        FROM ranked, season_events WHERE rn <= season_events.counting
        GROUP BY first_name, last_name ORDER BY total_pax_points DESC
    """), {"sid": season_id})
    pax_rows = [dict(r._mapping) for r in pax.fetchall()]

    raw = await db.execute(text("""
        WITH season_events AS (
            SELECT COUNT(DISTINCT e.id) AS total,
                   COALESCE(s.max_counting_events, COUNT(DISTINCT e.id)) AS counting
            FROM events e JOIN seasons s ON s.id = e.season_id WHERE e.season_id = :sid
        ),
        event_scores AS (
            SELECT d.first_name, d.last_name, r.event_id,
                (SELECT MIN(r2.raw_time + r2.cones*2) FROM results r2
                 WHERE r2.event_id = r.event_id)
                / (r.raw_time + r.cones*2) * 100 AS raw_points
            FROM results r
            JOIN drivers d ON d.id = r.driver_id
            JOIN events e ON e.id = r.event_id
            WHERE e.season_id = :sid AND CONCAT(d.first_name, ' ', d.last_name) != 'Common Car'
        ),
        ranked AS (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY first_name, last_name ORDER BY raw_points DESC) AS rn
            FROM event_scores
        )
        SELECT first_name, last_name,
               SUM(raw_points) AS total_raw_points,
               COUNT(*) AS events_counted
        FROM ranked, season_events WHERE rn <= season_events.counting
        GROUP BY first_name, last_name ORDER BY total_raw_points DESC
    """), {"sid": season_id})
    raw_rows = [dict(r._mapping) for r in raw.fetchall()]

    class_res = await db.execute(text("""
        WITH season_events AS (
            SELECT COUNT(DISTINCT e.id) AS total,
                   COALESCE(s.max_counting_events, COUNT(DISTINCT e.id)) AS counting
            FROM events e JOIN seasons s ON s.id = e.season_id WHERE e.season_id = :sid
        ),
        class_rankings AS (
            SELECT d.first_name, d.last_name, r.class, r.event_id,
                RANK() OVER (PARTITION BY r.event_id, r.class
                             ORDER BY r.raw_time + r.cones*2) AS class_pos
            FROM results r
            JOIN drivers d ON d.id = r.driver_id
            JOIN events e ON e.id = r.event_id WHERE e.season_id = :sid
        ),
        event_points AS (
            SELECT first_name, last_name, class, event_id,
                CASE class_pos
                    WHEN 1 THEN 20 WHEN 2 THEN 17 WHEN 3 THEN 14
                    WHEN 4 THEN 11 WHEN 5 THEN 8  WHEN 6 THEN 6
                    WHEN 7 THEN 4  WHEN 8 THEN 2  WHEN 9 THEN 1
                    ELSE 0
                END AS event_points
            FROM class_rankings
        ),
        ranked AS (
            SELECT *,
                ROW_NUMBER() OVER (PARTITION BY first_name, last_name, class
                                   ORDER BY event_points DESC) AS rn
            FROM event_points
        )
        SELECT first_name, last_name, class,
               SUM(event_points) AS total_points,
               COUNT(*) AS events_counted
        FROM ranked, season_events WHERE rn <= season_events.counting
        GROUP BY first_name, last_name, class
        ORDER BY class, total_points DESC
    """), {"sid": season_id})
    class_rows = [dict(r._mapping) for r in class_res.fetchall()]

    part_res = await db.execute(text("""
        SELECT d.first_name, d.last_name, COUNT(DISTINCT r.event_id) AS events_attended
        FROM results r
        JOIN drivers d ON d.id = r.driver_id
        JOIN events e ON e.id = r.event_id
        WHERE e.season_id = :sid
        GROUP BY d.first_name, d.last_name
        ORDER BY d.last_name, d.first_name
    """), {"sid": season_id})
    participants = [dict(r._mapping) for r in part_res.fetchall()]

    pdf_bytes = build_season_pdf(
        season_year=season.year if season else season_id,
        events_completed=events_completed,
        pax_rows=pax_rows,
        raw_rows=raw_rows,
        class_rows=class_rows,
        participants=participants,
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=season_{season_id}_report.pdf"},
    )
