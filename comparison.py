"""Full ordered one-to-one document comparison. All nonempty paragraphs retained."""
from collections import defaultdict
import difflib
import hashlib
import re
from legal_text import display_name, citation, add_citations

def _display(text):
    return re.sub(r'\\([.\-])',r'\1',text).replace('**','').strip()

def _key(text):
    return re.sub(r'\s+',' ',text).strip().casefold()

def parse_full_document(item,side,index):
    raw=item['text']; name=display_name(item.get('name') or f'Документ {index+1}')
    docid=f'{side}-{index+1}-{hashlib.sha256((name+raw).encode()).hexdigest()[:8]}'
    clauses=[]; parent=''; section=''; buffer=[]; start=1; lists=defaultdict(int)
    def flush():
        nonlocal parent,section,buffer
        if not buffer: return
        text='\n'.join(buffer)
        number=re.match(r'^(\d+(?:\.\d+)*)(?:[.)]\s*|\s+)(.+)',text,re.S)
        letter=re.match(r'^([а-яa-z])[.)]\s+(.+)',text,re.I|re.S)
        kind='paragraph'; body=text
        toc=bool(re.search(r'(?:\.{2,}|\t)\s*\d+\s*$',text))
        if number:
            ref,body=number.groups(); parent=ref
            if '.' not in ref and len(body)<180: kind='heading'; section=text
        elif letter and parent: ref=parent+'.'+letter.group(1).lower(); body=letter.group(2)
        elif re.match(r'^[-–•]\s+',text):
            lists[parent]+=1
            ref=f'{parent} · список {lists[parent]}'; body=re.sub(r'^[-–•]\s+','',text)
        else:
            ref=f'Фрагмент {len(clauses)+1}'
            if text.startswith('#') or _key(text) in ('оглавление','содержание','приложения'): kind='heading'; section=text
        clauses.append(dict(id=f'{docid}-full-{len(clauses)+1}',docId=docid,document=name,side=side,ref=ref,text=text,body=body,kind=kind,section=section,line=start,order=len(clauses),sourceOrder=len(clauses),toc=toc))
        buffer=[]
    for lineno,raw_line in enumerate(raw.splitlines(),1):
        line=_display(raw_line)
        if not line: flush(); continue
        chunks=re.split(r'(?<=[.;!?])\s+(?=\d{1,2}(?:\.\d{1,3}){1,3}\.\s*[А-ЯA-ZЁ])',line)
        for chunk in chunks:
            marked=bool(re.match(r'^(?:(?:раздел|глава|статья)\s+|#{1,6}\s|\d+(?:\.\d+)*[.)]?\s|[а-яa-z][.)]\s|[-–•]\s)',chunk,re.I))
            if marked or raw_line.strip().startswith('**'): flush()
            if not buffer: start=lineno
            buffer.append(chunk)
    flush()
    add_citations(clauses,raw)
    return dict(id=docid,name=name,clauses=clauses)

def word_diff(before,after):
    a=re.findall(r'\w+|\s+|[^\w\s]',before); b=re.findall(r'\w+|\s+|[^\w\s]',after)
    left=[]; right=[]
    def append(parts,text,kind):
        if not text:return
        if parts and parts[-1]['kind']==kind:parts[-1]['text']+=text
        else:parts.append(dict(text=text,kind=kind))
    for tag,i,j,k,l in difflib.SequenceMatcher(None,a,b,autojunk=False).get_opcodes():
        append(left,''.join(a[i:j]),'equal' if tag=='equal' else 'removed')
        append(right,''.join(b[k:l]),'equal' if tag=='equal' else 'added')
    return left,right

def _numeric_ref(c):
    return bool(re.match(r'^\d+(?:\.\d+)*(?:\.[а-яa-z])?$',c['ref']))

