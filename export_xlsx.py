"""Portable XLSX comparison export using standard OOXML and the Python stdlib."""
from io import BytesIO
import math
import re
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED

MISSING="Данный пункт в документе отсутствует."
LABELS={"unchanged":"Без изменений","changed":"Изменён","added":"Добавлен","removed":"Удалён","moved":"Перенумерован / перенесён"}
NS="http://schemas.openxmlformats.org/spreadsheetml/2006/main"

def _xml(value):
    return escape(re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "\ufffd", str(value or "")))

def _segments(clause,parts,multi):
    if clause is None:return [{"text":MISSING,"kind":"equal"}]
    prefix=(str(clause.get("document",""))+"\n") if multi else ""
    prefix+=str(clause.get("ref",""))+"\n"
    return [{"text":prefix,"kind":"equal"}]+(parts or [{"text":clause["text"],"kind":"equal"}])

def _chunks(parts,limit=900,width=44):
    """Keep continuation cells below Excel's visible row-height limit."""
    out=[]; current=[]; size=0; line=1; column=0
    for part in parts:
        kind=part.get("kind","equal")
        for character in str(part.get("text","")):
            advance=2 if character in "MWЖШЩЮФЫ" else 1
            nextline=line+(character=="\n" or column+advance>width)
            if current and (size>=limit or nextline>18):
                out.append(current);current=[];size=0;line=1;column=0
            if current and current[-1]["kind"]==kind:current[-1]["text"]+=character
            else:current.append({"text":character,"kind":kind})
            size+=1
            if character=="\n":line+=1;column=0
            else:
                if column+advance>width:line+=1;column=0
                column+=advance
    if current:out.append(current)
    return out or [[]]

def _text(parts):return "".join(p["text"] for p in parts)

def _height(parts,width):
    lines=sum(max(1,math.ceil(sum(2 if c in "MWЖШЩЮФЫ" else 1 for c in line)/width)) for line in _text(parts).split("\n"))
    return max(34,min(405,lines*17+14))

def _cell(address,parts,style=3):
    runs=[]
    for part in parts:
        kind=part.get("kind"); props='<rFont val="Roboto"/><sz val="'+("19" if style==0 else "12")+'"/>'
        if kind in ("removed","added"):
            props+='<b/><color rgb="FFB42335"/>'+('<strike/>' if kind=="removed" else '')
        elif style==2:
            props+='<b/><color rgb="FFFFFFFF"/>'
        elif style==0:props+='<b/><color rgb="FF0C457F"/>'
        else:props+='<color rgb="FF243E5D"/>'
        runs.append('<r><rPr>'+props+'</rPr><t xml:space="preserve">'+_xml(part["text"])+'</t></r>')
    return '<c r="'+address+'" s="'+str(style)+'" t="inlineStr"><is>'+"".join(runs)+'</is></c>'

def export_xlsx(analysis):
    data=analysis["comparison"]; docs=data["documents"]
    names={s:" + ".join(d["name"] for d in docs[s]) for s in ("before","after")}
    rows=[]
    def plain(text):return [{"text":str(text),"kind":"equal"}]
    rows.append('<row r="1" ht="34" customHeight="1">'+_cell("A1",plain("Versa — сравнительная таблица"),0)+'</row>')
    rows.append('<row r="2" ht="35" customHeight="1">'+_cell("A2",plain("Красный жирный — дополнение; красный зачёркнутый — удаление. Длинные пункты продолжаются следующей строкой."),1)+'</row>')
    header=[plain("Документ 1\n"+names["before"]),plain("Документ 2\n"+names["after"]),plain("Что изменилось")]
    rows.append('<row r="3" ht="'+str(max(72,*[_height(p,55) for p in header]))+'" customHeight="1">'+"".join(_cell(c+"3",p,2) for c,p in zip("ABC",header))+'</row>')
    rn=4
    for row in data["rows"]:
        cells=[_segments(row.get("before"),row.get("beforeParts"),len(docs["before"])>1),
               _segments(row.get("after"),row.get("afterParts"),len(docs["after"])>1),
               plain(LABELS.get(row["status"],row["status"])+". "+row["explanation"])]
        chunks=[_chunks(p,width=w) for p,w in zip(cells,(62,62,40))]
        for part in range(max(map(len,chunks))):
            values=[chunk[part] if part<len(chunk) else [] for chunk in chunks]
            height=max(_height(values[0],62),_height(values[1],62),_height(values[2],40))
            rows.append('<row r="'+str(rn)+'" ht="'+str(height)+'" customHeight="1">'+"".join(_cell(c+str(rn),p) for c,p in zip("ABC",values))+'</row>')
            rn+=1
    sheet='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="'+NS+'"><dimension ref="A1:C'+str(rn-1)+'"/><sheetViews><sheetView workbookViewId="0" showGridLines="0"><pane ySplit="3" topLeftCell="A4" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><sheetFormatPr defaultRowHeight="36"/><cols><col min="1" max="2" width="76" customWidth="1"/><col min="3" max="3" width="52" customWidth="1"/></cols><sheetData>'+"".join(rows)+'</sheetData><autoFilter ref="A3:C'+str(rn-1)+'"/><mergeCells count="2"><mergeCell ref="A1:C1"/><mergeCell ref="A2:C2"/></mergeCells><printOptions horizontalCentered="1"/><pageMargins left="0.3" right="0.3" top="0.4" bottom="0.4" header="0.2" footer="0.2"/><pageSetup paperSize="8" orientation="landscape" fitToWidth="1" fitToHeight="0"/></worksheet>'
    styles='<?xml version="1.0" encoding="UTF-8"?><styleSheet xmlns="'+NS+'"><fonts count="1"><font><sz val="12"/><name val="Roboto"/><color rgb="FF243E5D"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF0C457F"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="2"><border/><border><left style="thin"><color rgb="FFD4E1EC"/></left><right style="thin"><color rgb="FFD4E1EC"/></right><top style="thin"><color rgb="FFD4E1EC"/></top><bottom style="thin"><color rgb="FFD4E1EC"/></bottom></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="4"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf><xf numFmtId="0" fontId="0" fillId="2" borderId="1" xfId="0" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf><xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>'
    workbook='<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="'+NS+'" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Сравнение" sheetId="1" r:id="rId1"/></sheets><definedNames><definedName name="_xlnm.Print_Titles" localSheetId="0">\'Сравнение\'!$3:$3</definedName></definedNames></workbook>'
    relns='http://schemas.openxmlformats.org/package/2006/relationships'
    types='http://schemas.openxmlformats.org/package/2006/content-types'
    contents='<?xml version="1.0"?><Types xmlns="'+types+'"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>'
    rootrels='<?xml version="1.0"?><Relationships xmlns="'+relns+'"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'
    rels='<?xml version="1.0"?><Relationships xmlns="'+relns+'"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>'
    output=BytesIO()
    with ZipFile(output,"w",ZIP_DEFLATED) as z:
        for name,content in {"[Content_Types].xml":contents,"_rels/.rels":rootrels,"xl/workbook.xml":workbook,"xl/_rels/workbook.xml.rels":rels,"xl/styles.xml":styles,"xl/worksheets/sheet1.xml":sheet}.items():z.writestr(name,content.encode("utf-8"))
    return output.getvalue()
