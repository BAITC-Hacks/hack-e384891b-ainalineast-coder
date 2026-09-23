// Same Python engine as the desktop edition, isolated in a Web Worker.
const CDN='https://cdn.jsdelivr.net/pyodide/v0.27.7/full/';
const progress=text=>self.postMessage({progress:text});
let corePromise;
const loadedPackages=new Set();
const pythonFiles=['backend.py','comparison.py','comparison_report.py','legal_text.py','legal_report.py','export_api.py','export_documents.py','export_xlsx.py','browser_adapter.py'];
async function resource(path) {
  const response=await fetch(new URL('_python/'+path,import.meta.url));
  if(!response.ok)throw Error('Не удалось загрузить компонент приложения: '+path);
  return new Uint8Array(await response.arrayBuffer());
}
async function init() {
  progress('Подготавливаем модуль сравнения. При первом открытии потребуется Интернет.');
  const {loadPyodide}=await import(CDN+'pyodide.mjs');
  const py=await loadPyodide({indexURL:CDN});
  py.FS.mkdirTree('/versa/assets');py.FS.mkdirTree('/versa/data');
  const resources=[...pythonFiles,'assets/Roboto-Regular.ttf','assets/Roboto-Bold.ttf'];
  const contents=await Promise.all(resources.map(resource));
  resources.forEach((path,i)=>py.FS.writeFile('/versa/'+path,contents[i]));
  py.runPython("import sys\nsys.path.insert(0, '/versa')\nimport json\nfrom browser_adapter import dispatch");
  progress('Готово. Документы обрабатываются только в вашем браузере.');
  return py;
}
async function packages(py,url,payload) {
  let needed;
  if(url==='/api/extract' && (payload?.files||[]).some(f=>/\.pdf$/i.test(f.name))) needed='pdf-read';
  if(url==='/api/export-document') needed=payload?.extension;
  if(!needed||needed==='xlsx'||loadedPackages.has(needed))return;
  progress('Подготавливаем обработку '+(needed==='pdf-read'?'PDF':needed.toUpperCase())+'.');
  await py.loadPackage('micropip');
  if(needed==='docx'){
    await py.loadPackage('lxml');
    await py.runPythonAsync("import micropip\nawait micropip.install('python-docx==1.2.0')");
  } else if(needed==='pdf'){
    await py.loadPackage('pillow');
    await py.runPythonAsync("import micropip\nawait micropip.install('reportlab==4.4.9')");
  } else {
    await py.runPythonAsync("import micropip\nawait micropip.install('pypdf==6.10.0')");
  }
  loadedPackages.add(needed);
}
async function handle({id,url,payload}) {
  try{
    if(!corePromise)corePromise=init().catch(error=>{corePromise=null;throw error;});
    const py=await corePromise;
    await packages(py,url,payload);
    py.globals.set('_versa_url',url);
    py.globals.set('_versa_payload',JSON.stringify(payload??null));
    let result;
    try{result=JSON.parse(py.runPython("json.dumps(dispatch(_versa_url, json.loads(_versa_payload)), ensure_ascii=False)"));}
    finally{py.globals.delete('_versa_url');py.globals.delete('_versa_payload');}
    progress('Готово. Документы обрабатываются только в вашем браузере.');
    self.postMessage({id,result});
  }catch(error){
    const raw=String(error.message||error);
    const lines=raw.trim().split('\n');
    const detail=lines[lines.length-1].replace(/^\w*Error:\s*/,'');
    progress('Не удалось завершить операцию. Можно повторить действие.');
    self.postMessage({id,error:'Не удалось выполнить операцию: '+detail});
  }
}
let queue=Promise.resolve();
self.onmessage=event=>{queue=queue.then(()=>handle(event.data));};
