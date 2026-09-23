"""Source-grounded legal wording, complete changes and user-facing document names."""
import unittest
from backend import analyze, parse_document
from comparison import compare_documents, parse_full_document, _snippet
from legal_text import citation, display_name

def doc(text,name="Положение_редакция_8.docx.md",unit=""):
    return {"name":name,"text":text,"unit":unit}

class LegalPresentationTests(unittest.TestCase):
    def test_display_title_preserves_full_name_and_removes_only_transport_suffixes(self):
        name="Положение_"+"подробное_"*40+"редакция_8.docx.md"
        label=display_name(name)
        self.assertEqual(label,name.removesuffix(".docx.md").replace("_"," "))
        self.assertGreater(len(label),250)
        self.assertEqual(display_name("Документ.pdf.xlsx.TXT"),"Документ")
        self.assertEqual(display_name("Название.md внутри"),"Название.md внутри")

    def test_numeric_reference_does_not_invent_hierarchy(self):
        self.assertEqual(citation({"ref":"5.3.2"}),"пункт 5.3.2")
        self.assertEqual(citation({"ref":"5.3.2.а"}),"подпункт «а» пункта 5.3.2")
        self.assertEqual(citation({"ref":"Фрагмент 7"}),"ненумерованный абзац 7")
        source="5.3.2. Формирует заключение по результатам проверки."
        for parser in (parse_document,parse_full_document):
            clause=parser(doc(source),"before",0)["clauses"][0]
            self.assertEqual(clause["citation"],"пункт 5.3.2")

    def test_actual_section_and_article_are_retained_by_both_parsers(self):
        source="Раздел 2. Полномочия\nСтатья 4. Порядок контроля\n1. Формирует ежегодный отчет о результатах проверок."
        for parser in (parse_document,parse_full_document):
            clauses=parser(doc(source),"before",0)["clauses"]
            clause=next(c for c in clauses if c["ref"]=="1")
            self.assertEqual(clause["citation"],"пункт 1 статьи 4 «Порядок контроля» раздела 2 «Полномочия»")
        full=parse_full_document(doc(source),"before",0)["clauses"]
        self.assertEqual(len(full),3)
        self.assertEqual(full[0]["citation"],"раздел 2 «Полномочия»")
        self.assertEqual(full[1]["citation"],"статья 4 «Порядок контроля»")

    def test_numbered_real_heading_and_unknown_bold_clause(self):
        source="**9\\. Порядок планирования**\n9.15. Проверка осуществляется ежегодно."
        for parser in (parse_document,parse_full_document):
            clause=next(c for c in parser(doc(source),"before",0)["clauses"] if c["ref"]=="9.15")
            self.assertEqual(clause["citation"],"пункт 9.15 раздела 9 «Порядок планирования»")
        source="**1. Формирует отчет о результатах проверки.**"
        for parser in (parse_document,parse_full_document):
            clause=next(c for c in parser(doc(source),"before",0)["clauses"] if c["ref"]=="1")
            self.assertEqual(clause["citation"],"пункт 1")

    def test_complete_changes_are_not_truncated_or_limited_to_three(self):
        changes=[{"kind":"added","text":f"{i} "+("полный текст дополнения "*20)} for i in range(1,6)]
        rendered=_snippet(changes,"added")
        for change in changes:self.assertIn(change["text"].strip(),rendered)
        self.assertNotIn("…",rendered)
        before="1.1. Альфа один Бета два Гамма три Дельта четыре Эпсилон пять."
        after="1.1. Альфа первый Бета второй Гамма третий Дельта четвертый Эпсилон пятый."
        row=compare_documents({"before":[doc(before)],"after":[doc(after)]})["rows"][0]
        self.assertEqual(len(row["changes"]),5)
        self.assertIn("Изменение 5.",row["explanation"])
        for value in ("первый","второй","третий","четвертый","пятый"):
            self.assertIn(value,row["explanation"])
        self.assertNotIn("…",row["explanation"])

    def test_loss_title_and_reason_include_full_source_without_false_legal_breach(self):
        full="Формирует группы контроля качества с привлечением работников БВА, обладающих необходимой квалификацией для проведения проверки качества аудиторских процедур и подготовки полного заключения о результатах проведенной оценки."
        result=analyze({"before":[doc("5.6.2. "+full,unit="Методология")],
                        "after":[doc("1.1. Выполняет резервное копирование клиентских баз данных.",unit="ИТ")]})
        finding=next(f for f in result["findings"] if f["type"]=="loss")
        self.assertIn(full,finding["title"])
        self.assertIn(full,finding["explanation"])
        self.assertIn("пункт 5.6.2",finding["explanation"].lower())
        self.assertNotIn("…",finding["title"])
        self.assertIn("само по себе не подтверждает",finding["explanation"])
        self.assertTrue(all(not d["name"].endswith(".md") for d in result["documents"]))
        self.assertTrue(all("citation" in c and ".md" not in c["document"] for f in result["findings"] for c in f["evidence"]))

    def test_added_removed_explanations_quote_full_content(self):
        before="1.1. Архивирует технические материалы старого подразделения."
        after="9.9. Осуществляет независимый медицинский осмотр водителей."
        result=compare_documents({"before":[doc(before)],"after":[doc(after)]})
        removed=next(r for r in result["rows"] if r["status"]=="removed")
        added=next(r for r in result["rows"] if r["status"]=="added")
        self.assertIn(before,removed["explanation"])
        self.assertIn(after,added["explanation"])
        self.assertTrue(all(".md" not in row["explanation"] for row in result["rows"]))

    def test_section_heading_not_inferred_from_unrelated_numeric_prefix(self):
        source="1.1. Проверяет отчетность.\n9.15. Осуществляет анализ контрольных процедур."
        for parser in (parse_document,parse_full_document):
            clause=next(c for c in parser(doc(source),"before",0)["clauses"] if c["ref"]=="9.15")
            self.assertEqual(clause["citation"],"пункт 9.15")

if __name__=="__main__":
    unittest.main()