def _match_clauses(left,right):
    matches={};used=set()
    def pair(i,j):matches[i]=j;used.add(j)
    ga=defaultdict(list);gb=defaultdict(list)
    for i,c in enumerate(left):ga[(_key(c['body']),c['toc'])].append(i)
    for j,c in enumerate(right):gb[(_key(c['body']),c['toc'])].append(j)
    for key,ii in ga.items():
        available=list(gb.get(key,[]))
        for i in ii:
            if not available:break
            same=[j for j in available if left[i]['ref']==right[j]['ref']]
            j=min(same or available,key=lambda j:abs(i/max(1,len(left))-j/max(1,len(right))))
            pair(i,j);available.remove(j)
    for i,a in enumerate(left):
        if i in matches or not _numeric_ref(a):continue
        candidates=[j for j,b in enumerate(right) if j not in used and a['ref']==b['ref'] and a['toc']==b['toc']]
        if candidates:pair(i,min(candidates,key=lambda j:abs(i-j)))
    proposals=[]; wb=[set(re.findall(r'\w+',_key(c['body']))) for c in right]
    for i,a in enumerate(left):
        if i in matches:continue
        wa=set(re.findall(r'\w+',_key(a['body']))); scored=[]
        for j,b in enumerate(right):
            if j in used or a['toc']!=b['toc']:continue
            overlap=len(wa&wb[j])/max(1,len(wa|wb[j]))
            if overlap>=.25:scored.append((overlap,j))
        for overlap,j in sorted(scored,reverse=True)[:4]:
            score=difflib.SequenceMatcher(None,_key(a['body']),_key(right[j]['body']),autojunk=False).ratio()
            nearby=abs(i/max(1,len(left))-j/max(1,len(right)))<=.08
            unnumbered=not _numeric_ref(a) and not _numeric_ref(right[j])
            if (score>=.72 and overlap>=.3) or (unnumbered and nearby and score>=.6 and overlap>=.25):proposals.append((score,-abs(i-j),i,j))
    for score,distance,i,j in sorted(proposals,reverse=True):
        if i not in matches and j not in used:pair(i,j)
    return matches

def _snippet(parts,kind):
    chunks=[p['text'].strip() for p in parts if p['kind']==kind and p['text'].strip()]
    return '; '.join('«'+text+'»' for text in chunks)

def _source(clause):
    return citation(clause) + ' документа «' + display_name(clause['document']) + '»'

def _changes(before,after):
    old=re.findall(r'\w+|\s+|[^\w\s]',before)
    new=re.findall(r'\w+|\s+|[^\w\s]',after)
    return [dict(type=tag,before=''.join(old[i:j]),after=''.join(new[k:l]))
            for tag,i,j,k,l in difflib.SequenceMatcher(None,old,new,autojunk=False).get_opcodes()
            if tag!='equal']

