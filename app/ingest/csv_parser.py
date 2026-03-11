import csv
from decimal import Decimal
import io
from sqlalchemy import text

async def parse_csv(file_bytes: bytes, event_id: int, db)->dict:
    content = file_bytes.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    next(reader)

    for row in reader:
        if len(row) <8:
            continue

        first_name  = row[0].strip()
        last_name   = row[1].strip()
        car_class   = row[2].strip()
        car_number  = row[3].strip()
        member_num  = row[4].strip()
        region      = row[5].strip()
        sponsor     = row[6].strip()

        run_data = row[7:]
        runs = []
        for i in range(0,len(run_data)-2, 3):
            time_str = run_data[i].strip()
            cones = run_data[i+1].strip()
            status = run_data[i+2].strip()

            if not time_str:
                continue

            runs.append({
                "time": Decimal(time_str),
                "cones": int(cones) if cones else 0,
                "dnf": status == "DNF",
                "rerun": status == "RRN",
            })

        valid_runs = [r for r in runs if not r["dnf"] and not r["rerun"]]
        if not valid_runs:
            continue  # driver has no clean runs, skip

        best_run = min(valid_runs, key=lambda r: r["time"] + r["cones"] * 2)
        best_time = best_run["time"]
        best_cones = best_run["cones"]

        if member_num:
            result = await db.execute(
                text("SELECT id FROM drivers WHERE member_number = :mn"),
                {"mn": member_num}
            )
        else:
            result = await db.execute(
                text("SELECT id FROM drivers WHERE first_name = :fn AND last_name = :ln"),
                {"fn": first_name, "ln": last_name}
            )

        driver_row = result.fetchone()

        if driver_row:
            driver_id = driver_row[0]
        else:
            await db.execute(
                text("""
                    INSERT INTO drivers (first_name, last_name, member_number, region)
                    VALUES (:fn, :ln, :mn, :rg)
                """),
                {"fn": first_name, "ln": last_name, "mn": member_num or None, "rg": region}
            )
            result = await db.execute(text("SELECT LAST_INSERT_ID()"))
            driver_id = result.scalar()

        # Look up PAX index for this class
        pax_result = await db.execute(
            text("SELECT idx FROM pax_indices WHERE class = :cls"),
            {"cls": car_class}
        )
        pax_row = pax_result.fetchone()
        pax_index = pax_row[0] if pax_row else Decimal("1.000")
        pax_time = best_time * pax_index

        # Insert result
        await db.execute(
            text("""
                INSERT INTO results
                    (event_id, driver_id, class, car_number, raw_time, pax_index, pax_time, cones)
                VALUES
                    (:eid, :did, :cls, :cnum, :rt, :pi, :pt, :cones)
            """),
            {
                "eid": event_id, "did": driver_id, "cls": car_class,
                "cnum": int(car_number) if car_number else None,
                "rt": best_time, "pi": pax_index, "pt": pax_time,
                "cones": best_cones,
            }
        )
        result_id_row = await db.execute(text("SELECT LAST_INSERT_ID()"))
        result_id = result_id_row.scalar()

        # Insert individual runs
        for idx, run in enumerate(runs, start=1):
            await db.execute(
                text("""
                    INSERT INTO runs (result_id, run_num, raw_time, cones, dnf, rerun)
                    VALUES (:rid, :rnum, :rt, :cones, :dnf, :rerun)
                """),
                {
                    "rid": result_id, "rnum": idx,
                    "rt": None if run["dnf"] else run["time"],
                    "cones": run["cones"], "dnf": run["dnf"], "rerun": run["rerun"],
                }
            )

    await db.commit()
    return {"status": "ok"}

