from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Autocross API is running"}
