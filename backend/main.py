
from fastapi import FastAPI

app = FastAPI(title="Zote Jam Room API")


@app.get("/")
def home():
    return {
        "message": "Welcome to Zote Jam Room API!",
        "status": "running"
    }
