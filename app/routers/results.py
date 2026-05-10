from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_db

router = APIRouter(prefix="/results", tags=["results"])


@router.get("/dashboard/{season_id}")
async def dashboard(season_id: int, db: AsyncSession = Depends(get_db)):
    stats = await db.execute(
        text("""
        SELECT
            (SELECT COUNT(DISTINCT CONCAT(d.first_name, d.last_name))
             FROM results r
             JOIN drivers d ON d.id = r.driver_id
             JOIN events e ON e.id = r.event_id
             WHERE e.season_id = :sid) AS unique_drivers,

            (SELECT COUNT(DISTINCT r.driver_id)
             FROM results r
             WHERE r.event_id = (
                 SELECT id FROM events WHERE season_id = :sid ORDER BY event_date DESC LIMIT 1
             )) AS last_event_drivers,

            (SELECT ROUND(AVG(event_counts.cnt), 1)
             FROM (
                 SELECT COUNT(*) AS cnt
                 FROM results r
                 JOIN events e ON e.id = r.event_id
                 WHERE e.season_id = :sid
                 GROUP BY r.event_id
             ) AS event_counts) AS avg_drivers_per_event,

            (SELECT e.event_num FROM events e
             WHERE e.season_id = :sid
             ORDER BY e.event_date DESC LIMIT 1) AS last_event_num,

            (SELECT COUNT(*) FROM events WHERE season_id = :sid) AS total_events,

            (SELECT COUNT(DISTINCT CONCAT(d.first_name, d.last_name))
             FROM results r
             JOIN drivers d ON d.id = r.driver_id
             WHERE r.event_id = (
                 SELECT id FROM events WHERE season_id = :sid ORDER BY event_date DESC LIMIT 1
             )
             AND CONCAT(d.first_name, d.last_name) NOT IN (
                 SELECT DISTINCT CONCAT(d2.first_name, d2.last_name)
                 FROM results r2
                 JOIN drivers d2 ON d2.id = r2.driver_id
                 JOIN events e2 ON e2.id = r2.event_id
                 WHERE e2.season_id = :sid
                 AND e2.id != (
                     SELECT id FROM events WHERE season_id = :sid ORDER BY event_date DESC LIMIT 1
                 )
             )) AS new_drivers_last_event
        """),
        {"sid": season_id}
    )
    row = stats.fetchone()

    cones = await db.execute(
        text("""
        SELECT d.first_name, d.last_name, SUM(ru.cones) AS total_cones
        FROM runs ru
        JOIN results r ON r.id = ru.result_id
        JOIN drivers d ON d.id = r.driver_id
        JOIN events e ON e.id = r.event_id
        WHERE e.season_id = :sid
        GROUP BY d.first_name, d.last_name
        ORDER BY total_cones DESC
        LIMIT 5
        """),
        {"sid": season_id}
    )
    cone_rows = cones.fetchall()

    return {
        **dict(row._mapping),
        "cone_leaders": [dict(r._mapping) for r in cone_rows]
    }


@router.get("/dashboard/{season_id}/drivers-per-event")
async def drivers_per_event(season_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("""
        SELECT e.event_num, e.event_date, COUNT(DISTINCT r.driver_id) AS driver_count
        FROM events e
        LEFT JOIN results r ON r.event_id = e.id
        WHERE e.season_id = :sid
        GROUP BY e.id, e.event_num, e.event_date
        ORDER BY e.event_date
        """),
        {"sid": season_id}
    )
    return [dict(r._mapping) for r in result.fetchall()]


@router.get("/dashboard/{season_id}/cone-race")
async def cone_race(season_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("""
        SELECT e.event_num, d.first_name, d.last_name, SUM(ru.cones) AS event_cones
        FROM runs ru
        JOIN results r ON r.id = ru.result_id
        JOIN drivers d ON d.id = r.driver_id
        JOIN events e ON e.id = r.event_id
        WHERE e.season_id = :sid
        GROUP BY e.id, e.event_num, d.first_name, d.last_name
        ORDER BY e.event_num
        """),
        {"sid": season_id}
    )
    rows = [dict(r._mapping) for r in result.fetchall()]

    # Find top 5 drivers by total cones
    totals = {}
    for row in rows:
        name = f"{row['first_name']} {row['last_name']}"
        totals[name] = totals.get(name, 0) + row['event_cones']
    top5 = sorted(totals, key=lambda n: totals[n], reverse=True)[:5]

    # Build cumulative series per driver
    events = sorted(set(r['event_num'] for r in rows))
    series = {name: [] for name in top5}
    for name in top5:
        cumulative = 0
        for event_num in events:
            match = next((r for r in rows
                          if f"{r['first_name']} {r['last_name']}" == name
                          and r['event_num'] == event_num), None)
            cumulative += match['event_cones'] if match else 0
            series[name].append(cumulative)

    return {"events": events, "series": series}


