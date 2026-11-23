from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from strawberry.fastapi import GraphQLRouter

from app.database import Base, engine, SessionLocal
from app.schema import schema
from app.rbac import seed_rbac
from app.security import jwt_secret


@asynccontextmanager
async def lifespan(app: FastAPI):
    jwt_secret()
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_rbac(db)
    yield


app = FastAPI(title="Sistema General de Ingresos - Dashboard financiero", lifespan=lifespan)
app.include_router(GraphQLRouter(schema, graphql_ide="graphiql"), prefix="/graphql")


@app.get("/")
def root():
    return RedirectResponse("/dashboard/")


@app.get("/health")
def health():
    return {"status": "ok"}


app.mount("/dashboard", StaticFiles(directory=Path(__file__).resolve().parents[2] / "dashboard", html=True), name="dashboard")
