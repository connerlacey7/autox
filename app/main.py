from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.routers import ingest, events, results, drivers

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def index():
    return FileResponse("static/index.html")

app.include_router(ingest.router)
app.include_router(events.router)
app.include_router(results.router)
app.include_router(drivers.router)
