"""Behavioral checks for evidence, scope, negation, transfers and ingestion."""
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.error import URLError
import zipfile
from backend import analyze, extract_file

def document(text, unit=""):
    return {"name": "fixture.md", "text": text, "unit": unit}

class ComparisonTests(unittest.TestCase):
    def run_pair(self, before, after):
        return analyze({"before": before, "after": after})

    def test_renumbering_preserves_function_and_sources(self):
        r = self.run_pair([document("1.1. Проверяет сохранность оборудования на складе.", "Аудит")],
                          [document("9.7. Проверяет сохранность оборудования на складе.", "Аудит")])
        self.assertEqual(r["mappings"][0]["status"], "preserved")
        self.assertEqual(r["mappings"][0]["after"]["ref"], "9.7")
        self.assertNotEqual(r["mappings"][0]["before"]["id"], r["mappings"][0]["after"]["id"])
        self.assertEqual(r["stats"]["losses"], 0)

    def test_owner_transfer_is_not_loss(self):
        r = self.run_pair([document("1.1. Проводит инвентаризацию оборудования на складе.", "Старый отдел")],
                          [document("3.2. Проводит инвентаризацию оборудования на складе.", "Новый отдел")])
        self.assertEqual(r["mappings"][0]["status"], "moved")
        self.assertEqual(r["stats"]["losses"], 0)

    def test_real_policy_transfer_across_sections(self):
        before = "5.4. Директор департамента непрерывного мониторинга системы внутреннего контроля:\n5.4.4. взаимодействует с субъектами СВК Общества в части:\nб. выявления рисков с недостаточным или дублирующим покрытием субъектами СВК и иными заинтересованными сторонами в рамках Карты гарантий;"
        after = "5.3. Директоры департаментов и Директоры направлений ДИТААД и ДОА:\n5.3.3. готовят предложения для включения в план работ БВА, взаимодействуют с субъектами СВК Общества в части:\nб. выявления рисков с недостаточным или дублирующим покрытием субъектами СВК и иными заинтересованными сторонами в рамках Карты гарантий;"
        r = self.run_pair([document(before)],[document(after)])
        m = next(m for m in r["mappings"] if m["before"]["ref"]=="5.4.4.б")
        self.assertEqual(m["status"],"moved")
        self.assertEqual(m["after"]["ref"],"5.3.3.б")

    def test_loss_is_a_candidate_with_original_evidence(self):
        r = self.run_pair([document("1.1. Формирует группы контроля качества с привлечением работников.", "Методология")],
                          [document("1.1. Выполняет резервное копирование клиентских баз данных.", "ИТ")])
        f = next(f for f in r["findings"] if f["type"]=="loss")
        self.assertEqual(f["evidence"][0]["side"],"before")
        self.assertIn("не доказывает", " ".join(r["warnings"]))
        self.assertEqual(f["review"],"pending")

    def test_distinct_owners_duplicate(self):
        function = "1.1. Проверяет платежи поставщикам оборудования."
        r = self.run_pair([document(function,"Контроль")],
                          [document(function,"Контроль"),document(function,"Казначейство")])
        f = next(f for f in r["findings"] if f["type"]=="duplicate")
        self.assertEqual(len({c["unit"] for c in f["evidence"]}),2)
        self.assertTrue(all(c["side"]=="after" for c in f["evidence"]))

    def test_same_owner_is_not_duplicate(self):
        function = "1.1. Проверяет платежи поставщикам оборудования."
        r = self.run_pair([document(function,"Контроль")],
                          [document(function+"\n1.2. Проверяет платежи поставщикам оборудования.","Контроль")])
        self.assertFalse(any(f["type"]=="duplicate" for f in r["findings"]))

    def test_execution_control_conflict_and_prohibition(self):
        before = document("1.1. Управляет закупками оборудования.", "Закупки")
        r = self.run_pair([before],[document("1.1. Управляет закупками оборудования.\n1.2. Проверяет закупки оборудования.", "Закупки")])
        self.assertTrue(any(f["type"]=="conflict" for f in r["findings"]))
        r = self.run_pair([before],[document("1.1. Не имеет права управлять закупками оборудования.\n1.2. Проверяет закупки оборудования.", "Закупки")])
        self.assertFalse(any(f["type"]=="conflict" for f in r["findings"]))

    def test_obligation_weakening_is_not_lost_in_normalization(self):
        r = self.run_pair([document("9.15. Для определения объема проверки осуществляется анализ контрольных процедур объекта аудита.", "Аудит")],
                          [document("9.15. Для определения объема проверки может осуществляться анализ контрольных процедур объекта аудита.", "Аудит")])
        self.assertTrue(any(f["title"]=="Изменена обязательность или запрет" for f in r["findings"]))

    def test_evidence_integrity_and_no_implicit_llm(self):
        r = self.run_pair([document("1.1. Проверяет учет оборудования.", "Аудит")],
                          [document("1.2. Организует обучение персонала.", "Кадры")])
        ids={c["id"] for d in r["documents"] for c in d["clauses"]}
        self.assertTrue(all(c["id"] in ids for f in r["findings"] for c in f["evidence"]))
        self.assertFalse(r["engine"]["llmUsed"])

    def test_empty_input_is_rejected(self):
        with self.assertRaises(ValueError):
            analyze({"before":[],"after":[]})