@router.get("/event/{event_id}")
async def event_results(event_id: int, sort: str = "pax", db: AsyncSession = Depends(get_db)):
    order = "r.raw_time + (r.cones * 2)" if sort == "raw" else "r.pax_time"
    result = await db.execute(
        text(f"""
        SELECT d.first_name, d.last_name, r.class, r.car_number,
             r.raw_time, r.cones, r.raw_time + (r.cones*2) AS total_time,
             r.pax_index, r.pax_time
        FROM results r
        JOIN drivers d on d.id = r.driver_id
        WHERE r.event_id = :eid
        ORDER BY {order}
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
             SELECT COUNT(DISTINCT e.id) AS total,
                    COALESCE(s.max_counting_events, COUNT(DISTINCT e.id)) AS counting
             FROM events e
             JOIN seasons s ON s.id = e.season_id
             WHERE e.season_id = :sid
             ),
        event_scores AS (
             SELECT r.driver_id, d.first_name, d.last_name, r.event_id,
             (SELECT MIN((r2.raw_time + r2.cones * 2) * r2.pax_index) FROM results r2
             WHERE r2.event_id = r.event_id) / ((r.raw_time + r.cones * 2) * r.pax_index) * 100 AS pax_points
             FROM results r
             JOIN drivers d ON d.id = r.driver_id
             JOIN events e ON e.ID = r.event_id
             WHERE e.season_id = :sid
               AND CONCAT(d.first_name, ' ', d.last_name) != 'Common Car'
             ),
             ranked AS (
                SELECT *, ROW_NUMBER() OVER (PARTITION BY first_name, last_name ORDER BY pax_points DESC) AS rn
                FROM event_scores
             )
             SELECT first_name, last_name,
                SUM(pax_points) AS total_pax_points,
                COUNT(*) AS events_counted
             FROM ranked, season_events
             WHERE rn <= season_events.counting
             GROUP BY first_name, last_name
             ORDER BY total_pax_points DESC

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
             SELECT COUNT(DISTINCT e.id) AS total,
                    COALESCE(s.max_counting_events, COUNT(DISTINCT e.id)) AS counting
             FROM events e
             JOIN seasons s ON s.id = e.season_id
             WHERE e.season_id = :sid
             ),
        event_scores AS (
             SELECT r.driver_id, d.first_name, d.last_name, r.event_id,
             (SELECT MIN(r2.raw_time + r2.cones * 2) FROM results r2
             WHERE r2.event_id = r.event_id) / (r.raw_time + r.cones * 2) * 100 AS raw_points
             FROM results r
             JOIN drivers d ON d.id = r.driver_id
             JOIN events e ON e.ID = r.event_id
             WHERE e.season_id = :sid
               AND CONCAT(d.first_name, ' ', d.last_name) != 'Common Car'
             ),
             ranked AS (
                SELECT *, ROW_NUMBER() OVER (PARTITION BY first_name, last_name ORDER BY raw_points DESC) AS rn
                FROM event_scores
             )
             SELECT first_name, last_name,
                SUM(raw_points) AS total_raw_points,
                COUNT(*) AS events_counted
             FROM ranked, season_events
             WHERE rn <= season_events.counting
             GROUP BY first_name, last_name
             ORDER BY total_raw_points DESC

        """),
       {"sid": season_id}
    )
    rows = result.fetchall()
    return [dict(row._mapping) for row in rows]

@router.get("/event/{event_id}/class/{class_name}")
async def event_class_results(event_id: int, class_name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("""
        SELECT d.first_name, d.last_name, r.car_number,
               r.raw_time, r.cones, r.raw_time + (r.cones * 2) AS total_time,
               ROW_NUMBER() OVER (ORDER BY r.raw_time + (r.cones * 2)) AS class_pos
        FROM results r
        JOIN drivers d ON d.id = r.driver_id
        WHERE r.event_id = :eid AND r.class = :cls
        ORDER BY total_time
        """),
        {"eid": event_id, "cls": class_name}
    )
    rows = result.fetchall()
    return [dict(row._mapping) for row in rows]

@router.get("/class/{season_id}/{class_name}")
async def class_standings(season_id: int, class_name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("""
        WITH season_events AS (
            SELECT COUNT(DISTINCT e.id) AS total,
                   COALESCE(s.max_counting_events, COUNT(DISTINCT e.id)) AS counting
            FROM events e
            JOIN seasons s ON s.id = e.season_id
            WHERE e.season_id = :sid
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
            SELECT *, ROW_NUMBER() OVER (PARTITION BY first_name, last_name ORDER BY class_points DESC) AS rn
            FROM event_scores
        )
        SELECT first_name, last_name,
            SUM(class_points) AS total_class_points,
            COUNT(*) AS events_counted
        FROM ranked, season_events
        WHERE rn <= season_events.counting
        GROUP BY first_name, last_name
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
