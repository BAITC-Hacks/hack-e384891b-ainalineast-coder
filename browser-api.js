/* Browser-only transport: user documents never leave this tab. */
(() => {
  const workerURL = new URL('browser-worker.mjs', document.currentScript.src);
  let worker, counter = 0;
  const pending = new Map(), downloadURLs = new Set();
  function progress(text) {
    const element = document.getElementById('browser-engine-status');
    if (element) element.textContent = text;
  }
  function stop(error) {
    for (const entry of pending.values()) { clearTimeout(entry.timer); entry.reject(error); }
    pending.clear();
    if (worker) worker.terminate();
    worker = null;
  }
  function getWorker() {
    if (worker) return worker;
    worker = new Worker(workerURL, {type:'module'});
    worker.onmessage = ({data}) => {
      if (data.progress) { progress(data.progress); return; }
      const entry = pending.get(data.id);
      if (!entry) return;
      clearTimeout(entry.timer); pending.delete(data.id);
      if (data.error) entry.reject(new Error(data.error));
      else entry.resolve(data.result);
    };
    worker.onerror = event => {
      event.preventDefault();
      progress('Не удалось загрузить модуль. Проверьте соединение и повторите действие.');
      stop(new Error('Не удалось загрузить модуль сравнения. Проверьте доступ к Интернету и повторите действие.'));
    };
    return worker;
  }
  function request(url, payload) {
    return new Promise((resolve, reject) => {
      const id=++counter;
      const timer=setTimeout(() => {
        progress('Операция прервана по времени. Можно повторить действие.');
        stop(new Error('Операция заняла слишком много времени. Повторите действие или сравните меньший комплект документов.'));
      }, 180000);
      pending.set(id,{resolve,reject,timer});
      try { getWorker().postMessage({id,url,payload}); }
      catch (error) { clearTimeout(timer);pending.delete(id);reject(error); }
    });
  }
  function blobResult(content, mime, extension) {
    const href=URL.createObjectURL(new Blob([content],{type:mime}));
    downloadURLs.add(href);
    setTimeout(()=>{URL.revokeObjectURL(href);downloadURLs.delete(href);},60000);
    return {href,name:'Versa-сравнение.'+extension,path:'Versa-сравнение.'+extension};
  }
  window.versaBrowserApi = async (url, payload) => {
    if (url==='/api/health') return {ok:true,version:'1.1.0',browser:true,local:true,pdf:true,llmConfigured:false,llmModel:''};
    if (url==='/api/export') {
      const types={html:'text/html;charset=utf-8',csv:'text/csv;charset=utf-8',json:'application/json;charset=utf-8'};
      if(!types[payload?.extension]||typeof payload.content!=='string')throw Error('Неизвестный формат скачивания.');
      return blobResult(payload.content,types[payload.extension],payload.extension);
    }
    const result=await request(url,payload);
    if(result.encoding==='base64') {
      const binary=atob(result.content);
      const bytes=Uint8Array.from(binary,char=>char.charCodeAt(0));
      return blobResult(bytes,result.mime,result.extension);
    }
    return result;
  };
  window.addEventListener('pagehide',()=>{
    for(const href of downloadURLs)URL.revokeObjectURL(href);
    downloadURLs.clear();
    stop(new Error('Страница закрыта. Повторите действие после возвращения.'));
  });
})();
