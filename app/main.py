from fastapi import FastAPI
from app.routers import ingest, events

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Autocross API is running"}

app.include_router(ingest.router)
app.include_router(events.router)