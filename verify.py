"""Reproducible acceptance run; writes actual results, not assumed metrics."""
from pathlib import Path
from datetime import datetime, timezone
import html, json, platform, subprocess, sys, time
import backend
from comparison_report import render_comparison
from legal_report import build_conclusion, render_conclusion
from app import CONTROL
ROOT=Path(__file__).resolve().parent
def main():
    result=subprocess.run([sys.executable,"-X","utf8","-B","-m","unittest","discover","-p","tests*.py","-v"],cwd=ROOT,capture_output=True,text=True,encoding="utf-8")
    out=ROOT/"validation"
    out.mkdir(exist_ok=True)
    (out/"tests.txt").write_text(result.stdout+result.stderr,encoding="utf-8")
    if result.returncode:
        print(result.stdout+result.stderr); return result.returncode
    cases={"audit":{"before":[{"name":"Положение о внутреннем аудите · редакция 8.md","text":(ROOT/"data/audit-before.md").read_text(encoding="utf-8"),"unit":"Блок внутреннего аудита"}],
                    "after":[{"name":"Положение о внутреннем аудите · редакция 9.md","text":(ROOT/"data/audit-after.md").read_text(encoding="utf-8"),"unit":"Блок внутреннего аудита"}]},
           "control":CONTROL}
    summary={"generatedAt":datetime.now(timezone.utc).isoformat(),"python":platform.python_version(),"platform":platform.system(),"testsPassed":True,"llmLiveTested":False,"cases":{}}
    e=html.escape
    for name,payload in cases.items():
        begin=time.perf_counter(); analysis=backend.analyze(payload); elapsed=round((time.perf_counter()-begin)*1000)
        analysis["conclusion"]=build_conclusion(analysis)
        (out/(name+"-analysis.json")).write_text(json.dumps(analysis,ensure_ascii=False,indent=2),encoding="utf-8")
        clauses={c["id"]:c for d in analysis["documents"] for c in d["clauses"]}
        evidence_ok=all(c.get("id") in clauses and c["text"]==clauses[c["id"]]["text"] for f in analysis["findings"] for c in f["evidence"])
        assert evidence_ok, "Invalid source evidence"
        summary["cases"][name]={"elapsedMs":elapsed,"stats":analysis["stats"],"evidenceReferencesValid":evidence_ok,"comparisonStats":analysis["comparison"]["stats"]}
        (out/(name+"-comparison.html")).write_text(render_comparison(analysis),encoding="utf-8")
        page=render_conclusion(analysis)
        (out/(name+"-conclusion.html")).write_text(page,encoding="utf-8")
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2));return 0
if __name__=="__main__": raise SystemExit(main())