def _row(a,b):
    bp,ap=word_diff(a['text'] if a else '',b['text'] if b else '')
    changes=_changes(a['text'] if a else '',b['text'] if b else '')
    if a is None:
        status='added'
        explanation=('Дополнение новой редакции. В документе 1 соответствующий структурный элемент не установлен. '
                     'В документ 2 включён следующий структурный элемент: '+_source(b)+'. '
                     'Содержание дополнения: «'+b['text']+'». '
                     'Вывод относится к представленным документам и требует проверки при наличии иных документов, закрепляющих указанное положение.')
    elif b is None:
        status='removed'
        explanation=('В новой редакции соответствующий структурный элемент не установлен. '
                     'В документе 1 содержится '+_source(a)+': «'+a['text']+'». '
                     'В документе 2 текстовое соответствие не найдено. Необходимо установить, исключено ли положение '
                     'либо перенесено в иной документ; отсутствие соответствия само по себе не подтверждает прекращение предусмотренной функции.')
    else:
        renumbered=_numeric_ref(a) and _numeric_ref(b) and a['ref']!=b['ref']
        status='moved' if renumbered and a['body']==b['body'] else 'unchanged' if a['text']==b['text'] else 'changed'
        explanation=('Сопоставлены '+_source(a)+' и '+_source(b)+'. ')
        if status=='unchanged':
            explanation+='Формулировка сохранена без изменений.'
        if renumbered:
            explanation+=f"Изменена нумерация: {a['ref']} → {b['ref']}. "
        if status=='moved':
            explanation+='Содержание положения сохранено; изменение относится к его обозначению и расположению в структуре документа.'
        elif status=='changed':
            substantive=[change for change in changes if change['before'].strip() or change['after'].strip()]
            for number,change in enumerate(substantive,1):
                old=change['before'].strip(); new=change['after'].strip()
                explanation+=f"Изменение {number}. "
                if old and new:
                    explanation+='Фрагмент «'+old+'» заменён фрагментом «'+new+'». '
                elif old:
                    explanation+='Исключён фрагмент: «'+old+'». '
                elif new:
                    explanation+='Включён фрагмент: «'+new+'». '
            if not substantive:
                explanation+='Изменены пробелы или расположение текста; различий в словесной формулировке не установлено. '
            old_neg=bool(re.search(r'\bне\s+(?:долж|вправе|име|допуска)|запрещ',a['body'],re.I))
            new_neg=bool(re.search(r'\bне\s+(?:долж|вправе|име|допуска)|запрещ',b['body'],re.I))
            if old_neg!=new_neg:
                explanation+='Изменена запретительная формулировка; требуется определить, изменяется ли объём допустимых действий. '
            if bool(re.search(r'\b(?:может|могут|вправе)\b',a['body'],re.I))!=bool(re.search(r'\b(?:может|могут|вправе)\b',b['body'],re.I)):
                explanation+='Изменена формулировка возможности осуществления действия или предоставленного полномочия; необходимо уточнить условия её применения. '
    return dict(id='',before=a,after=b,status=status,explanation=explanation.strip(),changes=changes,beforeParts=bp,afterParts=ap)

def _pair_rows(left,right):
    matches=_match_clauses(left,right);anchors=defaultdict(list);pending=[]
    reverse={j:i for i,j in matches.items()}
    for j in range(len(right)):
        if j in reverse:anchors[reverse[j]].extend(pending);pending=[]
        else:pending.append(j)
    rows=[]
    for i,a in enumerate(left):
        rows.extend(_row(None,right[j]) for j in anchors.get(i,[]))
        rows.append(_row(a,right[matches[i]] if i in matches else None))
    rows.extend(_row(None,right[j]) for j in pending)
    return rows

def _name_key(name):
    name=display_name(name)
    return re.sub(r'(?:редакция|версия|revision|version|до|после|before|after)[ _\-№No\d]*','',name,flags=re.I).replace('_',' ').strip().casefold()

def compare_documents(payload):
    documents={side:[parse_full_document(item,side,i) for i,item in enumerate(payload[side])] for side in ('before','after')}
    left=documents['before'];right=documents['after'];pairings={};used=set()
    if len(left)==len(right)==1:pairings[0]=0;used={0}
    else:
        proposals=[]
        for i,a in enumerate(left):
            for j,b in enumerate(right):
                na=_name_key(a['name']);nb=_name_key(b['name']);score=difflib.SequenceMatcher(None,na,nb).ratio()
                if na and nb and score>=.65:proposals.append((score,-abs(i-j),i,j))
        for score,distance,i,j in sorted(proposals,reverse=True):
            if i not in pairings and j not in used:pairings[i]=j;used.add(j)
    rows=[]
    for i,doc in enumerate(left):rows.extend(_pair_rows(doc['clauses'],right[pairings[i]]['clauses'] if i in pairings else []))
    for j,doc in enumerate(right):
        if j not in used:rows.extend(_pair_rows([],doc['clauses']))
    for i,row in enumerate(rows):row['id']=f'C{i+1:04d}'
    stats={s:sum(r['status']==s for r in rows) for s in ('unchanged','changed','added','removed','moved')};stats['total']=len(rows)
    return dict(documents={s:[dict(id=d['id'],name=d['name']) for d in documents[s]] for s in documents},rows=rows,stats=stats)
