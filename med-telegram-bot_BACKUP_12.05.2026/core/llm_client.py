import asyncio
import logging
import os
import base64
from groq import AsyncGroq
import google.generativeai as genai
import httpx
import aiohttp
from core.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Ты — медицинский информационный ассистент «МедАссистент». Ты НЕ врач и НЕ ставишь диагнозы.

ЗАДАЧА:
1. Анализировать симптомы, предоставленные пользователем
2. Предоставлять ИНФОРМАЦИЮ о возможных причинах
3. Указывать уровень срочности
4. Рекомендовать обращение к врачу

ОГРАНИЧЕНИЯ:
- НИКОГДА не ставь диагноз
- НИКОГДА не назначай лечение или дозировки
- ВСЕГДА указывай, что это НЕ замена врачу
- ВСЕГДА включай дисклеймер в конце
- При опасных симптомах — НЕМЕДЛЕННО рекомендуй скорую помощь

⛔ ВАЖНО: ОТВЕЧАЙ СТРОГО НА РУССКОМ ЯЗЫКЕ. НИ ОДНОГО АНГЛИЙСКОГО СЛОВА.
Запрещено использовать: "meantime", "OK", "red flags", "urgent" и любые другие английские слова или фразы.
Даже медицинские термины пиши на русском: "ангина", а не "tonsillitis".
Если не знаешь русского слова — опиши его русскими словами.

ФОРМАТ ОТВЕТА (строго на русском):
1. 🔴 Красные флаги (если есть) — В НАЧАЛЕ
2. 📋 Возможные причины (с вероятностью)
3. 📊 Уровень срочности
4. 💡 Рекомендации
5. ⚠️ Дисклеймер: «Это не медицинский диагноз. Обратитесь к врачу для точной диагностики и лечения.»
"""


class LLMClient:
    def __init__(self):
        self.proxy = settings.proxy_url or None
        
        # Groq client with proxy
        if settings.groq_api_key:
            http_client = httpx.AsyncClient(proxy=self.proxy) if self.proxy else None
            self.groq_client = AsyncGroq(
                api_key=settings.groq_api_key,
                http_client=http_client
            ) if settings.groq_api_key else None
        else:
            self.groq_client = None

        # Gemini client with proxy
        self.gemini_model = None
        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)
            self.gemini_model = genai.GenerativeModel(settings.gemini_model)
            if self.proxy:
                os.environ['HTTP_PROXY'] = self.proxy
                os.environ['HTTPS_PROXY'] = self.proxy

    async def query_groq(self, prompt: str) -> str:
        if not self.groq_client:
            raise ValueError("Groq API key not configured")
        response = await self.groq_client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=1500,
        )
        return response.choices[0].message.content

    async def query_gemini(self, prompt: str) -> str:
        if not self.gemini_model:
            raise ValueError("Gemini API key not configured")
        response = await self.gemini_model.generate_content_async(
            f"{SYSTEM_PROMPT}\n\nUser query: {prompt}"
        )
        return response.text

    async def query_openrouter(self, prompt: str) -> str:
        if not settings.openrouter_api_key:
            raise ValueError("OpenRouter API key not configured")
        
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://medassistant.bot",
            "X-Title": "MedAssistant"
        }
        payload = {
            "model": settings.openrouter_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    text = await response.text()
                    raise Exception(f"OpenRouter API error: {response.status} - {text}")
                data = await response.json()
                return data['choices'][0]['message']['content']

    async def query_with_image(self, prompt: str, image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
        """Analyze image with Gemini vision using base64 inline data"""
        if not self.gemini_model:
            raise ValueError("Gemini API key not configured")
        
        b64_data = base64.b64encode(image_bytes).decode('utf-8')
        
        image_part = {
            "inline_data": {
                "mime_type": mime_type,
                "data": b64_data
            }
        }
        
        response = await self.gemini_model.generate_content_async(
            [f"{SYSTEM_PROMPT}\n\nЭто медицинское изображение. {prompt}", image_part]
        )
        return response.text

    async def extract_text_from_image(self, image_bytes: bytes) -> str:
        """Extract text from image using OCR (Lazy load reader for performance)"""
        import io
        import easyocr
        from PIL import Image
        
        try:
            image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        except Exception as e:
            raise ValueError(f"Cannot open image: {e}")
        
        # Lazy load: create reader only if it doesn't exist
        if not hasattr(self, '_ocr_reader'):
            logger.info("Initializing OCR model (this takes ~10s on first run)...")
            self._ocr_reader = easyocr.Reader(['ru', 'en'], gpu=False, verbose=False)
        
        results = self._ocr_reader.readtext(image_bytes)
        extracted_text = ' '.join([r[1] for r in results])
        
        if not extracted_text.strip():
            return ""
        
        return extracted_text

    async def extract_text_from_image_openrouter(self, image_bytes: bytes) -> str:
        """Extract text from image using OpenRouter vision model (good for handwriting)."""
        import base64
        b64 = base64.b64encode(image_bytes).decode('utf-8')

        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://medassistant.bot",
            "X-Title": "MedAssistant"
        }
        payload = {
            "model": "qwen/qwen-2.5-vl-72b-instruct",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Распознай и верни ТОЛЬКО текст, который ты видишь на этом изображении. "
                                "Это может быть рукописный текст или печатный. "
                                "Если текст нечитаем — верни пустую строку. "
                                "Не добавляй своих комментариев, только распознанный текст."
                            )
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{b64}"
                            }
                        }
                    ]
                }
            ]
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    text = await response.text()
                    raise Exception(f"OpenRouter vision error: {response.status} - {text}")
                data = await response.json()
                return data['choices'][0]['message']['content'].strip()

    async def query(self, prompt: str) -> str:
        providers = [
            ("Groq", self.query_groq),
            ("Gemini", self.query_gemini),
            ("OpenRouter", self.query_openrouter),
        ]
        for name, func in providers:
            try:
                logger.info(f"Trying {name}...")
                result = await asyncio.wait_for(func(prompt), timeout=45)
                logger.info(f"{name} responded successfully")
                return result
            except Exception as e:
                logger.warning(f"{name} failed: {e}")
                continue
        raise RuntimeError("All LLM providers failed")


llm_client = LLMClient()
