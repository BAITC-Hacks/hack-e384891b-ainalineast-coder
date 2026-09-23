"""Validated binary export dispatch; input documents are data only."""
from export_xlsx import export_xlsx
FORMATS={"docx":"application/vnd.openxmlformats-officedocument.wordprocessingml.document",
         "xlsx":"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
         "pdf":"application/pdf"}
def validate_analysis(analysis):
    if not isinstance(analysis,dict) or not isinstance(analysis.get("comparison"),dict):
        raise ValueError("Отсутствует сравнительная таблица")
    c=analysis["comparison"]; documents=c.get("documents",{}); rows=c.get("rows")
    for side in ("before","after"):
        docs=documents.get(side) if isinstance(documents,dict) else None
        if not isinstance(docs,list) or not 1<=len(docs)<=30 or any(not isinstance(d,dict) or not isinstance(d.get("name"),str) or len(d["name"])>1000 for d in docs):
            raise ValueError("Неверные названия документов")
    if not isinstance(rows,list) or not 1<=len(rows)<=6000:raise ValueError("Для экспорта требуется от 1 до 6000 строк")
    for row in rows:
        if not isinstance(row,dict) or row.get("status") not in {"unchanged","changed","added","removed","moved"} or not isinstance(row.get("explanation"),str):
            raise ValueError("Неверная строка сравнительной таблицы")
        if row.get("before") is None and row.get("after") is None:raise ValueError("Пустая строка таблицы")
        for side in ("before","after"):
            clause=row.get(side);parts=row.get(side+"Parts",[])
            if clause is not None and (not isinstance(clause,dict) or not isinstance(clause.get("text"),str) or len(clause["text"])>600000):
                raise ValueError("Неверный текст пункта")
            if not isinstance(parts,list) or any(not isinstance(p,dict) or not isinstance(p.get("text"),str) or p.get("kind") not in {"equal","removed" if side=="before" else "added"} for p in parts):
                raise ValueError("Неверное выделение изменений")
            if parts and "".join(p["text"] for p in parts)!=(clause or {}).get("text",""):
                raise ValueError("Выделение не соответствует тексту пункта")
    return analysis

def export_document(analysis,extension):
    if extension not in FORMATS:raise ValueError("Формат экспорта не поддерживается")
    validate_analysis(analysis)
    if extension=="xlsx":return export_xlsx(analysis)
    from export_documents import export_docx,export_pdf
    return (export_docx if extension=="docx" else export_pdf)(analysis)
