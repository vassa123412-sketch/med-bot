import os, sys, uuid, io, base64, json, hashlib, logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException, Cookie, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.templating import _TemplateResponse
from jinja2 import Environment, FileSystemLoader
from urllib.parse import urlencode

from core.config import settings
from core.llm_client import llm_client
from core.result_formatter import format_llm_result
from core.robokassa import robokassa

from landing.db import init_db, get_db, WebAnalysis, WebPayment

logging.basicConfig(level=settings.log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()

BASE_DIR = Path(__file__).parent
jinja_env = Environment(loader=FileSystemLoader(str(BASE_DIR / "templates")))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

def render(name: str, **kwargs) -> _TemplateResponse:
    template = jinja_env.get_template(name)
    html = template.render(**kwargs)
    return HTMLResponse(html)

UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

RUBLE_PRICES = {1: 50, 2: 99, 10: 199}
PACKAGE_LABELS = {1: "1 анализ", 2: "2 анализа", 10: "10 анализов"}

# --- Session helpers ---
def get_or_create_session(response: Response = None, request: Request = None):
    session_id = None
    if request:
        session_id = request.cookies.get("session_id")
    if not session_id:
        session_id = uuid.uuid4().hex[:32]
    if response:
        response.set_cookie(key="session_id", value=session_id, max_age=86400 * 30, httponly=True)
    return session_id

# --- Startup ---
@app.on_event("startup")
async def on_startup():
    init_db()
    logger.info("Landing DB initialized")

@app.get("/")
async def index():
    return render("index.html")

@app.get("/legal")
async def legal():
    return render("legal.html")

@app.get("/health")
async def health():
    return {"status": "ok"}

# --- Symptom Analysis (FREE) ---
SYMPTOM_PROMPT = """Пользователь описывает симптомы:

- Симптомы: {symptoms}
- Длительность: {duration}
- Температура: {temperature}
- Возраст: {age}
- Пол: {gender}

Проведите анализ симптомов.

ФОРМАТ ОТВЕТА:
1. 🔴 Красные флаги (если есть)
2. 📋 Возможные причины
3. 📊 Уровень срочности
4. 💡 Рекомендации"""

@app.get("/analyze/symptoms", response_class=HTMLResponse)
async def symptom_form():
    return render("symptoms.html")

@app.post("/analyze/symptoms")
async def analyze_symptoms(
    symptoms: str = Form(...),
    duration: str = Form(...),
    temperature: str = Form(...),
    age: str = Form(...),
    gender: str = Form(...),
):
    if len(symptoms.strip()) < 3:
        return render("symptoms.html", error="Опишите симптомы подробнее (минимум 3 символа)",
                       symptoms=symptoms, duration=duration, temperature=temperature, age=age, gender=gender)

    prompt = SYMPTOM_PROMPT.format(symptoms=symptoms, duration=duration, temperature=temperature, age=age, gender=gender)
    try:
        result = await llm_client.query(prompt)
        formatted = format_llm_result(result)
    except Exception as e:
        logger.error(f"Symptom analysis failed: {e}")
        return render("symptoms.html", error="Не удалось провести анализ. Попробуйте позже.")

    return render("result.html", result=formatted, analysis_type="symptoms", title="Анализ симптомов")

# --- Lab Analysis (PAID) ---
@app.get("/analyze/lab", response_class=HTMLResponse)
async def lab_upload_form():
    return render("lab_upload.html")

@app.post("/analyze/lab")
async def lab_upload(
    file: UploadFile = File(...),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        return render("lab_upload.html", error="Пожалуйста, загрузите изображение (JPG, PNG).")

    image_data = await file.read()
    if len(image_data) > 10 * 1024 * 1024:
        return render("lab_upload.html", error="Файл слишком большой. Максимум 10 МБ.")

    file_ext = file.filename.split(".")[-1] if file.filename else "jpg"
    filename = f"{uuid.uuid4().hex}.{file_ext}"
    filepath = UPLOAD_DIR / filename
    with open(filepath, "wb") as f:
        f.write(image_data)

    return render("lab_pricing.html", filename=filename)

@app.get("/analyze/lab/process/{filename}")
async def process_lab_analysis(
    filename: str,
    response: Response = None,
):
    """Process lab analysis (called after successful payment)."""
    filepath = UPLOAD_DIR / filename
    if not filepath.exists():
        return render("error.html", error="Файл не найден. Загрузите фото заново.")

    image_data = filepath.read_bytes()

    # OCR
    try:
        ocr_text = await llm_client.extract_text_from_image_openrouter(image_data)
        if not ocr_text.strip():
            ocr_text = await llm_client.extract_text_from_image(image_data)
        if not ocr_text.strip():
            raise ValueError("OCR failed to extract text")
    except Exception as e:
        logger.error(f"OCR failed: {e}")
        return render("error.html", error="Не удалось распознать текст на фото. Попробуйте с более чётким снимком.")

    # LLM analysis
    prompt = (
        "Пользователь прислал фото лабораторных анализов. Вот что распознано:\n\n"
        f"{ocr_text}\n\n"
        "Ты — медицинский ассистент. Это лабораторные результаты пациента.\n\n"
        "Проанализируй результаты в формате:\n"
        "1. Общее впечатление — какие показатели в норме, какие отклоняются\n"
        "2. Для КАЖДОГО отклонения — что это может означать\n"
        "3. Стоит ли обратиться к врачу и насколько срочно\n\n"
        "Тон — профессиональный, спокойный, информативный."
    )
    try:
        result = await llm_client.query(prompt)
        formatted = format_llm_result(result)
    except Exception as e:
        logger.error(f"Lab LLM analysis failed: {e}")
        return render("error.html", error="Не удалось проанализировать результаты. Попробуйте позже.")

    try:
        filepath.unlink()
    except:
        pass

    db = get_db()
    try:
        analysis = WebAnalysis(
            session_id="anon",
            analysis_type="lab",
            input_text=ocr_text[:3000],
            result=formatted,
            status="done",
            completed_at=datetime.now(),
        )
        db.add(analysis)
        db.commit()
    except Exception as e:
        logger.error(f"DB save failed: {e}")
    finally:
        db.close()

    return render("result.html", result=formatted, analysis_type="lab", title="Расшифровка анализов")

# --- Robokassa Payment Flow ---
@app.get("/pay/robokassa/{filename}/{package}")
async def pay_robokassa(
    filename: str,
    package: int,
    response: Response = None,
):
    amount = RUBLE_PRICES.get(package)
    if not amount:
        return render("error.html", error="Неверный пакет.")

    raw = f"{filename}_{package}"
    inv_id = abs(hash(raw)) % 1000000

    db = get_db()
    try:
        payment = WebPayment(
            session_id="anon",
            package_size=package,
            amount=amount,
            robokassa_inv_id=str(inv_id),
            status="pending",
        )
        db.add(payment)
        db.commit()
    except Exception as e:
        logger.error(f"Payment DB error: {e}")
    finally:
        db.close()

    if not robokassa.is_configured():
        return render("error.html", error="Оплата через Robokassa временно недоступна.")

    description = f"МедАссистент: {PACKAGE_LABELS.get(package, 'анализы')}"
    payment_url = robokassa.generate_payment_url(inv_id, amount, description)
    if robokassa.login.startswith("@"):
        payment_url += "&IsTest=1"

    if response:
        response.set_cookie(key="pending_filename", value=filename, max_age=3600, httponly=True)

    return RedirectResponse(url=payment_url)

@app.post("/robokassa/result")
async def robokassa_result(request: Request):
    """Robokassa Result URL — server-to-server notification."""
    form = await request.form()
    out_sum = form.get("OutSum", "")
    inv_id = form.get("InvId", "")
    signature = form.get("SignatureValue", "")
    logger.info(f"Robokassa result: InvId={inv_id}, OutSum={out_sum}")

    if not robokassa.verify_result_url(out_sum, inv_id, signature):
        logger.warning(f"Robokassa invalid signature for InvId={inv_id}")
        raise HTTPException(400, "Invalid signature")

    # Mark payment as paid
    db = get_db()
    try:
        payment = db.query(WebPayment).filter(WebPayment.robokassa_inv_id == int(inv_id)).first()
        if payment and payment.status == "pending":
            payment.status = "paid"
            payment.paid_at = datetime.now()
            db.commit()
            logger.info(f"Payment confirmed: InvId={inv_id}")
    except Exception as e:
        logger.error(f"Payment confirm error: {e}")
    finally:
        db.close()

    return HTMLResponse("OK")

@app.get("/robokassa/success")
async def robokassa_success(filename: str = Cookie(default="")):
    return render("payment_success.html", filename=filename)

@app.get("/robokassa/fail")
async def robokassa_fail():
    return render("payment_fail.html")

@app.get("/pricing")
async def pricing():
    return render("pricing.html")
