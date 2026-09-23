"""Formal, source-grounded conclusions for document comparison."""
from collections import Counter
from html import escape
from legal_text import citation, display_name

LABELS = {"unchanged":"Без изменений","changed":"Изменение редакции","added":"Дополнение","removed":"Исключение","moved":"Изменение нумерации"}
MISSING = "Данный пункт в документе отсутствует."

def build_conclusion(analysis):
    comparison=analysis.get("comparison",{})
    rows=comparison.get("rows",[])
    counts=Counter(row["status"] for row in rows)
    documents=comparison.get("documents",{})
    names={side:"; ".join(display_name(d.get("name")) for d in documents.get(side,[])) or ("Документ 1" if side=="before" else "Документ 2") for side in ("before","after")}
    findings=analysis.get("findings",[])
    risks=Counter(f.get("type") for f in findings)
    changed=sum(counts[k] for k in ("changed","added","removed","moved"))
    result=[
        f"Сопоставлено позиций: {len(rows)}. Формулировка сохранена без изменений в {counts['unchanged']} позициях. Изменение редакции установлено в {counts['changed']} позициях; дополнения — в {counts['added']}; отсутствие соответствующего положения в новой редакции — в {counts['removed']}; изменение нумерации при сохранении содержания — в {counts['moved']}.",
        ("Представленная новая редакция содержит изменения, дополнения и (или) изменения структурного расположения положений. Содержание каждого установленного расхождения, исходная формулировка и формулировка новой редакции приведены в перечне изменений ниже. При согласовании документа необходимо рассмотреть каждую из указанных позиций с учётом закреплённой функции, ответственного субъекта и условий её осуществления." if changed else
         "Различия в формулировках и нумерации сопоставленных положений не установлены. По представленному тексту основания для составления перечня изменений отсутствуют."),
        (f"По распределению функций и полномочий сформировано замечаний: {len(findings)}. В их числе: отсутствие установленного соответствия функции в новой редакции — {risks['loss']}; признаки пересечения полномочий — {risks['duplicate']}; признаки несогласованности исполнения, контроля или независимости — {risks['conflict']}; иные изменения закрепления полномочий и структуры — {risks['change']}. Каждое замечание сопровождается ссылками на исходные положения и рекомендацией по его рассмотрению." if findings else
         "Отдельные замечания по распределению функций и полномочий по результатам выполненного сопоставления не сформированы. Этот результат относится к предоставленному тексту и не заменяет проверку фактического распределения обязанностей.")
    ]
    recommendations=[
        "Рассмотреть перечень изменений последовательно по каждому положению. Для изменения формулировки установить, затрагивает ли оно содержание обязанности, объём полномочия, условия исполнения, срок, порядок подчинённости либо ответственность. Отдельно зафиксировать изменения, имеющие исключительно редакционный характер.",
        "По каждому исключённому или несопоставленному положению определить дальнейшее закрепление предусмотренной функции: сохранение в иной формулировке, передача другому подразделению либо прекращение на основании решения уполномоченного органа. При передаче указать принимающее подразделение и точное положение документа, устанавливающее его полномочие.",
        "По дополнениям определить ответственного исполнителя, пределы его полномочий и порядок взаимодействия с другими подразделениями. При признаках пересечения полномочий разграничить основное исполнение, участие соисполнителей и контроль. При совмещении исполнения и проверки установить достаточные условия независимости контроля.",
        "Результаты рассмотрения закрепить в протоколе согласования или ином принятом в организации документе. Для каждого замечания указать решение, обоснование, ответственное лицо и при необходимости срок внесения уточнений. Окончательную редакцию направить на утверждение после урегулирования подтверждённых расхождений."
    ] if changed or findings else [
        "Зафиксировать результат сопоставления в материалах согласования. Перед утверждением проверить полноту представленных документов, приложений и реквизитов, а также полномочия органа, принимающего соответствующее решение."
    ]
    return {
        "title":"Заключение по итогам сравнения",
        "introduction":[
            f"Предметом рассмотрения является сопоставление документа 1 «{names['before']}» и документа 2 «{names['after']}» в целях выявления изменений положений, полноты закрепления функций и согласованности распределения полномочий.",
            "Сопоставление выполнено по представленному тексту обеих редакций. Рассмотрены формулировки положений, их нумерация, дополнения и исключения, а также указания на подразделения и ответственных субъектов. Ссылки приведены по действительной структуре источника; ненумерованные абзацы обозначены отдельно.",
            "Основанием каждого вывода служат воспроизведённые положения документов. Цитаты приведены полностью. Термины «дополнение», «исключение» и «изменение редакции» характеризуют результат сопоставления представленных документов."
        ],
        "result":result,
        "recommendations":recommendations,
        "limitations":[
            "Настоящее заключение ограничено содержанием предоставленных документов. Выявленное текстовое расхождение само по себе не устанавливает нарушение законодательства, недействительность положения или фактическое неисполнение функции. Правовая оценка соответствия обязательным требованиям проводится с учётом применимых норм и дополнительных обстоятельств.",
            "Отсутствие текстового соответствия в новой редакции требует проверки иных внутренних документов и решений уполномоченных органов. Сведения о подразделении в одной из редакций сами по себе не подтверждают его юридическое создание, реорганизацию или ликвидацию.",
            "Окончательные выводы о допустимости изменений и утверждении редакции принимаются уполномоченным лицом после рассмотрения замечаний и проверки полноты исходных материалов."
        ]
    }

