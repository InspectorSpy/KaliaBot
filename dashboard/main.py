import os
import sqlite3
from datetime import datetime
from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

DB_PATH = "/app/data/user_count.db"

SECRET_KEY = os.getenv("SECRET_KEY", "33ae5a568a3f7f8752dddfe942d4e45cd04c6653430c3ea5ff2ff150c9739306")
DASHBOARD_USERNAME = os.getenv("DASHBOARD_USERNAME", "admin")
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "H41st4P4sk4!")

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def require_auth(request: Request):
    if not request.session.get("authenticated"):
        raise RedirectResponse("/login")

class RedirectException(Exception):
    def __init__(self, url: str):
        self.url = url

@app.exception_handler(RedirectException)
async def redirect_exception_handler(request: Request, exc: RedirectException):
    return RedirectResponse(exc.url)

@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={}
    )


@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == DASHBOARD_USERNAME and password == DASHBOARD_PASSWORD:
        request.session["authenticated"] = True
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": "Invalid username or password"}
    )

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login")

@app.get("/")
async def index(request: Request):
    db = get_db()

    # All-time leaderboard
    leaderboard = db.execute(
        """
        SELECT full_name, username, count, pyha_count, holiton_count,
            count + pyha_count + holiton_count as total
        FROM user_counts
        ORDER BY total DESC
    """).fetchall()

    # Group totals
    totals = db.execute(
        """
        SELECT SUM(count) as kalia, SUM(pyha_count) as pyha, SUM(holiton_count) as holiton
        FROM user_counts
    """).fetchone()

    chart_data = db.execute(
        """
        SELECT year_month,
               SUM(count) as kalia,
               SUM(pyha_count) as pyha,
               SUM(holiton_count) as holiton
        FROM monthly_counts
        GROUP BY year_month
        ORDER BY year_month ASC
    """).fetchall()

    db.close()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "leaderboard": leaderboard,
            "totals": totals,
            "chart_data": [dict(row) for row in chart_data],
        }
    )

@app.get("/monthly")
async def monthly(request: Request):
    db = get_db()

    months = db.execute("""
        SELECT year_month,
            SUM(count) as kalia,
            SUM(pyha_count) as pyha,
            SUM(holiton_count) as holiton,
            SUM(count + pyha_count + holiton_count) as total
        FROM monthly_counts
        GROUP BY year_month
        ORDER BY year_month DESC
    """).fetchall()

    db.close()
    return templates.TemplateResponse(
        request=request,
        name="monthly.html",
        context={"months": months}
    )