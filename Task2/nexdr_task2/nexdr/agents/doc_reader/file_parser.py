# Copyright (c) Nex-AGI. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import asyncio
import base64
import http.client
import json
import logging
import mimetypes
import os
import tempfile
from pathlib import Path
from typing import Tuple
from urllib import request as urllib_request

from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)

JINA_READER_ENDPOINT = "https://r.jina.ai/"
SERPER_SCRAPE_HOST = "scrape.serper.dev"
DEFAULT_SUFFIX = ".txt"
TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".py",
    ".json",
    ".csv",
    ".tsv",
    ".yaml",
    ".yml",
    ".html",
    ".htm",
}
PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
MARKITDOWN_EXTENSIONS = {
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
}


class FileParser:
    """
    Fetch textual content from URLs or local files using configurable providers.
    Returns a tuple of (success, content, suffix).
    """

    def __init__(self, timeout: float = 45.0) -> None:
        self.timeout = timeout
        self.jina_api_key = os.getenv("JINA_API_KEY")
        self.serper_api_key = os.getenv("SERPER_API_KEY")
        self.providers = self._load_provider_order()

    async def parse(self, url_or_local_file: str) -> Tuple[bool, str, str]:
        if self._looks_like_url(url_or_local_file):
            return await self._parse_remote(url_or_local_file)
        return await self._parse_local(url_or_local_file)

    async def _parse_remote(self, url: str) -> Tuple[bool, str, str]:
        errors = []
        for provider in self.providers:
            if provider == "builtin":
                success, content, suffix = await self._parse_remote_with_builtin(url)
            elif provider == "jina":
                success, content, suffix = await self._parse_remote_with_jina(url)
            elif provider == "serper":
                success, content, suffix = await self._parse_remote_with_serper(url)
            else:
                logger.warning("Unknown document parser provider: %s", provider)
                errors.append(f"{provider}: unsupported provider")
                continue

            if success:
                return True, content, suffix
            errors.append(f"{provider}: {content}")

        error_msg = (
            "Failed to fetch document with available providers. "
            + " | ".join(errors)
        )
        return False, error_msg, DEFAULT_SUFFIX

    async def _parse_remote_with_builtin(self, url: str) -> Tuple[bool, str, str]:
        try:
            raw_bytes, content_type = await asyncio.to_thread(
                self._fetch_bytes_and_type, url, self.timeout
            )
        except Exception as exc:
            logger.exception("Builtin URL fetch failed: %s", url)
            return False, f"Failed to fetch {url}: {exc}", DEFAULT_SUFFIX

        content_type = (content_type or "").lower()
        suffix = self._suffix_from_url(url)
        if "application/pdf" in content_type or suffix in PDF_EXTENSIONS:
            try:
                return await asyncio.to_thread(self._parse_pdf_bytes, raw_bytes)
            except Exception as exc:
                return False, f"Failed to parse remote pdf: {exc}", ".pdf"

        if content_type.startswith("image/") or suffix in IMAGE_EXTENSIONS:
            try:
                return await asyncio.to_thread(
                    self._parse_image_bytes, raw_bytes, suffix or ".png"
                )
            except Exception as exc:
                return False, f"Failed to parse remote image: {exc}", suffix or ".png"

        text = self._bytes_to_text(raw_bytes)
        if "<html" in text.lower():
            text = self._html_to_text(text)
            return True, text, ".md"
        return True, text, suffix or DEFAULT_SUFFIX

    async def _parse_remote_with_jina(self, url: str) -> Tuple[bool, str, str]:
        if not self.jina_api_key:
            return (
                False,
                "JINA_API_KEY is not set. Skip Jina provider.",
                DEFAULT_SUFFIX,
            )

        jina_url = self._build_jina_reader_url(url)
        logger.info("Fetching document via Jina reader: %s", jina_url)

        try:
            raw_bytes = await asyncio.to_thread(
                self._fetch_bytes_with_auth, jina_url, self.timeout, self.jina_api_key
            )
        except Exception as exc:
            logger.exception("Failed to fetch remote document via Jina: %s", url)
            return False, f"Failed to fetch {url}: {exc}", DEFAULT_SUFFIX

        content = self._bytes_to_text(raw_bytes)
        if not content.strip():
            return False, "Empty content returned from Jina reader", DEFAULT_SUFFIX
        return True, content, DEFAULT_SUFFIX

    async def _parse_remote_with_serper(self, url: str) -> Tuple[bool, str, str]:
        if not self.serper_api_key:
            return (
                False,
                "SERPER_API_KEY is not set. Skip Serper provider.",
                DEFAULT_SUFFIX,
            )

        payload = json.dumps({"url": url})
        headers = {
            "X-API-KEY": self.serper_api_key,
            "Content-Type": "application/json",
        }
        logger.info("Fetching document via Serper scrape: %s", url)

        try:
            status, raw_bytes = await asyncio.to_thread(
                self._fetch_serper_bytes,
                payload,
                headers,
                self.timeout,
            )
        except Exception as exc:
            logger.exception("Failed to fetch remote document via Serper: %s", url)
            return False, f"Failed to fetch via Serper {url}: {exc}", DEFAULT_SUFFIX

        if status >= 400:
            return False, f"Serper scrape error (status {status})", DEFAULT_SUFFIX

        decoded = self._bytes_to_text(raw_bytes)
        parsed = self._extract_text_from_serper_response(decoded)
        if not parsed.strip():
            return False, "Empty content returned from Serper scrape", DEFAULT_SUFFIX
        return True, parsed, ".md"

    async def _parse_local(self, path_str: str) -> Tuple[bool, str, str]:
        path = Path(path_str).expanduser().resolve()
        if not path.exists():
            return False, f"Local file not found: {path}", DEFAULT_SUFFIX

        suffix = path.suffix.lower()
        try:
            if suffix in PDF_EXTENSIONS:
                return await asyncio.to_thread(self._parse_local_pdf, path)
            if suffix in IMAGE_EXTENSIONS:
                return await asyncio.to_thread(self._parse_local_image, path)
            if suffix in MARKITDOWN_EXTENSIONS:
                return await asyncio.to_thread(self._parse_local_with_markitdown, path)

            read_as_text = suffix in TEXT_EXTENSIONS or self._is_probably_text(path)
            if read_as_text:
                content = await asyncio.to_thread(
                    path.read_text, encoding="utf-8", errors="ignore"
                )
            else:
                content = self._bytes_to_text(await asyncio.to_thread(path.read_bytes))
        except Exception as exc:
            logger.exception("Failed to read local file: %s", path)
            return False, f"Failed to read {path}: {exc}", suffix or DEFAULT_SUFFIX

        if not content.strip():
            return False, "Local file is empty", suffix or DEFAULT_SUFFIX
        return True, content, suffix or DEFAULT_SUFFIX

    def _parse_local_pdf(self, path: Path) -> Tuple[bool, str, str]:
        try:
            import fitz  # pymupdf

            doc = fitz.open(str(path))
            pages = []
            for index, page in enumerate(doc, start=1):
                text = page.get_text("text").strip()
                if text:
                    pages.append(f"## Page {index}\n\n{text}")
            doc.close()
            if pages:
                return True, "\n\n".join(pages), ".md"
        except Exception as exc:
            logger.warning("PyMuPDF parse failed for %s: %s", path, exc)

        return self._parse_local_with_markitdown(path)

    def _parse_local_with_markitdown(self, path: Path) -> Tuple[bool, str, str]:
        try:
            from markitdown import MarkItDown

            md = MarkItDown()
            result = md.convert(str(path))
            text = getattr(result, "text_content", "") or str(result)
            if text.strip():
                return True, text, ".md"
        except Exception as exc:
            logger.warning("MarkItDown parse failed for %s: %s", path, exc)
        return False, f"Failed to parse document: {path.name}", path.suffix or ".md"

    def _parse_local_image(self, path: Path) -> Tuple[bool, str, str]:
        ocr_text = self._ocr_image_with_paddle(path)
        if ocr_text:
            content = f"# OCR Result\n\n{ocr_text}"
            return True, content, ".md"

        caption = self._describe_image_with_multimodal(path)
        if caption:
            content = f"# Image Description\n\n{caption}"
            return True, content, ".md"

        return (
            False,
            "Failed to parse image. Install paddleocr or configure MULTI_MODAL_LLM_*.",
            path.suffix or ".png",
        )

    def _parse_image_bytes(self, image_bytes: bytes, suffix: str) -> Tuple[bool, str, str]:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(image_bytes)
            tmp_path = Path(tmp.name)
        try:
            return self._parse_local_image(tmp_path)
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

    def _parse_pdf_bytes(self, pdf_bytes: bytes) -> Tuple[bool, str, str]:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(pdf_bytes)
            tmp_path = Path(tmp.name)
        try:
            return self._parse_local_pdf(tmp_path)
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

    def _ocr_image_with_paddle(self, path: Path) -> str:
        try:
            from paddleocr import PaddleOCR
        except Exception:
            return ""
        try:
            lang = os.getenv("PADDLEOCR_LANG", "ch")
            ocr = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)
            result = ocr.ocr(str(path), cls=True)
            lines = []
            for page_result in result or []:
                for row in page_result or []:
                    if len(row) >= 2 and row[1]:
                        text = row[1][0]
                        if text:
                            lines.append(text)
            return "\n".join(lines).strip()
        except Exception as exc:
            logger.warning("PaddleOCR failed for %s: %s", path, exc)
            return ""

    def _describe_image_with_multimodal(self, path: Path) -> str:
        base_url = os.getenv("MULTI_MODAL_LLM_BASE_URL", "").strip()
        api_key = os.getenv("MULTI_MODAL_LLM_API_KEY", "").strip()
        model = os.getenv("MULTI_MODAL_LLM_MODEL", "").strip()
        if not base_url or not api_key or not model:
            return ""
        try:
            from openai import OpenAI
        except Exception:
            return ""
        try:
            raw = path.read_bytes()
            image_base64 = base64.b64encode(raw).decode("utf-8")
            mime_type, _ = mimetypes.guess_type(path.name)
            mime_type = mime_type or "image/png"
            client = OpenAI(api_key=api_key, base_url=base_url)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Describe the image and extract any visible text. "
                            "If text exists, keep original language."
                        ),
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Please describe this image."},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{image_base64}"
                                },
                            },
                        ],
                    },
                ],
            )
            return (response.choices[0].message.content or "").strip()
        except Exception as exc:
            logger.warning("Multimodal image parse failed for %s: %s", path, exc)
            return ""

    @staticmethod
    def _looks_like_url(value: str) -> bool:
        return value.startswith("http://") or value.startswith("https://")

    @staticmethod
    def _fetch_bytes_with_auth(url: str, timeout: float, api_key: str) -> bytes:
        headers = {
            "User-Agent": "NexDR-Task2/1.0",
            "Authorization": f"Bearer {api_key}",
        }
        request = urllib_request.Request(url, headers=headers)
        with urllib_request.urlopen(request, timeout=timeout) as response:
            return response.read()

    @staticmethod
    def _fetch_bytes_and_type(url: str, timeout: float) -> tuple[bytes, str]:
        request = urllib_request.Request(url, headers={"User-Agent": "NexDR-Task2/1.0"})
        with urllib_request.urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get("Content-Type", "")
            return response.read(), content_type

    @staticmethod
    def _fetch_serper_bytes(
        payload: str, headers: dict, timeout: float
    ) -> Tuple[int, bytes]:
        conn = http.client.HTTPSConnection(SERPER_SCRAPE_HOST, timeout=timeout)
        try:
            conn.request("POST", "/", body=payload, headers=headers)
            res = conn.getresponse()
            status = res.status
            data = res.read()
        finally:
            conn.close()
        return status, data

    @staticmethod
    def _build_jina_reader_url(url: str) -> str:
        if url.startswith(JINA_READER_ENDPOINT):
            return url
        return f"{JINA_READER_ENDPOINT}{url}"

    @staticmethod
    def _bytes_to_text(raw_bytes: bytes) -> str:
        try:
            return raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return raw_bytes.decode("utf-8", errors="ignore")

    @staticmethod
    def _html_to_text(html_text: str) -> str:
        soup = BeautifulSoup(html_text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)

    @staticmethod
    def _suffix_from_url(url: str) -> str:
        return Path(url.split("?")[0]).suffix.lower()

    @staticmethod
    def _is_probably_text(path: Path) -> bool:
        mime_type, _ = mimetypes.guess_type(path.name)
        return mime_type is not None and mime_type.startswith("text")

    @staticmethod
    def _load_provider_order() -> list[str]:
        providers_env = os.getenv("DOC_READER_PROVIDERS")
        if not providers_env:
            return ["builtin", "jina", "serper"]
        providers = [
            provider.strip().lower()
            for provider in providers_env.split(",")
            if provider.strip()
        ]
        return providers or ["builtin", "jina", "serper"]

    @staticmethod
    def _extract_text_from_serper_response(decoded_body: str) -> str:
        try:
            parsed_json = json.loads(decoded_body)
        except json.JSONDecodeError:
            return decoded_body

        if not isinstance(parsed_json, dict):
            return decoded_body
        if isinstance(parsed_json.get("markdown"), str):
            return parsed_json["markdown"]
        if isinstance(parsed_json.get("content"), str):
            return parsed_json["content"]
        if isinstance(parsed_json.get("text"), str):
            return parsed_json["text"]
        return decoded_body


if __name__ == "__main__":
    parser = FileParser()
    success, content, suffix = asyncio.run(parser.parse("https://chat2svg.github.io/"))
    print(success, suffix, content[:300])
