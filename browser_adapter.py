"""Browser-worker API bridge for the existing Python comparison engine.

No server, Pyodide-specific imports, network requests, or document filesystem
writes are required. The worker supplies modules, demo data, fonts and optional
format libraries in its virtual filesystem before calling dispatch().
"""
from __future__ import annotations

import base64
import copy
import importlib.util
import json
from pathlib import Path
import time
from urllib.parse import parse_qs, urlparse

import backend
from export_api import FORMATS, export_document
from legal_report import build_conclusion
from legal_text import display_name

ROOT = Path(__file__).resolve().parent
MAX_BODY = 35 * 1024 * 1024

CONTROL = {
 "before": [
  {"name":"Контроль — финансы — редакция 1","unit":"Департамент финансов","text":"# Департамент финансов\n1.1. Департамент финансов формирует бюджет подразделений.\n1.2. Департамент финансов ведет реестр договоров.\n1.3. Департамент финансов проверяет платежные операции.\n1.4. Департамент финансов готовит отчет по ликвидности."},
 ],
 "after": [
  {"name":"Контроль — финансы — редакция 2","unit":"Департамент финансов","text":"# Департамент финансов\n2.1. Департамент финансов формирует бюджет подразделений.\n2.2. Департамент финансов проверяет платежные операции.\n2.3. Департамент финансов выполняет платежные операции."},
  {"name":"Контроль — казначейство — редакция 2","unit":"Департамент казначейства","text":"# Департамент казначейства\n3.1. Департамент казначейства формирует бюджет подразделений.\n3.2. Департамент казначейства ведет реестр договоров."}
 ],
 "label":"Контрольный пример распределения функций и полномочий"
}


def _payload(value):
    if not isinstance(value, dict):
        raise ValueError("Ожидается JSON-объект")
    try:
        body = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("Ожидается JSON-объект") from exc
    if len(body) > MAX_BODY:
        raise ValueError("Допустимый размер запроса: до 35 МБ")
    return value


def _extract(payload):
    files = payload.get("files", [])
    if not isinstance(files, list) or not 1 <= len(files) <= 30:
        raise ValueError("Выберите от 1 до 30 файлов")
    if any(not isinstance(item, dict) for item in files):
        raise ValueError("Каждый файл должен содержать название и содержимое")
    output = []
    for item in files:
        name = str(item.get("name", "document"))
        try:
            raw = base64.b64decode(item.get("content", ""), validate=True)
            if len(raw) > backend.MAX_FILE_BYTES:
                raise ValueError("Файл превышает 15 МБ")
            result = backend.extract_file(name, raw)
            if isinstance(result, str):
                result = {"text": result, "warnings": []}
            output.append({"name": display_name(name), **result})
        except Exception as exc:
            output.append({"name": display_name(name), "error": str(exc), "text": "", "warnings": []})
    return {"files": output}


def _demo(query):
    if parse_qs(query).get("case", ["audit"])[0] == "control":
        return copy.deepcopy(CONTROL)
    return {
        "before": [{"name": "Положение о внутреннем аудите · редакция 8",
                    "text": (ROOT / "data/audit-before.md").read_text(encoding="utf-8"),
                    "unit": "Блок внутреннего аудита"}],
        "after": [{"name": "Положение о внутреннем аудите · редакция 9",
                   "text": (ROOT / "data/audit-after.md").read_text(encoding="utf-8"),
                   "unit": "Блок внутреннего аудита"}],
        "label": "Предоставленные обезличенные документы · редакции 8 и 9",
    }


def dispatch(url, payload=None):
    """Return a JSON-serializable API result, or raise a useful validation error.

    Binary export results contain base64 in ``content``, plus ``encoding``,
    ``extension``, ``name`` and ``mime``. The JavaScript caller creates a Blob
    download; Python does not persist documents or generated exports.
    """
    if not isinstance(url, str):
        raise ValueError("Неверный адрес запроса")
    parsed = urlparse(url)
    if parsed.path == "/api/health":
        return {"ok": True, "version": "1.0.0", "browser": True, "local": True,
                "pdf": importlib.util.find_spec("pypdf") is not None,
                "llmConfigured": False, "llmModel": ""}
    if parsed.path == "/api/demo":
        return _demo(parsed.query)
    if parsed.path not in ("/api/extract", "/api/analyze", "/api/export-document"):
        raise ValueError("Не найдено")
    payload = _payload(payload)
    if parsed.path == "/api/extract":
        return _extract(payload)
    if parsed.path == "/api/analyze":
        for side in ("before", "after"):
            docs = payload.get(side)
            if not isinstance(docs, list) or not 1 <= len(docs) <= 30:
                raise ValueError("Нужен хотя бы один документ в каждом комплекте; максимум 30")
            if any(not isinstance(doc, dict) or not isinstance(doc.get("text"), str)
                   or not doc["text"].strip() for doc in docs):
                raise ValueError("Каждый документ должен содержать читаемый текст")
        started = time.perf_counter()
        # Ignore any client LLM toggle; this route never contacts Ollama or an API.
        result = backend.analyze({**payload, "llm": False})
        result["conclusion"] = build_conclusion(result)
        result["elapsedMs"] = round((time.perf_counter() - started) * 1000)
        return result
    extension = str(payload.get("extension", ""))
    content = export_document(payload.get("analysis"), extension)
    return {"content": base64.b64encode(content).decode("ascii"), "encoding": "base64",
            "extension": extension, "name": "Versa-сравнение." + extension, "mime": FORMATS[extension]}
