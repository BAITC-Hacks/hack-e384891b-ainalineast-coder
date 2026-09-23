"""Reproducible acceptance run; writes actual results, not assumed metrics."""
from pathlib import Path
from datetime import datetime, timezone
import html, json, platform, subprocess, sys, time
import backend
from app import CONTROL
ROOT=Path(__file__).resolve().parent
def main():
    result=subprocess.run([sys.executable,"-X","utf8","-B","-m","unittest","discover","-p","tests*.py","-v"],cwd=ROOT,capture_output=True,text=True,encoding="utf-8")
    out=ROOT/"validation"
    out.mkdir(exist_ok=True)
    (out/"tests.txt").write_text(result.stdout+result.stderr,encoding="utf-8")
    if result.returncode:
        print(result.stdout+result.stderr); return result.returncode
    cases={"audit":{"before":[{"name":"audit-before.md","text":(ROOT/"data/audit-before.md").read_text(encoding="utf-8"),"unit":"Блок внутреннего аудита"}],
                    "after":[{"name":"audit-after.md","text":(ROOT/"data/audit-after.md").read_text(encoding="utf-8"),"unit":"Блок внутреннего аудита"}]},
           "control":CONTROL}
    summary={"generatedAt":datetime.now(timezone.utc).isoformat(),"python":platform.python_version(),"platform":platform.system(),"testsPassed":True,"llmLiveTested":False,"cases":{}}
    e=html.escape
    for name,payload in cases.items():
        begin=time.perf_counter(); analysis=backend.analyze(payload); elapsed=round((time.perf_counter()-begin)*1000)
        (out/(name+"-analysis.json")).write_text(json.dumps(analysis,ensure_ascii=False,indent=2),encoding="utf-8")
        clauses={c["id"]:c for d in analysis["documents"] for c in d["clauses"]}
        evidence_ok=all(c.get("id") in clauses and c["text"]==clauses[c["id"]]["text"] for f in analysis["findings"] for c in f["evidence"])
        assert evidence_ok, "Invalid source evidence"
        summary["cases"][name]={"elapsedMs":elapsed,"stats":analysis["stats"],"evidenceReferencesValid":evidence_ok}
        rows=[]
        for f in analysis["findings"]:
            rows.append("<article><h3>"+e(f["title"])+"</h3><p>"+e(f["explanation"])+"</p><p><b>Рекомендация:</b> "+e(f["recommendation"])+"</p>"+"".join("<blockquote><b>"+e(c["document"])+" · п. "+e(c["ref"])+"</b><br>"+e(c["text"])+"</blockquote>" for c in f["evidence"])+"<p class='muted'>Решение эксперта: на проверке.</p></article>")
        body="<h1>OrgLens — аналитическое заключение</h1><p>"+("Предоставленные редакции 8 и 9" if name=="audit" else "Синтетический контрольный пример")+"</p><p>Дата: "+e(summary["generatedAt"])+"</p><p>Время текущего запуска: "+str(elapsed)+" мс. Замечаний: "+str(len(analysis["findings"]))+". Все ссылки на извлечённые фрагменты проверены программно.</p><h2>Подразделения</h2><ul>"+"".join("<li>"+e(u["name"])+" — "+e({"retained":"сохранено","created":"впервые в новом комплекте","removed":"не найдено после"}.get(u["status"],u["status"]))+"</li>" for u in analysis["units"])+"</ul><h2>Наблюдения для экспертной проверки</h2>"+"".join(rows)+"<h2>Ограничения</h2><p>Использованы локальные правила и лексическое сопоставление. Языковая модель в этом запуске не использовалась. Кандидат отсутствия функции не доказывает её фактическую утрату. Источники — обезличенные материалы пользователя; внешняя нормативная проверка не выполнялась.</p>"
        page="<!doctype html><html lang='ru'><meta charset='utf-8'><title>OrgLens — заключение</title><style>body{max-width:1000px;margin:50px auto;padding:0 30px;font:16px/1.7 Arial;color:#1b2b40}h1{color:#087f82}article{border-top:1px solid #dce5ed;padding:20px 0}blockquote{border-left:3px solid #86bfb4;margin:15px 0;padding:10px 20px;background:#f4f8f8}.muted{color:#778899;font-size:13px}@media print{article{break-inside:avoid}}</style><body>"+body+"</body></html>"
        (out/(name+"-conclusion.html")).write_text(page,encoding="utf-8")
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2));return 0
if __name__=="__main__": raise SystemExit(main())