class IngestionTests(unittest.TestCase):
    def test_docx_paragraphs_are_read(self):
        file=io.BytesIO()
        with zipfile.ZipFile(file,"w") as z:
            z.writestr("word/document.xml",'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>1.1. Контролирует закупки.</w:t></w:r></w:p></w:body></w:document>')
        result=extract_file("sample.docx",file.getvalue())
        self.assertIn("Контролирует закупки",result["text"])

    def test_legacy_and_scan_need_explicit_conversion(self):
        with self.assertRaisesRegex(ValueError,"Старый"):
            extract_file("sample.doc",b"binary")
        with self.assertRaisesRegex(ValueError,"не найден"):
            extract_file("sample.txt",b" ")



class LocalModelValidationTests(unittest.TestCase):
    def payload(self):
        return {"before":[document("1.1. Проверяет сохранность складского оборудования.", "Аудит")],
                "after":[document("1.1. Формирует отчет по коммерческим предложениям клиентов.", "Продажи")],"llm":True}

    def test_unavailable_local_model_falls_back_honestly(self):
        with patch("backend.urllib.request.urlopen", side_effect=URLError("unavailable")):
            r=analyze(self.payload())
        self.assertTrue(r["engine"]["llmRequested"])
        self.assertFalse(r["engine"]["llmUsed"])
        self.assertEqual(r["engine"]["mode"],"offline")
        self.assertTrue(any("Ollama недоступна" in w for w in r["warnings"]))

    def test_model_fabricated_source_ids_are_rejected(self):
        answer={"response":json.dumps({"matches":[{"beforeId":"fabricated","afterId":"fabricated",
                  "beforeQuote":"Проверяет сохранность складского оборудования.",
                  "afterQuote":"Формирует отчет по коммерческим предложениям клиентов."}]},ensure_ascii=False)}
        with patch("backend.urllib.request.urlopen", return_value=io.BytesIO(json.dumps(answer).encode())):
            r=analyze(self.payload())
        self.assertEqual(r["engine"]["refinedPairs"],0)
        self.assertEqual(r["mappings"][0]["status"],"missing")

    def test_model_fabricated_quotes_are_rejected(self):
        payload=self.payload()
        baseline=analyze({**payload,"llm":False})
        a=baseline["mappings"][0]["before"]
        b=next(c for d in baseline["documents"] if d["side"]=="after" for c in d["clauses"] if c["functional"])
        answer={"response":json.dumps({"matches":[{"beforeId":a["id"],"afterId":b["id"],
                  "beforeQuote":"Эта цитата не существует в исходном документе.",
                  "afterQuote":"Эта цитата также выдумана полностью."}]},ensure_ascii=False)}
        with patch("backend.urllib.request.urlopen", return_value=io.BytesIO(json.dumps(answer).encode())):
            r=analyze(payload)
        self.assertEqual(r["engine"]["refinedPairs"],0)
        self.assertEqual(r["mappings"][0]["status"],"missing")

