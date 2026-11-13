# -*- coding: utf-8 -*-
"""87版《红楼梦》女性人物照片采集脚本（可复用于下一位角色）。

用法：
  1) 修改下方 KEYWORDS 为目标人物的检索词（例如 "薛宝钗 张莉 剧照"）。
  2) 修改 main() 里的文件名前缀 name = f'cxx-{n:03d}...' 中的 cxx 为对应缩写。
  3) 运行： python scripts/fetch_nverce_photos.py
     结果写入 _archive/retired/nverce-source/images/，候选与清单写入
     _tmp/candidates.json、_tmp/manifest.json（采集底本已移出仓库）。
  4) 去重与人工目检后，把选定图片整理进 data/nv-photos-source.js（字段见现有记录），
     再运行 scripts/make_nverce_thumbs.ps1 生成 thumbs/ 缩略图。
  5) 在人物数据 window.PEOPLE 中把该角色 status 改为 done。

说明：图片来自公开图片检索结果，仅用于个人资料收藏，版权归原权利人所有。
"""
import os, re, json, time, html, hashlib, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.path.join(ROOT, '_tmp')
IMG = os.path.join(ROOT, '_archive', 'retired', 'nverce-source', 'images')
os.makedirs(IMG, exist_ok=True)
os.makedirs(TMP, exist_ok=True)

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

KEYWORDS = [
    '陈晓旭 林黛玉 剧照',
    '陈晓旭 林黛玉 87版红楼梦 剧照',
    '陈晓旭 林黛玉 高清剧照',
    '87版红楼梦 黛玉葬花 剧照 陈晓旭',
    '陈晓旭 林黛玉 定妆照',
    '陈晓旭 生活照 老照片',
    '陈晓旭 林黛玉 潇湘馆 剧照',
    '陈晓旭 林黛玉 焚稿 剧照',
    '陈晓旭 林黛玉 宝黛读西厢 剧照',
    '陈晓旭 欧阳奋强 红楼梦 合影',
    '陈晓旭 张莉 邓婕 红楼梦 剧组合影',
    '陈晓旭 妙真法师 出家 照片',
    '陈晓旭 世邦广告 照片',
    '陈晓旭 早年 鞍山话剧团 照片',
    '87版红楼梦 林黛玉 陈晓旭 壁纸',
    '陈晓旭 家春秋 梅表姐 剧照',
    '陈晓旭 林黛玉 剧照 新浪 图集',
    '陈晓旭 林黛玉 黑白 老照片',
    '陈晓旭 追思会 林黛玉 照片',
    '陈晓旭 林黛玉 造型 剧照 合集',
]

# Reject obviously irrelevant results (bing sometimes degrades to stock photos)
GOOD = re.compile(r'陈晓旭|晓旭|林黛玉|黛玉|红楼梦|红楼|妙真|潇湘|葬花|宝黛|王扶林|欧阳奋强|邓婕|张莉|大观园|颦')
BAD = re.compile(r'素材|模板|设计图|免抠|昵图|摄图|众图|包图|知乎|毕业证|旅游|爱心|图标|矢量|壁纸网|素材网|下载|PSD|AI素材|logo|素材图片')

