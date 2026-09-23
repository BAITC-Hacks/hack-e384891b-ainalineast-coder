"""Full ordered one-to-one document comparison. All nonempty paragraphs retained."""
from collections import defaultdict
import difflib
import hashlib
import re

def _display(text):
    return re.sub(r'\\([.\-])',r'\1',text).replace('**','').strip()

def _key(text):
    return re.sub(r'\s+',' ',text).strip().casefold()

def parse_full_document(item,side,index):
    raw=item['text']; name=str(item.get('name') or f'{side}-{index+1}.txt')[:250]
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
            marked=bool(re.match(r'^(?:#{1,6}\s|\d+(?:\.\d+)*[.)]?\s|[а-яa-z][.)]\s|[-–•]\s)',chunk,re.I))
            if marked or raw_line.strip().startswith('**'): flush()
            if not buffer: start=lineno
            buffer.append(chunk)
    flush()
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
    chunks=[re.sub(r'\s+',' ',p['text']).strip() for p in parts if p['kind']==kind and p['text'].strip()]
    return '; '.join('«'+s[:120]+('…' if len(s)>120 else '')+'»' for s in chunks[:3])

def _row(a,b):
    bp,ap=word_diff(a['text'] if a else '',b['text'] if b else '')
    if a is None:status='added'; explanation='Добавлен пункт: в документе 1 соответствие не найдено.'
    elif b is None:status='removed'; explanation='Пункт отсутствует в документе 2: соответствие не найдено.'
    else:
        renumbered=_numeric_ref(a) and _numeric_ref(b) and a['ref']!=b['ref']
        status='moved' if renumbered and a['body']==b['body'] else 'unchanged' if a['text']==b['text'] else 'changed'
        explanation='Текст без изменений.' if status=='unchanged' else ''
        if renumbered:explanation=f"Изменена нумерация: {a['ref']} → {b['ref']}."
        if status=='moved':explanation+=' Формулировка сохранена.'
        elif status=='changed':
            removed=_snippet(bp,'removed');added=_snippet(ap,'added')
            edits=(f' Удалено: {removed}.' if removed else '')+(f' Добавлено: {added}.' if added else '')
            explanation+=edits or ' Изменены пробелы или оформление.'
            old_neg=bool(re.search(r'\bне\s+(?:долж|вправе|име|допуска)|запрещ',a['body'],re.I))
            new_neg=bool(re.search(r'\bне\s+(?:долж|вправе|име|допуска)|запрещ',b['body'],re.I))
            if old_neg!=new_neg:explanation+=' Изменена запретительная формулировка; проверьте смысл.'
            if bool(re.search(r'\b(?:может|могут|вправе)\b',a['body'],re.I))!=bool(re.search(r'\b(?:может|могут|вправе)\b',b['body'],re.I)):explanation+=' Изменена формулировка возможности или полномочия.'
    return dict(id='',before=a,after=b,status=status,explanation=explanation.strip(),beforeParts=bp,afterParts=ap)

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
    name=re.sub(r'\.(?:docx?|pdf|md|txt)$','',name,flags=re.I)
    name=re.sub(r'\.(?:docx?|pdf)$','',name,flags=re.I)
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
