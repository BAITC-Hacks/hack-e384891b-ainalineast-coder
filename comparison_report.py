"""Standalone three-column document comparison for Versa."""
import html
def render_comparison(analysis):
    data=analysis["comparison"]
    esc=lambda value:html.escape(str(value or ""))
    labels={"unchanged":"Без изменений","changed":"Изменён","added":"Добавлен","removed":"Удалён","moved":"Перенумерован / перенесён"}
    def cell(clause,parts,side):
        if not clause:
            return '<span class="absence">— '+"Данный пункт в документе отсутствует."+'</span>'
        text=""
        for p in parts or [{"text":clause["text"],"kind":"equal"}]:
            value=esc(p["text"])
            tag={"removed":"del","added":"ins"}.get(p["kind"])
            text+=("<"+tag+">"+value+"</"+tag+">") if tag else value
        source='<div class="source">'+esc(clause.get("document",""))+'</div>' if len(data["documents"][side])>1 else ''
        return source+'<div class="ref">'+esc(clause["ref"])+'</div><div class="text">'+text+'</div>'
    before=" + ".join(d["name"] for d in data["documents"]["before"])
    after=" + ".join(d["name"] for d in data["documents"]["after"])
    rows=[]
    for row in data["rows"]:
        rows.append('<tr><td>'+cell(row["before"],row["beforeParts"],"before")+'</td><td>'+cell(row["after"],row["afterParts"],"after")+'</td><td><b class="status">'+labels.get(row["status"],row["status"])+'</b><div class="explanation">'+esc(row["explanation"])+'</div></td></tr>')
    style="body{font:16px/1.85 Arial,sans-serif;color:#263e4f;margin:35px}h1{color:#0095da;font-size:34px}p{color:#688392}table{border-collapse:collapse;table-layout:fixed;width:100%}th{background:#eaf6fd;text-align:left;vertical-align:top;color:#126b9b;font-size:19px;padding:22px;border:1px solid #cee4f1;width:37%}th:last-child{width:26%}td{padding:23px;border:1px solid #dce8ef;vertical-align:top;overflow-wrap:anywhere}.source{font-size:13px;color:#688392;margin-bottom:8px}.ref{display:inline-block;font-size:13px;color:#0085c2;background:#eef8fe;padding:2px 8px;margin-bottom:13px;font-weight:bold}.text,.explanation{white-space:pre-wrap}del{background:#fff0f2;color:#be3546;font-weight:bold}ins{background:#fff0e9;color:#ae2f32;text-decoration:none;font-weight:bold}.status{display:block;color:#168dc6;font-size:13px;margin-bottom:12px}.explanation{font-size:15px;color:#587080}.absence{color:#97aab6;font-size:14px}@page{size:A3 landscape;margin:13mm}@media print{body{margin:0}thead{display:table-header-group}tr{break-inside:avoid}}"
    return '<!doctype html><html lang="ru"><meta charset="utf-8"><title>Versa — сравнительная таблица</title><style>'+style+'</style><body><h1>Versa · Сравнительная таблица</h1><p>Все пункты в порядке документа 1. Красный зачёркнутый текст — удаление; красный жирный текст — дополнение. Пояснения требуют экспертной проверки.</p><table><thead><tr><th>Документ 1<br>'+esc(before)+'</th><th>Документ 2<br>'+esc(after)+'</th><th>Что изменилось</th></tr></thead><tbody>'+"".join(rows)+'</tbody></table></body></html>'
