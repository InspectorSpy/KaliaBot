import os
import sqlite3
import docker
import asyncio
from datetime import datetime
from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from concurrent.futures import ThreadPoolExecutor

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
    return RedirectResponse(url="/login", status_code=302)

@app.get("/")
async def index(request: Request):
    if not request.session.get("authenticated"):
        return RedirectResponse(url="/login", status_code=302)
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
    if not request.session.get("authenticated"):
        return RedirectResponse(url="/login", status_code=302)

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

async def get_container_info(name: str, docker_client) -> dict:
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as pool:
        return await loop.run_in_executor(pool, _fetch_container_info, name, docker_client)
    
def _fetch_container_info(name: str, docker_client) -> dict:
    try:
        c = docker_client.containers.get(name)
        stats = c.stats(stream=False)

        # CPU %
        cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - stats["precpu_stats"]["cpu_usage"]["total_usage"]
        system_delta = stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"]["system_cpu_usage"]
        cpu_percent = round((cpu_delta / system_delta) * len(stats["cpu_stats"]["cpu_usage"].get("percpu_usage", [1])) * 100, 2)
    
        # Memory %
        mem_usage = stats["memory_stats"]["usage"] // (1024 * 1024)
        mem_limit = stats["memory_stats"]["limit"] // (1024 * 1024)
        
        # Logs
        logs = c.logs(tail=20).decode("utf-8", errors="replace")

        return {
            "status": c.status,
            "started_at": c.attrs["State"]["StartedAt"][:19].replace("T", " "),
            "cpu": cpu_percent,
            "mem_usage": mem_usage,
            "mem_limit": mem_limit,
            "logs": logs,
        }
    except docker.errors.NotFound:
        return None

@app.get("/system")
async def system(request: Request):
    if not request.session.get("authenticated"):
        return RedirectResponse(url="/login", status_code=302)

    docker_client = docker.from_env()
    names = ["kaliabot-server-1", "kaliabot-dashboard-1"]

    containers = {}
    for name in names:
        try:
            c = docker_client.containers.get(name)
            containers[name] = {"status": c.status}
        except docker.errors.NotFound:
            containers[name] = None

    return templates.TemplateResponse(
        request=request,
        name="system.html",
        context={"containers": containers}
    )

@app.get("/api/container-stats")
async def container_stats(request: Request):
    if not request.session.get("authenticated"):
        return RedirectResponse(url="/login", status_code=302)

    docker_client = docker.from_env()
    names = ["kaliabot-server-1", "kaliabot-dashboard-1"]
    results = await asyncio.gather(*[get_container_info(name, docker_client) for name in names])
    containers = dict(zip(names, results))

    return containers

@app.post("/system/restart/{container_name}")
async def restart_container(request: Request, container_name: str):
    if not request.session.get("authenticated"):
        return RedirectResponse(url="/login", status_code=302)

    docker_client = docker.from_env()
    try:
        c = docker_client.containers.get(container_name)
        c.restart()
    except docker.errors.NotFound:
        pass
    return RedirectResponse(url="/system", status_code=302)

@app.get("/admin")
async def admin(request: Request):
    if not request.session.get("authenticated"):
        return RedirectResponse(url="/login", status_code=302)
    
    db = get_db()
    users = db.execute(
        """
        SELECT chat_id, user_id, full_name, username, count, pyha_count, holiton_count
        FROM user_counts
        ORDER BY count + pyha_count + holiton_count DESC
    """).fetchall()

    photos = db.execute(
        """
        SELECT p.file_unique_id, p.user_id, p.used_at, u.full_name, u.username
        FROM used_photos p
        LEFT JOIN user_counts u ON p.chat_id = u.chat_id AND p.user_id = u.user_id
        ORDER BY p.used_at DESC
    """).fetchall()

    monthly = db.execute(
        """
        SELECT year_month
        FROM monthly_counts
        ORDER BY year_month DESC
    """).fetchall()

    db.close()
    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "users": users,
            "photos": photos,
            "monthly": monthly,
        }
    )

# Update user scores
@app.post("/admin/user/update")

# Delete user
@app.post("/admin/user/delete")

# Delete monthly data
@app.post("/admin/monthly/delete")

# Delete used photo
@app.post("/admin/photo/delete")
