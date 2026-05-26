import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader

app = FastAPI()

BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

def render(template_name: str, **kwargs) -> HTMLResponse:
    template = env.get_template(template_name)
    return HTMLResponse(template.render(**kwargs))

@app.get("/")
async def index(request: Request):
    return render("index.html")

@app.get("/legal")
async def legal(request: Request):
    return render("legal.html")

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
