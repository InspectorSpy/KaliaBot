import sqlite3
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

DB_PATH = "/app/data/user_count.db"
app = FastAPI()

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

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