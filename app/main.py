from fastapi import FastAPI
from app.core.lifespan import lifespan
from app.router import auth

app = FastAPI()

app = FastAPI(
    title="SHL Solver API",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(auth.router)
