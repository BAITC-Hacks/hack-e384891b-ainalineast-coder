"""OrgLens: local evidence-first organizational analysis workbench."""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import base64, importlib.util, json, os, time, traceback, re, uuid
import backend

ROOT = Path(__file__).resolve().parent
MAX_BODY = 35 * 1024 * 1024
CONTROL = {
 "before": [
  {"name":"Контроль — до.md","unit":"Департамент финансов","text":"# Департамент финансов\n1.1. Департамент финансов формирует бюджет подразделений.\n1.2. Департамент финансов ведет реестр договоров.\n1.3. Департамент финансов проверяет платежные операции.\n1.4. Департамент финансов готовит отчет по ликвидности."},
 ],
 "after": [
  {"name":"Контроль — после — финансы.md","unit":"Департамент финансов","text":"# Департамент финансов\n2.1. Департамент финансов формирует бюджет подразделений.\n2.2. Департамент финансов проверяет платежные операции.\n2.3. Департамент финансов выполняет платежные операции."},
  {"name":"Контроль — после — казначейство.md","unit":"Департамент казначейства","text":"# Департамент казначейства\n3.1. Департамент казначейства формирует бюджет подразделений.\n3.2. Департамент казначейства ведет реестр договоров."}
 ],
 "label":"Синтетический контрольный пример — ожидаемые случаи описаны в docs/DEMO.md"
}