class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=Path(__file__).resolve().parent
        cls.result=None
        if (root/"data/audit-before.md").exists() and (root/"data/audit-after.md").exists():
            cls.result=analyze({"before":[{"name":"audit-before.md","unit":"Блок внутреннего аудита","text":(root/"data/audit-before.md").read_text(encoding="utf-8")}],
                                "after":[{"name":"audit-after.md","unit":"Блок внутреннего аудита","text":(root/"data/audit-after.md").read_text(encoding="utf-8")}]})
            r=cls.result
            print("\nAUDIT_DIAGNOSTIC="+json.dumps({"stats":r["stats"],"engine":r["engine"],
                "units":[{"name":u["name"],"status":u["status"]} for u in r["units"]],
                "specialMappings":[{"before":m["before"]["ref"],"after":m["after"]["ref"] if m["after"] else None,
                    "from":m["before"]["unit"],"to":m["after"]["unit"] if m["after"] else None,"status":m["status"],"score":m["score"]}
                    for m in r["mappings"] if m["before"]["ref"] in ("5.4.4.а","5.4.4.б","9.15","5.6.2","5.6.3")],
                "findings":[{"type":f["type"],"title":f["title"],"refs":[c["ref"] for c in f["evidence"]]} for f in r["findings"][:25]]},ensure_ascii=False))

    def test_full_audit_structure_and_transfers(self):
        if self.result is None:
            self.skipTest("Optional bundled audit fixtures are absent")
        r=self.result
        units={u["name"]:u for u in r["units"]}
        self.assertEqual(units["ДНМ"]["status"],"retained")
        self.assertEqual(units["ДККМ"]["status"],"retained")
        self.assertEqual(units["ДИТААД"]["status"],"created")
        self.assertEqual(units["ДОА"]["status"],"created")
        for letter in ("а","б"):
            m=next(m for m in r["mappings"] if m["before"]["ref"]=="5.4.4."+letter)
            self.assertEqual(m["status"],"moved")
            self.assertEqual(m["after"]["ref"],"5.3.3."+letter)
            self.assertEqual(m["before"]["unit"],"ДНМ")
        self.assertTrue(any(f["type"]=="change" and any(c["ref"]=="9.15" for c in f["evidence"]) for f in r["findings"]))
        self.assertFalse(any(f["type"]=="loss" and any(c["ref"]=="3.6" for c in f["evidence"]) for f in r["findings"]))
        self.assertFalse(any(f["type"]=="change" and any(c["ref"]=="4.4" for c in f["evidence"]) for f in r["findings"]))
        self.assertFalse(any(f["type"]=="loss" and any(c["ref"]=="8.8.8" for c in f["evidence"]) for f in r["findings"]))
        self.assertGreater(r["stats"]["preserved"],100)
        self.assertFalse(r["engine"]["llmUsed"])

    def test_control_end_to_end(self):
        try:
            from app import CONTROL
        except ImportError:
            self.skipTest("Optional server control fixture is absent")
        r=analyze(CONTROL)
        print("\nCONTROL_DIAGNOSTIC="+json.dumps({"stats":r["stats"],"findings":[{"type":f["type"],"refs":[c["ref"] for c in f["evidence"]]} for f in r["findings"]]},ensure_ascii=False))
        self.assertTrue(any(f["type"]=="loss" and any("ликвидности" in c["text"] for c in f["evidence"]) for f in r["findings"]))
        self.assertTrue(any(m["status"]=="moved" and "реестр договоров" in m["before"]["text"] for m in r["mappings"]))
        self.assertTrue(any(f["type"]=="duplicate" and all("бюджет" in c["text"] for c in f["evidence"]) for f in r["findings"]))
        self.assertTrue(any(f["type"]=="conflict" and all("платежные операции" in c["text"] for c in f["evidence"]) for f in r["findings"]))

if __name__ == "__main__":
    unittest.main()

