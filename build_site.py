"""Build a static, browser-only edition. No uploads, histories or exports are published."""
from pathlib import Path
import json, shutil
ROOT=Path(__file__).resolve().parent
OUT=ROOT/"dist"
PYTHON=["backend.py","comparison.py","comparison_report.py","legal_text.py","legal_report.py",
        "export_api.py","export_documents.py","export_xlsx.py","browser_adapter.py",
        "assets/Roboto-Regular.ttf","assets/Roboto-Bold.ttf"]
ASSETS=["app.js","styles.css","browser-api.js","browser-worker.mjs","assets/Roboto.ttf","assets/Roboto-OFL.txt","THIRD_PARTY.md"]
def main():
    OUT.mkdir(exist_ok=True)
    for name in ASSETS:
        dest=OUT/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/name,dest)
    for name in PYTHON:
        dest=OUT/"_python"/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/name,dest)
    page=(ROOT/"index.html").read_text(encoding="utf-8")
    page=page.replace('href="/"','href="./"').replace('href="/styles.css"','href="./styles.css"')
    page=page.replace('<script src="/app.js"></script>','<script src="./browser-api.js"></script><script src="./app.js"></script>')
    assert "browser-api.js" in page, "Browser transport must load before app.js"
    page=page.replace('<option value="audit">Редакции 8 и 9 · предоставленные документы</option>', "")
    page=page.replace("Локально и конфиденциально","Обработка в вашем браузере")
    page=page.replace("<main>",'<main><p id="browser-engine-status" class="browser-engine-status" role="status">Документы обрабатываются в вашем браузере и не отправляются на сервер. При первом сравнении загружается модуль обработки.</p>',1)
    (OUT/"index.html").write_text(page,encoding="utf-8")
    css=(OUT/"styles.css").read_text(encoding="utf-8").replace("url('/assets/","url('./assets/").replace('url("/assets/','url("./assets/').replace('url(/assets/','url(./assets/')
    css+='\n.browser-engine-status{margin:0 0 20px;padding:14px 18px;border:1px solid #b4d8ee;border-radius:14px;background:#eef8ff;color:#184e80;font-size:15px;line-height:1.6}\n'
    (OUT/"styles.css").write_text(css,encoding="utf-8")
    (OUT/".nojekyll").write_text("",encoding="utf-8")
    expected=set(ASSETS+["index.html",".nojekyll"]+["_python/"+p for p in PYTHON])
    actual={p.relative_to(OUT).as_posix() for p in OUT.rglob("*") if p.is_file()}
    if actual!=expected:raise RuntimeError("Unexpected build files: "+str(actual^expected))
    print(json.dumps({"files":len(actual),"bytes":sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file()),"directory":str(OUT)},ensure_ascii=False))
if __name__=="__main__":main()
