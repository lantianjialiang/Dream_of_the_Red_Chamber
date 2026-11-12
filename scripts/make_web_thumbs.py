# -*- coding: utf-8 -*-
"""为本轮补采的 web-NNNN.* 生成 webt-NNNN.jpg 缩略图。

本机没有 Pillow，PowerShell 的 System.Drawing 在此环境也加载不了，
因此用无头 Chrome 内置的 canvas 完成缩放：临时起一个本地 HTTP 服务
提供原图、接收缩放后的 JPEG，Chrome 只负责解码/绘制。

用法： python scripts/make_web_thumbs.py
可重复运行，已生成的文件自动跳过。
"""
import os, re, sys, time, base64, threading, subprocess, http.server, socketserver, json

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(ROOT, 'assets', 'photos')
CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
TODOS = []

state = {'done': 0, 'fail': 0}
lock = threading.Lock()

PAGE = '''<!doctype html><meta charset="utf-8"><title>WORKING</title><body>
<script>
const files = __FILES__;
const MAX = 560;
async function one(f){
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
        await fetch('/thumb/'+encodeURIComponent(f), {method:'POST', body:b64});
      }catch(e){ }
      resolve();
    };
    img.onerror = ()=>resolve();
    img.src = '/img/'+encodeURIComponent(f);
  });
}
(async()=>{
  for (let i=0;i<files.length;i+=6){
    await Promise.all(files.slice(i,i+6).map(one));
  }
  document.title = 'DONE';
})();
</script></body>'''


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path == '/' or self.path.startswith('/?'):
            body = PAGE.replace('__FILES__', json.dumps(TODOS)).encode('utf-8')
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
            stem = os.path.splitext(name)[0].replace('web-', '')
            out = os.path.join(DEST, 'webt-' + stem + '.jpg')
            n = int(self.headers.get('Content-Length', 0))
            raw = self.rfile.read(n)
            try:
                data = base64.b64decode(raw)
                if len(data) > 1000:
                    open(out, 'wb').write(data)
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
        print('未找到 Chrome，跳过缩略图生成（站点将直接使用原图）')
        return
    for f in sorted(os.listdir(DEST)):
        m = re.match(r'^web-(\d{4})\.(jpg|jpeg|png|webp)$', f, re.I)
        if not m:
            continue
        t = os.path.join(DEST, 'webt-' + m.group(1) + '.jpg')
        if not os.path.exists(t):
            TODOS.append(f)
    if not TODOS:
        print('缩略图已全部存在，无需生成')
        return
    print(f'待生成缩略图 {len(TODOS)} 张', flush=True)

    srv = Server(('127.0.0.1', 0), Handler)
    port = srv.server_address[1]
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()

    profile = os.path.join(ROOT, '_tmp', 'chrome-thumb-profile')
    cmd = [CHROME, '--headless=new', '--disable-gpu', '--no-sandbox',
           '--hide-scrollbars', '--disable-extensions',
           '--user-data-dir=' + profile,
           '--window-size=800,600', f'http://127.0.0.1:{port}/']
    p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while time.time() - t0 < 420:
        with lock:
            got = state['done'] + state['fail']
        if got >= len(TODOS):
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
