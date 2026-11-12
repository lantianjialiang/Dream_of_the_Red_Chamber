# -*- coding: utf-8 -*-
"""通用缩略图生成（无头 Chrome Canvas），支持任意文件名映射。

本机没有 Pillow / System.Drawing，沿用 make_web_thumbs.py 的方案：
临时 HTTP 服务提供原图并接收缩放后的 JPEG，Chrome 负责解码绘制。

用法： python scripts/make_thumbs_generic.py _tmp/thumb_jobs.json
清单格式： [{"src":"bk-0001.jpg","out":"bkt-0001.jpg"}, ...]
"""
import os, sys, json, time, base64, threading, subprocess, http.server, socketserver

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(ROOT, 'assets', 'photos')
CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
JOBS = {}          # src -> out
state = {'done': 0, 'fail': 0}
lock = threading.Lock()

PAGE = '''<!doctype html><meta charset="utf-8"><title>WORKING</title><body>
<script>
const jobs = __JOBS__;
const MAX = 560;
async function one(j){
  return new Promise(resolve=>{
    const img = new Image();
    img.onload = async ()=>{
      try{
        const r = Math.min(1, MAX/img.width, MAX/img.height);
        const c = document.createElement('canvas');
        c.width = Math.max(1, Math.round(img.width*r));
        c.height = Math.max(1, Math.round(img.height*r));
        c.getContext('2d').drawImage(img,0,0,c.width,c.height);
        const b64 = c.toDataURL('image/jpeg',0.82).split(',')[1];
        await fetch('/thumb/'+encodeURIComponent(j.out), {method:'POST', body:b64});
      }catch(e){ }
      resolve();
    };
    img.onerror = ()=>resolve();
    img.src = '/img/'+encodeURIComponent(j.src);
  });
}
(async()=>{
  for (let i=0;i<jobs.length;i+=6){ await Promise.all(jobs.slice(i,i+6).map(one)); }
  document.title = 'DONE';
})();
</script></body>'''


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path == '/' or self.path.startswith('/?'):
            body = PAGE.replace('__JOBS__', json.dumps(
                [{'src': k, 'out': v} for k, v in JOBS.items()])).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path.startswith('/img/'):
            name = os.path.basename(self.path[5:].split('?')[0])
            p = os.path.join(DEST, name)
            if not os.path.exists(p):
                self.send_response(404); self.end_headers(); return
            data = open(p, 'rb').read()
            self.send_response(200)
            self.send_header('Content-Type', 'image/jpeg')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self.send_response(404); self.end_headers()

    def do_POST(self):
        if self.path.startswith('/thumb/'):
            name = os.path.basename(self.path[7:].split('?')[0])
            n = int(self.headers.get('Content-Length', 0))
            raw = self.rfile.read(n)
            try:
                data = base64.b64decode(raw)
                if len(data) > 1000:
                    open(os.path.join(DEST, name), 'wb').write(data)
                    with lock:
                        state['done'] += 1
                else:
                    with lock:
                        state['fail'] += 1
            except Exception:
                with lock:
                    state['fail'] += 1
            self.send_response(200); self.end_headers(); self.wfile.write(b'ok')
            return
        self.send_response(404); self.end_headers()


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    if not os.path.exists(CHROME):
        print('未找到 Chrome，跳过缩略图生成')
        return
    jobs = json.load(open(sys.argv[1], encoding='utf-8'))
    for j in jobs:
        if not os.path.exists(os.path.join(DEST, j['out'])):
            JOBS[j['src']] = j['out']
    if not JOBS:
        print('缩略图已全部存在，无需生成')
        return
    print(f'待生成缩略图 {len(JOBS)} 张', flush=True)
    srv = Server(('127.0.0.1', 0), Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    profile = os.path.join(ROOT, '_tmp', 'chrome-thumb-profile')
    p = subprocess.Popen([CHROME, '--headless=new', '--disable-gpu', '--no-sandbox',
                          '--hide-scrollbars', '--disable-extensions',
                          '--user-data-dir=' + profile,
                          '--window-size=800,600', f'http://127.0.0.1:{port}/'],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while time.time() - t0 < 900:
        with lock:
            got = state['done'] + state['fail']
        if got >= len(JOBS):
            break
        time.sleep(0.5)
    try:
        p.terminate(); p.wait(timeout=10)
    except Exception:
        pass
    srv.shutdown()
    print(f'生成 {state["done"]} 张，失败 {state["fail"]} 张，耗时 {int(time.time()-t0)} 秒', flush=True)


if __name__ == '__main__':
    main()