class Handler(BaseHTTPRequestHandler):
    server_version = "OrgLens/1.0"
    def log_message(self, fmt, *args):
        # Never log document contents.
        print(time.strftime("%H:%M:%S"), fmt % args)
    def reply(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(body)))
        self.send_header("Cache-Control","no-store")
        self.send_header("X-Content-Type-Options","nosniff")
        self.end_headers()
        self.wfile.write(body)
    def do_GET(self):
        parsed=urlparse(self.path)
        if parsed.path=="/api/health":
            self.reply({"ok":True,"version":"1.0.0","pdf":importlib.util.find_spec("pypdf") is not None,
                        "llmConfigured":bool(os.getenv("ORGLENS_LLM_MODEL")),"llmModel":os.getenv("ORGLENS_LLM_MODEL",""),
                        "local":True})
            return
        if parsed.path=="/api/demo":
            if parse_qs(parsed.query).get("case",["audit"])[0]=="control":
                self.reply(CONTROL)
            else:
                try:
                    self.reply({"before":[{"name":"Положение о внутреннем аудите · редакция 8.md","text":(ROOT/"data/audit-before.md").read_text(encoding="utf-8"),"unit":"Блок внутреннего аудита"}],
                                "after":[{"name":"Положение о внутреннем аудите · редакция 9.md","text":(ROOT/"data/audit-after.md").read_text(encoding="utf-8"),"unit":"Блок внутреннего аудита"}],
                                "label":"Предоставленные обезличенные документы · редакции 8 и 9"})
                except FileNotFoundError:
                    self.reply({"error":"Демонстрационные документы отсутствуют в data."},500)
            return
        if re.fullmatch(r"/exports/[a-f0-9]{12}\.(html|json|csv)",parsed.path):
            file=ROOT/parsed.path.lstrip("/")
            if not file.is_file():
                self.reply({"error":"Файл экспорта не найден"},404);return
            body=file.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type",{"html":"text/html; charset=utf-8","json":"application/json; charset=utf-8","csv":"text/csv; charset=utf-8"}[file.suffix[1:]])
            self.send_header("Content-Disposition",'attachment; filename="OrgLens-report'+file.suffix+'"')
            self.send_header("Content-Security-Policy","sandbox; default-src 'none'; style-src 'unsafe-inline'")
            self.send_header("Content-Length",str(len(body)))
            self.end_headers();self.wfile.write(body);return
        files={"/":"index.html","/index.html":"index.html","/app.js":"app.js","/styles.css":"styles.css"}
        if parsed.path not in files:
            self.reply({"error":"Не найдено"},404)
            return
        file=ROOT/files[parsed.path]
        if not file.exists():
            self.reply({"error":"Ресурс отсутствует"},404); return
        body=file.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type",{"html":"text/html; charset=utf-8","js":"text/javascript; charset=utf-8","css":"text/css; charset=utf-8"}[file.suffix[1:]])
        self.send_header("Content-Length",str(len(body)))
        self.send_header("Cache-Control","no-cache")
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("Content-Security-Policy","default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self.end_headers(); self.wfile.write(body)
    def do_POST(self):
        # Reject browser cross-origin calls; only the local workbench may submit documents.
        origin=self.headers.get("Origin")
        allowed={f"http://127.0.0.1:{self.server.server_port}",f"http://localhost:{self.server.server_port}"}
        if origin and origin not in allowed:
            self.reply({"error":"Недопустимый источник запроса"},403); return
        try:
            size=int(self.headers.get("Content-Length","0"))
            if not 0<size<=MAX_BODY:
                self.reply({"error":"Допустимый размер запроса: до 35 МБ"},413); return
            payload=json.loads(self.rfile.read(size).decode("utf-8"))
            if not isinstance(payload,dict):
                raise ValueError("Ожидается JSON-объект")
            if self.path=="/api/extract":
                files=payload.get("files",[])
                if not isinstance(files,list) or not 1<=len(files)<=30:
                    raise ValueError("Выберите от 1 до 30 файлов")
                output=[]
                for item in files:
                    name=str(item.get("name","document"))
                    try:
                        raw=base64.b64decode(item.get("content",""),validate=True)
                        if len(raw)>15*1024*1024:
                            raise ValueError("Файл превышает 15 МБ")
                        result=backend.extract_file(name,raw)
                        if isinstance(result,str): result={"text":result,"warnings":[]}
                        output.append({"name":name,**result})
                    except Exception as exc:
                        output.append({"name":name,"error":str(exc),"text":"","warnings":[]})
                self.reply({"files":output})
            elif self.path=="/api/export":
                extension=str(payload.get("extension",""))
                content=payload.get("content")
                if extension not in ("html","json","csv") or not isinstance(content,str) or len(content)>20_000_000:
                    raise ValueError("Неверный формат или размер экспорта")
                folder=ROOT/"exports"
                folder.mkdir(exist_ok=True)
                file=folder/(uuid.uuid4().hex[:12]+"."+extension)
                file.write_text(content,encoding="utf-8")
                self.reply({"href":"/exports/"+file.name,"path":str(file),"name":file.name})
            elif self.path=="/api/analyze":
                for side in ("before","after"):
                    docs=payload.get(side)
                    if not isinstance(docs,list) or not 1<=len(docs)<=30:
                        raise ValueError("Нужен хотя бы один документ в каждом комплекте; максимум 30")
                    if any(not isinstance(d,dict) or not isinstance(d.get("text"),str) or not d["text"].strip() for d in docs):
                        raise ValueError("Каждый документ должен содержать читаемый текст")
                started=time.perf_counter()
                result=backend.analyze(payload)
                result["elapsedMs"]=round((time.perf_counter()-started)*1000)
                self.reply(result)
            else: self.reply({"error":"Не найдено"},404)
        except (ValueError,TypeError,KeyError) as exc:
            self.reply({"error":str(exc)},400)
        except Exception:
            traceback.print_exc()
            self.reply({"error":"Ошибка анализа. Подробности доступны в локальном терминале."},500)

def main():
    port=int(os.getenv("ORGLENS_PORT","8765"))
    server=ThreadingHTTPServer(("127.0.0.1",port),Handler)
    print(f"OrgLens is ready: http://127.0.0.1:{port}",flush=True)
    print("Documents stay local. Ctrl+C to stop.",flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
if __name__=="__main__": main()
