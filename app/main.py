from fastapi import FastAPI
from pydantic import BaseModel

from app.core.lifespan import lifespan

app = FastAPI()


app = FastAPI(
    title="SHL Solver API",
    version="0.1.0",
    lifespan=lifespan,
)
