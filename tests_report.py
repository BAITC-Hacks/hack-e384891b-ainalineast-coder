import unittest
from backend import analyze
from legal_report import build_conclusion, render_conclusion

class LegalConclusionTests(unittest.TestCase):
    def analyze(self,a,b):
        return analyze({"before":[{"name":"Исходное_положение.docx.md","text":a}],"after":[{"name":"Новое_положение.pdf","text":b}]})
    def test_conclusion_uses_actual_counts_and_clean_titles(self):
        a=self.analyze("1.1. Проверяет отчетность.","1.1. Проверяет отчетность.")
        report=build_conclusion(a)
        self.assertIn("Сопоставлено позиций: 1."," ".join(report["result"]))
        self.assertIn("Различия в формулировках и нумерации сопоставленных положений не установлены."," ".join(report["result"]))
        self.assertIn("Исходное положение"," ".join(report["introduction"]))
        self.assertNotIn(".md",str(report))
        self.assertNotIn(".pdf",str(report))
    def test_every_changed_position_and_entire_quotations_retained(self):
        before="\n".join(f"{i}.1. Проверяет отчетность старой группы {i}." for i in range(1,7))
        after="\n".join(f"{i}.1. Проверяет отчетность новой группы {i}." for i in range(1,7))
        a=self.analyze(before,after);page=render_conclusion(a)
        rows=[r for r in a["comparison"]["rows"] if r["status"]!="unchanged"]
        self.assertEqual(page.count("data-comparison-id="),len(rows))
        for row in rows:
            self.assertIn(row["before"]["text"],page)
            self.assertIn(row["after"]["text"],page)
            self.assertIn(row["explanation"],page)
    def test_html_escapes_untrusted_text_and_keeps_end_marker(self):
        long="Сведения "*600+"ПОСЛЕДНИЕ СЛОВА <script>alert(1)</script>"
        a=self.analyze("1.1. "+long,"1.1. Проверяет иной объект.")
        page=render_conclusion(a)
        self.assertIn("ПОСЛЕДНИЕ СЛОВА",page)
        self.assertIn("&lt;script&gt;",page)
        self.assertNotIn("<script>",page)
        self.assertNotIn("…",page)
    def test_no_invented_article_and_explicit_limits(self):
        a=self.analyze("5.3.2. Проверяет отчетность.","5.3.2. Может проверять отчетность.")
        report=build_conclusion(a);page=render_conclusion(a)
        self.assertIn("пункт 5.3.2",page)
        self.assertNotIn("статьи 5",page)
        self.assertIn("само по себе не устанавливает нарушение законодательства"," ".join(report["limitations"]))
if __name__=="__main__":unittest.main()
