import unittest
from pathlib import Path
from comparison import compare_documents, parse_full_document, word_diff, _display
from comparison_report import render_comparison

class CompleteComparisonTests(unittest.TestCase):
    def result(self,a,b):
        return compare_documents({'before':[{'name':'Документ 1.md','text':a}],'after':[{'name':'Документ 2.md','text':b}]})
    def coverage(self,result,a,b):
        for side,text in [('before',a),('after',b)]:
            original=parse_full_document({'name':f'Документ {1 if side=="before" else 2}.md','text':text},side,0)['clauses']
            actual=[r[side] for r in result['rows'] if r[side]]
            self.assertEqual(sorted(c['id'] for c in original), sorted(c['id'] for c in actual))
            self.assertEqual(len(actual),len({c['id'] for c in actual}))
        self.assertEqual([r['before']['order'] for r in result['rows'] if r['before']],sorted(r['before']['order'] for r in result['rows'] if r['before']))
        for row in result['rows']:
            for side,parts in [('before','beforeParts'),('after','afterParts')]:
                self.assertEqual(''.join(p['text'] for p in row[parts]),row[side]['text'] if row[side] else '')
    def test_identical_all_content(self):
        a='УТВЕРЖДЕНО\nСоветом\n\n**1\\. Название**\n\n1.1. Любая запись.\n\nа) Подпункт.\n\n- элемент\n\nТермин — определение.\n\n**Оглавление**\n\n1. Название 1\n\nПриложение А'
        result=self.result(a,a); self.coverage(result,a,a)
        self.assertEqual(result['stats']['unchanged'],result['stats']['total'])
        self.assertGreaterEqual(result['stats']['total'],9)
    def test_same_ref_entire_rewrite(self):
        r=self.result('1.1. Старая обязанность.','1.1. Совершенно иное полномочие.')
        self.assertEqual(r['stats']['changed'],1);self.assertEqual(r['stats']['total'],1)
    def test_insert_delete_order(self):
        a='1. Альфа\n2. Бета\n3. Гамма';b='1. Альфа\n1.1. Новое\n3. Гамма'
        r=self.result(a,b);self.coverage(r,a,b)
        self.assertEqual([row['status'] for row in r['rows']],['unchanged','removed','added','unchanged'])
    def test_renumbering(self):
        r=self.result('1.1. Готовит отчет.','2.4. Готовит отчет.')
        self.assertEqual(r['stats']['moved'],1)
        self.assertIn('1.1 → 2.4',r['rows'][0]['explanation'])
    def test_repeated_clause_not_reused(self):
        a='1.1. Одинаковая функция.\n1.2. Одинаковая функция.';b='1.1. Одинаковая функция.'
        r=self.result(a,b);self.coverage(r,a,b)
        self.assertEqual(r['stats']['unchanged'],1);self.assertEqual(r['stats']['removed'],1)
    def test_repeated_clauses_same_ref_preference(self):
        a='1.1. Функция.\n1.2. Функция.';b='1.2. Функция.\n1.1. Функция.'
        r=self.result(a,b);self.coverage(r,a,b)
        self.assertTrue(all(x['before']['ref']==x['after']['ref'] for x in r['rows']))
    def test_changed_modality(self):
        r=self.result('9.15. Проверка осуществляется ежегодно.','9.15. Проверка может осуществляться ежегодно.')
        self.assertEqual(r['stats']['changed'],1)
        self.assertIn('возможности',r['rows'][0]['explanation'])
        self.assertTrue(any('может' in p['text'] for p in r['rows'][0]['afterParts'] if p['kind']=='added'))
    def test_negation(self):
        r=self.result('1.1. Аудитор вправе участвовать.','1.1. Аудитор не вправе участвовать.')
        self.assertIn('запретительная',r['rows'][0]['explanation'])
    def test_diff_reconstruction(self):
        for a,b in [('А (Б), 12.3\n  ёж!','А (В), 13.3\n ёж?'),('','новое'),('старое',''),('ёж ЁЖ','еж ЁЖ')]:
            bp,ap=word_diff(a,b);self.assertEqual(''.join(p['text'] for p in bp),a);self.assertEqual(''.join(p['text'] for p in ap),b)
    def test_no_keyword_filter(self):
        a='Сведения\n\nX\n\n14. Термины\n\nБВА — блок\n\nОглавление\n\n14. Термины 30'
        r=self.result(a,a);self.coverage(r,a,b=a);self.assertEqual(r['stats']['total'],6)
    def test_multiple_named_documents(self):
        p={'before':[{'name':'Аудит редакция 8.md','text':'1.1. Аудит.'},{'name':'Кадры редакция 8.md','text':'1.1. Кадры.'}],'after':[{'name':'Кадры редакция 9.md','text':'1.1. Кадры.'},{'name':'Аудит редакция 9.md','text':'1.1. Аудит.'}]}
        r=compare_documents(p);self.assertEqual(r['stats']['unchanged'],2)
        self.assertTrue(all(row['before']['text']==row['after']['text'] for row in r['rows']))
    def test_corpus_complete_once_and_source_text(self):
        root=Path(__file__).parent/'data'; files=[root/'audit-before.md',root/'audit-after.md']
        if not all(p.exists() for p in files):self.skipTest('Real audit data unavailable')
        a,b=[p.read_text(encoding='utf-8') for p in files];r=self.result(a,b);self.coverage(r,a,b)
        for side,source in [('before',a),('after',b)]:
            clauses=parse_full_document({'name':'x','text':source},side,0)['clauses']
            compact=lambda text:''.join(text.split())
            self.assertEqual(compact(''.join(c['text'] for c in clauses)),compact(_display(source)))
        target=[row for row in r['rows'] if row['before'] and row['before']['ref']=='9.15' and not row['before']['toc']]
        self.assertTrue(target);self.assertEqual(target[0]['status'],'changed')
    def test_toc_does_not_hide_following_body(self):
        a='Оглавление\n\n1. Общие .... 3\n\n1. Общие\n\n1.1. Проверка.'
        b='1. Общие\n\n1.1. Проверка.'
        r=self.result(a,b); self.coverage(r,a,b)
        target=next(row for row in r['rows'] if row['before'] and row['before']['ref']=='1.1')
        self.assertEqual(target['status'],'unchanged')
    def test_report_preserves_diff_and_escapes_input(self):
        r=self.result('1.1. <script>проверка</script>','1.1. <script>новая проверка</script>')
        page=render_comparison({'comparison':r})
        self.assertNotIn('<script>',page)
        self.assertIn('&lt;script&gt;',page)
        self.assertIn('<ins>новая ',page)
        self.assertIn('Документ 1.md',page)
        self.assertEqual(page.count('<tr>'),len(r['rows'])+1)
    def test_version_and_date_are_aligned(self):
        a='от «25» июня 2021 года\n\nПоложение\n\n(редакция No8)'
        b='от «23» декабря 2022 года\n\nПоложение\n\n(редакция No9)'
        r=self.result(a,b); self.coverage(r,a,b)
        self.assertEqual(r['stats']['changed'],2)
        self.assertEqual(r['stats']['total'],3)

    def test_headings_only_api_comparison(self):
        import backend
        result=backend.analyze({'before':[{'name':'1.md','text':'# Название'}],'after':[{'name':'2.md','text':'# Новое название'}]})
        self.assertGreaterEqual(result['comparison']['stats']['total'],1)

if __name__=='__main__':unittest.main()
