import base64, io, json, threading, unittest, urllib.request, urllib.error, zipfile
from http.server import ThreadingHTTPServer
import backend
import tempfile
from pathlib import Path
from unittest.mock import patch
import app
from app import Handler, CONTROL
class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True); cls.thread.start()
        cls.url="http://127.0.0.1:"+str(cls.server.server_port)
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join()
    def post(self,path,payload,headers=None):
        data=json.dumps(payload,ensure_ascii=False).encode()
        req=urllib.request.Request(self.url+path,data,{"Content-Type":"application/json",**(headers or {})})
        with urllib.request.urlopen(req) as res: return json.load(res)
    def test_http_control_and_evidence(self):
        result=self.post("/api/analyze",CONTROL)
        self.assertIn("elapsedMs",result)
        self.assertTrue(all(f["evidence"] for f in result["findings"]))
        self.assertGreaterEqual(result["stats"]["losses"],1)
    def test_reject_cross_origin(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.post("/api/analyze",CONTROL,{"Origin":"https://untrusted.invalid"})
        self.assertEqual(cm.exception.code,403)
    def test_reject_empty_documents(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.post("/api/analyze",{"before":[],"after":[]})
        self.assertEqual(cm.exception.code,400)
    def test_extract_reports_failed_file(self):
        result=self.post("/api/extract",{"files":[{"name":"ok.md","content":base64.b64encode("1.1. Отдел ведет реестр договоров.".encode()).decode()},{"name":"bad.doc","content":base64.b64encode(b"abc").decode()}]})
        self.assertIn("реестр",result["files"][0]["text"])
        self.assertIn("error",result["files"][1])
    def test_static_server_does_not_publish_source(self):
        with self.assertRaises(urllib.error.HTTPError) as cm: urllib.request.urlopen(self.url+"/backend.py")
        self.assertEqual(cm.exception.code,404)
    def test_export_is_saved_and_downloadable(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(app,"ROOT",Path(folder)):
            result=self.post("/api/export",{"extension":"html","content":"<!doctype html><p>Verified evidence report</p>"})
            file=Path(result["path"])
            self.assertEqual(file.parent,Path(folder)/"exports")
            self.assertTrue(file.is_file())
            with urllib.request.urlopen(self.url+result["href"]) as res:
                self.assertIn("attachment",res.headers["Content-Disposition"])
                self.assertIn("sandbox",res.headers["Content-Security-Policy"])
                self.assertIn(b"Verified evidence report",res.read())
    def test_export_rejects_path_like_extension(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.post("/api/export",{"extension":"../../app.py","content":"bad"})
        self.assertEqual(cm.exception.code,400)
    def test_xlsx_values(self):
        data=io.BytesIO()
        with zipfile.ZipFile(data,"w") as z:
            z.writestr("xl/worksheets/sheet1.xml",'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>Отдел аудита</t></is></c><c r="B1" t="inlineStr"><is><t>проверяет платежи</t></is></c></row></sheetData></worksheet>')
        text=backend.extract_file("test.xlsx",data.getvalue())["text"]
        self.assertIn("Отдел аудита",text);self.assertIn("проверяет платежи",text)
    def test_csv_utf8(self):
        text=backend.extract_file("test.csv","Подразделение;Функция\nАудит;Проверяет платежи".encode())["text"]
        self.assertIn("Аудит | Проверяет платежи",text)
    def test_pdf_extraction_if_installed(self):
        try: import pypdf
        except ImportError: self.skipTest("Optional pypdf not installed")
        # Small complete PDF with a standard Type1 font and ASCII text layer.
        objs=[b"<< /Type /Catalog /Pages 2 0 R >>",b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 800] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
        stream=b"BT /F1 12 Tf 40 700 Td (1.1. The audit department reviews payment operations and reports material risks.) Tj ET"
        objs.append(b"<< /Length "+str(len(stream)).encode()+b" >>\nstream\n"+stream+b"\nendstream")
        pdf=b"%PDF-1.4\n";offsets=[0]
        for i,obj in enumerate(objs,1): offsets.append(len(pdf));pdf+=str(i).encode()+b" 0 obj\n"+obj+b"\nendobj\n"
        pos=len(pdf);pdf+=b"xref\n0 6\n0000000000 65535 f \n"+b"".join(("%010d 00000 n \n"%x).encode() for x in offsets[1:])+b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n"+str(pos).encode()+b"\n%%EOF"
        text=backend.extract_file("test.pdf",pdf)["text"]
        self.assertIn("reviews payment operations",text)
if __name__=="__main__": unittest.main()
