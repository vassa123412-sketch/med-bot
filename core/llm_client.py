import asyncio
import logging
import os
import base64
import google.generativeai as genai
import aiohttp
from core.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Ты — медицинский информационный ассистент «МедАссистент». Ты НЕ врач и НЕ ставишь диагнозы.

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
"""


class LLMClient:
    def __init__(self):
        self.proxy = settings.proxy_url or None

        # Gemini client with proxy
        self.gemini_model = None
        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)
            self.gemini_model = genai.GenerativeModel(settings.gemini_model)
            if self.proxy:
                os.environ['HTTP_PROXY'] = self.proxy
                os.environ['HTTPS_PROXY'] = self.proxy

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

    async def query_opencode_zen(self, prompt: str) -> str:
        """Query OpenCode Zen API (free Big Pickle model)"""
        if not settings.opencode_zen_api_key:
            raise ValueError("OpenCode Zen API key not configured")

        url = f"{settings.opencode_zen_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.opencode_zen_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.opencode_zen_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    text = await response.text()
                    raise Exception(f"OpenCode Zen API error: {response.status} - {text}")
                data = await response.json()
                return data['choices'][0]['message']['content']

    async def query_with_image(self, prompt: str, image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
        """Analyze image with Gemini vision. Falls back to OpenRouter Qwen Vision."""
        if self.gemini_model:
            try:
                b64_data = base64.b64encode(image_bytes).decode('utf-8')
                image_part = {"inline_data": {"mime_type": mime_type, "data": b64_data}}
                response = await self.gemini_model.generate_content_async(
                    [f"{SYSTEM_PROMPT}\n\nЭто медицинское изображение. {prompt}", image_part]
                )
                return response.text
            except Exception as e:
                logger.warning(f"Gemini vision failed: {e}")
        
        # Fallback: OpenRouter Qwen Vision
        if settings.openrouter_api_key:
            try:
                b64 = base64.b64encode(image_bytes).decode('utf-8')
                url = "https://openrouter.ai/api/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": "qwen/qwen-2.5-vl-72b-instruct",
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": f"{SYSTEM_PROMPT}\n\nЭто медицинское изображение. {prompt}"},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                            ]
                        }
                    ]
                }
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, headers=headers, json=payload) as response:
                        if response.status == 200:
                            data = await response.json()
                            return data['choices'][0]['message']['content']
                        text = await response.text()
                        raise Exception(f"OpenRouter vision error: {response.status} - {text}")
            except Exception as e:
                logger.warning(f"OpenRouter vision failed: {e}")

        raise RuntimeError("All image providers failed")

    async def extract_text_from_image_tesseract(self, image_bytes: bytes) -> str:
        """Extract text using Tesseract OCR (lightweight, works on Render)."""
        import pytesseract
        from PIL import Image
        import io
        try:
            image = Image.open(io.BytesIO(image_bytes))
            text = pytesseract.image_to_string(image, lang='rus+eng')
            return text.strip()
        except Exception as e:
            logger.warning(f"Tesseract OCR failed: {e}")
            return ""

    async def extract_text_from_image(self, image_bytes: bytes) -> str:
        """Extract text from image using OCR chain:
        EasyOCR (local, not on Render) → Tesseract (lightweight, always available)."""
        import io
        from PIL import Image
        
        text = ""
        
        # Попытка 1: EasyOCR (только если не Render — PyTorch не влезает в лимиты)
        if not settings.render_deploy:
            try:
                import numpy as np
                import easyocr
                image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
                if not hasattr(self, '_ocr_reader'):
                    logger.info("Initializing OCR model (this takes ~10s on first run)...")
                    self._ocr_reader = easyocr.Reader(['ru', 'en'], gpu=False, verbose=False)
                image_np = np.array(image)
                results = self._ocr_reader.readtext(image_np)
                text = ' '.join([r[1] for r in results]).strip()
            except Exception as e:
                logger.warning(f"EasyOCR failed: {e}")
        
        # Попытка 2: Tesseract (работает везде, лёгкий)
        if not text:
            text = await self.extract_text_from_image_tesseract(image_bytes)
        
        return text

    async def extract_text_from_image_openrouter(self, image_bytes: bytes) -> str:
        """Extract text from image using OpenRouter vision model (good for handwriting).
        Falls back to EasyOCR if OpenRouter fails or returns empty text."""
        import base64, io
        import numpy as np
        from PIL import Image

        # Try OpenRouter first
        try:
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
                                    "Ты — система OCR. Распознай ВЕСЬ текст на изображении и верни ТОЛЬКО распознанный текст. "
                                    "Не добавляй своих комментариев, описаний или пояснений. "
                                    "Если это медицинский документ — всё равно просто верни текст. "
                                    "Если текст нечитаем — верни пустую строку."
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
                    if response.status == 200:
                        data = await response.json()
                        text = data['choices'][0]['message']['content'].strip()
                        if len(text) > 20:
                            return text
                        logger.info(f"OpenRouter vision returned short text ({len(text)} chars), falling back to EasyOCR")
                    else:
                        err_text = await response.text()
                        logger.warning(f"OpenRouter vision error: {response.status} - {err_text[:200]}")
        except Exception as e:
            logger.warning(f"OpenRouter vision failed: {e}")

        # Fallback: Tesseract (лёгкий, работает на Render)
        try:
            text = await self.extract_text_from_image_tesseract(image_bytes)
            if text:
                return text
        except Exception as e:
            logger.warning(f"Tesseract fallback failed: {e}")

        # Last resort: EasyOCR (только не на Render)
        if not settings.render_deploy:
            try:
                if not hasattr(self, '_ocr_reader'):
                    logger.info("Initializing EasyOCR model for handwriting fallback...")
                    import easyocr
                    self._ocr_reader = easyocr.Reader(['ru', 'en'], gpu=False, verbose=False)
                image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
                image_np = np.array(image)
                results = self._ocr_reader.readtext(image_np)
                extracted = ' '.join([r[1] for r in results])
                if extracted.strip():
                    return extracted.strip()
            except Exception as e:
                logger.warning(f"EasyOCR fallback also failed: {e}")

        return ""

    async def query(self, prompt: str) -> str:
        """Query LLM with full redundancy:
        Gemini (primary, лимит может быть исчерпан)
          → OpenRouter DeepSeek V4 Flash (fallback 1)
            → OpenCode Zen Big Pickle (fallback 2, бесплатно)"""
        providers = [
            ("Gemini", self.query_gemini),
            ("OpenRouter", self.query_openrouter),
            ("OpenCode Zen", self.query_opencode_zen),
        ]
        last_error = None
        for name, func in providers:
            try:
                logger.info(f"Trying {name}...")
                result = await asyncio.wait_for(func(prompt), timeout=45)
                logger.info(f"{name} responded successfully")
                return result
            except Exception as e:
                logger.warning(f"{name} failed: {e}")
                last_error = e
                continue
        raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")


llm_client = LLMClient()