def get(url, timeout=20, referer=None):
    req = urllib.request.Request(url, headers={
        'User-Agent': UA,
        'Accept': 'text/html,application/xhtml+xml,image/avif,image/webp,*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        **({'Referer': referer} if referer else {}),
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def search(kw):
    out = []
    q = urllib.parse.quote(kw)
    for first in (0, 35, 70):
        url = f'https://www.bing.com/images/async?q={q}&first={first}&count=35&relp=35&lostate=r&mmasync=1'
        try:
            raw = get(url, 25).decode('utf-8', 'ignore')
        except Exception as e:
            print('  SEARCH FAIL', kw, first, str(e)[:60], flush=True)
            time.sleep(1.2)
            continue
        for m in re.findall(r'\sm="(\{[^>]*?\})"', raw):
            try:
                d = json.loads(html.unescape(m))
            except Exception:
                continue
            if 'murl' not in d:
                continue
            title = re.sub('<[^>]+>', '', d.get('t', '') or '')
            out.append({
                'url': d.get('murl', ''),
                'thumb': d.get('turl', ''),
                'page': d.get('purl', ''),
                'title': title[:160],
                'kw': kw,
            })
        time.sleep(0.55)
    return out

def dims(data):
    try:
        if data[:8] == b'\x89PNG\r\n\x1a\n':
            return int.from_bytes(data[16:20], 'big'), int.from_bytes(data[20:24], 'big')
        if data[:2] == b'\xff\xd8':
            i = 2
            while i < len(data) - 9:
                if data[i] != 0xFF:
                    i += 1; continue
                marker = data[i+1]
                if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                    i += 2; continue
                seglen = int.from_bytes(data[i+2:i+4], 'big')
                if marker in (0xC0,0xC1,0xC2,0xC3,0xC5,0xC6,0xC7,0xC9,0xCA,0xCB,0xCD,0xCE,0xCF):
                    return int.from_bytes(data[i+7:i+9], 'big'), int.from_bytes(data[i+5:i+7], 'big')
                i += 2 + seglen
            return None
        if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
            if data[12:16] == b'VP8X':
                return (int.from_bytes(data[24:27],'little')+1, int.from_bytes(data[27:30],'little')+1)
            if data[12:16] == b'VP8 ':
                return (int.from_bytes(data[26:28],'little') & 0x3fff, int.from_bytes(data[28:30],'little') & 0x3fff)
            if data[12:16] == b'VP8L':
                b = int.from_bytes(data[21:25],'little')
                return ((b & 0x3fff)+1, ((b>>14)&0x3fff)+1)
        if data[:3] == b'GIF':
            return int.from_bytes(data[6:8],'little'), int.from_bytes(data[8:10],'little')
    except Exception:
        return None
    return None

def sniff(data):
    if data[:2] == b'\xff\xd8': return 'jpg'
    if data[:8] == b'\x89PNG\r\n\x1a\n': return 'png'
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP': return 'webp'
    if data[:3] == b'GIF': return 'gif'
    return None

def relevant(it):
    t = it['title']
    if GOOD.search(t): return True
    # keep if from a page clearly about the subject, even with a generic title
    if GOOD.search(urllib.parse.unquote(it['page'])): return True
    if BAD.search(t): return False
    return None  # uncertain -> keep for visual review

def main():
    all_items = []
    for kw in KEYWORDS:
        got = search(kw)
        print(f'[search] {kw} -> {len(got)}', flush=True)
        all_items += got
    seen, items = set(), []
    for it in all_items:
        u = it['url']
        if not u.startswith('http') or u in seen: continue
        seen.add(u)
        it['rel'] = relevant(it)
        if it['rel'] is False: continue
        items.append(it)
    print('TOTAL relevant candidates:', len(items), flush=True)
    json.dump(items, open(os.path.join(TMP, 'candidates.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    results = []
    def dl(idx_it):
        idx, it = idx_it
        for u in [it['url'], it['thumb']]:
            if not u.startswith('http'): continue
            try:
                data = get(u, 18, referer=it.get('page') or 'https://www.bing.com/')
                ext = sniff(data)
                if not ext or len(data) < 9000: continue
                d = dims(data)
                if not d or min(d) < 240 or max(d) < 300: continue
                return {'idx': idx, 'data': data, 'ext': ext, 'w': d[0], 'h': d[1],
                        'url': u, 'page': it.get('page',''), 'kw': it['kw'], 'title': it['title']}
            except Exception:
                continue
        return None

    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = [ex.submit(dl, (i, it)) for i, it in enumerate(items)]
        for f in as_completed(futs):
            r = f.result()
            if r: results.append(r)
    print('DOWNLOADED ok:', len(results), flush=True)

    by_hash = {}
    for r in results:
        h = hashlib.md5(r['data']).hexdigest()
        if h not in by_hash or r['w']*r['h'] > by_hash[h]['w']*by_hash[h]['h']:
            by_hash[h] = r
    uniq = sorted(by_hash.values(), key=lambda x: -(x['w']*x['h']))
    print('UNIQUE:', len(uniq), flush=True)

    manifest = []
    for n, r in enumerate(uniq, 1):
        name = f'cxx-{n:03d}.{r["ext"]}'
        open(os.path.join(IMG, name), 'wb').write(r['data'])
        manifest.append({'file': 'images/'+name, 'w': r['w'], 'h': r['h'],
                         'source': r['url'], 'page': r['page'], 'keyword': r['kw'], 'title': r['title']})
        del r['data']
    json.dump(manifest, open(os.path.join(TMP, 'manifest.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('SAVED', len(manifest), flush=True)

if __name__ == '__main__':
    main()