def _paragraphs(values):
    return "".join("<p>"+escape(str(text))+"</p>" for text in values)

def _source(clause):
    if not clause:return "<p>"+MISSING+"</p>"
    return "<p class='source'>"+escape(citation(clause))+" документа «"+escape(display_name(clause.get("document")))+"»</p><blockquote>"+escape(clause["text"])+"</blockquote>"

def render_conclusion(analysis):
    report=build_conclusion(analysis)
    rows=analysis.get("comparison",{}).get("rows",[])
    changed=[row for row in rows if row["status"]!="unchanged"]
    findings=analysis.get("findings",[])
    notes=[]
    for index,f in enumerate(findings,1):
        explanation=str(f.get("explanation",""))
        if f.get("evidence"):explanation=explanation.split("\nОснования сопоставления:\n")[0]
        notes.append("<article><h3>"+str(index)+". "+escape(f["title"])+"</h3><p>"+escape(explanation)+"</p>"+"".join(_source(c) for c in f.get("evidence",[]))+"<p class='recommendation'><b>Рекомендуемое действие.</b> "+escape(f.get("recommendation",""))+"</p><p class='source'>Статус рассмотрения: требует рассмотрения.</p></article>")
    items=[]
    for index,row in enumerate(changed,1):
        items.append("<article data-comparison-id='"+escape(str(row["id"]),quote=True)+"'><h3>"+str(index)+". "+escape(LABELS[row["status"]])+" — "+escape(citation(row.get("after") or row.get("before")))+"</h3><p>"+escape(row.get("explanation",""))+"</p><div class='versions'><section><h4>Документ 1</h4>"+_source(row.get("before"))+"</section><section><h4>Документ 2</h4>"+_source(row.get("after"))+"</section></div></article>")
    from comparison_report import render_comparison
    comparison=render_comparison(analysis)
    table=comparison[comparison.index("<table"):comparison.index("</table>")+8]
    body="<header><small>VERSA · ЭКСПЕРТИЗА РЕДАКЦИЙ</small><h1>"+escape(report["title"])+"</h1><p>Дата формирования: "+escape(str(analysis.get("generatedAt","")))+"</p></header>"
    body+="<h2>1. Предмет и основания сопоставления</h2>"+_paragraphs(report["introduction"])
    body+="<h2>2. Основные выводы</h2>"+_paragraphs(report["result"])
    body+="<h2>3. Замечания о функциях и полномочиях</h2>"+("".join(notes) or "<p>Отдельные замечания не сформированы.</p>")
    body+="<h2>4. Перечень изменений и дополнений по пунктам</h2>"+("".join(items) or "<p>Изменения не установлены.</p>")
    body+="<h2>5. Рекомендации по согласованию редакции</h2>"+_paragraphs(report["recommendations"])
    body+="<h2>6. Пределы заключения</h2>"+_paragraphs(report["limitations"])
    body+="<section class='appendix'><h2>Приложение. Полная сравнительная таблица</h2>"+table+"</section>"
    css="""body{margin:50px auto;max-width:1250px;padding:0 35px;font:17px/1.75 Arial,sans-serif;color:#243e5d}header{border-bottom:3px solid #147cc0;padding-bottom:25px}header small{color:#127db4;font-weight:bold;letter-spacing:2px}h1{font-size:32px;color:#0c457f;line-height:1.35}h2{font-size:25px;color:#0c457f;margin:36px 0 18px}h3{font-size:19px;color:#0c457f;line-height:1.6}article{border-bottom:1px solid #d2e4ef;padding:18px 0 28px;overflow-wrap:anywhere}p{white-space:pre-line}blockquote{white-space:pre-wrap;padding:15px 20px;margin:12px 0;background:#f1f7fc;border-left:3px solid #1483c5}.source{font-size:14px;font-weight:bold;color:#456e8b}.recommendation{background:#e7f3fb;padding:18px;border-radius:10px}.versions{display:grid;grid-template-columns:1fr 1fr;gap:22px}.versions section{min-width:0}table{width:100%;border-collapse:collapse;table-layout:fixed}th,td{border:1px solid #bdd7e9;padding:18px;vertical-align:top;overflow-wrap:anywhere}th{background:#e7f3fb;color:#0c457f}td{white-space:pre-wrap}del,ins{color:#b42335;font-weight:bold}ins{text-decoration:none}.appendix{margin-top:55px}@page{size:A3 landscape;margin:15mm}@media print{body{max-width:none;margin:0;padding:0;font-size:11pt}.appendix{break-before:page}h2,h3{break-after:avoid}thead{display:table-header-group}.versions{display:block}}@media(max-width:700px){body{padding:0 18px}.versions{grid-template-columns:1fr}}"""
    return "<!doctype html><html lang='ru'><meta charset='utf-8'><title>Versa — заключение по итогам сравнения</title><style>"+css+"</style><body>"+body+"</body></html>"
