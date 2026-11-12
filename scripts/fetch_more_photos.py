# -*- coding: utf-8 -*-
"""v2.7 第三轮图库补采：新公开图文页 / 微信公众号图文 + 360 图片检索。

与 fetch_web_photos.py 共用同一套去重、下载、归属与落盘逻辑，新的图片直接
追加进 _tmp/web_manifest.json 与 data/photos-web.js，不新增第五路数据文件，
也不改动站内来源筛选枚举（只使用既有的「微信公众号图文 / 公开图文页 /
公开图片检索」三类）。

用法：
  python scripts/fetch_more_photos.py --dry --limit 8        # 只统计候选
  python scripts/fetch_more_photos.py --only pages            # 只采图文页
  python scripts/fetch_more_photos.py --only 360              # 只做图片检索
  python scripts/fetch_more_photos.py                         # 全量

产出：
  assets/photos/web-NNNN.{jpg|png|webp}   原图（缩略图另由 make_web_thumbs.py 生成）
  data/photos-web.js                      重建后的图库记录
  _tmp/web_manifest.json                  追加后的逐张采集明细
  _tmp/more_candidates.json               本轮全部候选（含被过滤原因）

出处口径与既有图库一致：每张保留原文页面 srcUrl、出处站点/公众号 host、
文章标题 title、采集日期 date、原始图片地址 source 与紧邻配文 caption；
人物归属只依据短图注或检索关键词，无法判定者记「剧组 · 花絮」。
"""
import os, re, sys, json, time, html, argparse, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fetch_web_photos as F  # noqa: E402

F.TODAY = '2026-11-12'
ROOT = F.ROOT
TMP = F.TMP
DEST = F.DEST

SRC_FILE = os.path.join(HERE, 'sources-more.json')
CAND_FILE = os.path.join(TMP, 'more_candidates.json')

# 站点装饰图：头像、logo、二维码、加载占位、推荐位缩略图等
BAD_EXTRA = re.compile(
    r'logo|/icon|_icon|avatar|portrait|qrcode|loading|blank|share|thumb_default|'
    r'sina_logo|/face|top\.png|default/|comment|/btn|1x1|spacer|emoticon|'
    r'/ad/|wx_fmt=gif|/emoji|placeholder|/star|/hot|copyright|'
    r'statics\.itc\.cn|_th\.|_s\.jpg|/small|bg_video|bg0\d\.png|/upload/article/', re.I)

# 360 检索结果里混有视频页/动态页，来源页不是可核查的图文原文，直接放弃
BAD_PAGE = re.compile(r'bilibili\.com/video|/video/|douyin|ixigua|youku|iqiyi|'
                      r'v\.qq\.com|/watch\?|/live/|/shorts/', re.I)

# 懒加载页面把图片地址放在 JS 变量 / data-* 里而非 <img src>，需要整页扫一遍
RAW_IMG = re.compile(r'(?:https?:)?//[^\s"\'<>\\]+?\.(?:jpg|jpeg|png|webp)(?:\?[^\s"\'<>\\]*)?', re.I)

# 360 图片检索：定向人物沿用既有 BING_TARGETS，另加主题词补「场景 / 花絮 / 挂历」
SO360_TOPICS = [
    '87版红楼梦 高清剧照', '87版红楼梦 经典场景 剧照', '87版红楼梦 定妆照',
    '87版红楼梦 试妆照', '87版红楼梦 演员培训班 老照片',
    '87版红楼梦 片场 花絮照', '87版红楼梦 幕后 合影',
    '87版红楼梦 挂历 剧照', '87版红楼梦 30周年 再聚首',
    '87版红楼梦 李耀宗 摄影 剧照', '87版红楼梦 服装设计 手稿',
    '87版红楼梦 群芳 大合影', '87版红楼梦 陈晓旭 欧阳奋强 合影',
    '87版红楼梦 宝黛钗 剧照', '87版红楼梦 金陵十二钗 剧照',
    '87版红楼梦 元妃省亲 剧照', '87版红楼梦 黛玉葬花 剧照',
    '87版红楼梦 刘姥姥进大观园 剧照', '87版红楼梦 晴雯补裘 剧照',
    '87版红楼梦 探春远嫁 剧照', '87版红楼梦 杂志封面 1987',
    '87版红楼梦 扑克牌 剧照', '87版红楼梦 赴港 宣传 旧照',
]

BAD_TITLE = F.BAD_BING
TOPIC_OK = re.compile(r'87版|八七版|1987|红楼梦|红楼|剧照|定妆|试妆|'
                      r'陈晓旭|欧阳奋强|张莉|邓婕|王扶林|李耀宗')
# 只要「图像类」标题，排除纯评论文章里随意配的封面图
IMG_WORD = re.compile(r'剧照|定妆|试妆|老照片|花絮|合影|挂历|封面|照片|'
                      r'图集|影像|造型|扮相|美照|旧照|镜头|画面')


def get_doc(url, timeout=25):
    """带编码兜底的页面抓取：部分搜狐/文学城老页仍是 GBK。"""
    raw = F.get(url, timeout, binary=True)
    doc = raw.decode('utf-8', 'ignore')
    head = doc[:4000]
    if re.search(r'charset\s*=\s*["\']?(gb2312|gbk|gb18030|big5)', head, re.I):
        enc = 'big5' if re.search(r'big5', head, re.I) else 'gb18030'
        doc = raw.decode(enc, 'ignore')
    elif doc.count('\ufffd') > 40:
        doc = raw.decode('gb18030', 'ignore')
    return doc


def pick_ctx(prev, nxt):
    """在既有 choose_ctx 之上补一种版式：▲ 图注写在图片**之前**。"""
    c = F.choose_ctx(prev, nxt)
    if c:
        return c
    p = (prev or '').strip()
    if re.match(r'^[▲△]', p) and F.is_short_label(p):
        return p[:160]
    return ''


def pairs_from_source(src):
    """按 DOM 顺序取每张图的前/后文，返回 [(图片URL, 图注)]。

    另做一次整页原始 URL 扫描：搜狐挂历、杂志封面等页面的图片地址写在
    JS 变量 / data-* 里，<img> 标签只能看到 1 张占位图。补进来的图不给
    人物归属（ctx 为空），避免把推荐位配文硬套到画面上。
    """
    url = src['url'].split('#')[0]
    doc = None
    for attempt in range(2):
        try:
            doc = get_doc(url, 28)
            break
        except Exception:
            if attempt:
                raise
            time.sleep(0.8)
    body = F.body_of(doc, src['type'])
    seq = []
    for tok in F.IMG_TAG.split(body):
        if tok.startswith('<img'):
            u = F.img_url(tok, url)
            if u:
                seq.append(('IMG', u))
        else:
            t = F.clean_text(tok)
            if t:
                seq.append(('TXT', t))
    pairs = []
    for k, (kind, val) in enumerate(seq):
        if kind != 'IMG':
            continue
        prev = next((seq[x][1] for x in range(k - 1, -1, -1) if seq[x][0] == 'TXT'), '')
        nxt = next((seq[x][1] for x in range(k + 1, len(seq)) if seq[x][0] == 'TXT'), '')
        pairs.append((val, pick_ctx(prev, nxt)))

    allow = re.compile(src['allow'], re.I) if src.get('allow') else None
    # 整页 URL 兜底只对 sources-more.json 里标了 raw:true 的懒加载专题启用：
    # 普通门户页的整页 URL 里混着大量侧栏推荐位 / 站点静态图，不能一律收。
    if not src.get('raw'):
        return pairs
    have = {u for u, _ in pairs}
    extra = 0
    for m in RAW_IMG.finditer(doc):
        u = html.unescape(m.group(0)).replace('\\/', '/')
        if u.startswith('//'):
            u = 'https:' + u
        if not u.startswith('http'):
            continue
        if u in have or F.BAD_URL.search(u) or BAD_EXTRA.search(u):
            continue
        if allow and not allow.search(u):
            continue
        have.add(u)
        pairs.append((u, ''))
        extra += 1
    if extra:
        print(f'    [懒加载补图] +{extra} 张', flush=True)
    return pairs


def collect_pages(sources):
    out = []
    for i, s in enumerate(sources, 1):
        try:
            pairs = pairs_from_source(s)
        except Exception as e:
            print(f'  [页面失败] {i}/{len(sources)} {s["title"][:22]} -> {repr(e)[:80]}', flush=True)
            continue
        allow = re.compile(s['allow'], re.I) if s.get('allow') else None
        keep = 0
        for u, ctx in pairs:
            if F.BAD_URL.search(u) or BAD_EXTRA.search(u):
                continue
            if allow and not allow.search(u):
                continue
            if F.PROMO.search(ctx or ''):
                continue
            if s['type'] == 'weixin':
                host = '微信公众号 · ' + s.get('account', '未标注')
                origin = '微信公众号图文'
            else:
                host = s.get('host') or urllib.parse.urlparse(s['url']).netloc
                origin = '公开图文页'
            out.append({
                'url': u, 'page': s['url'].split('#')[0], 'ctx': ctx,
                'title': s['title'], 'host': host, 'origin': origin,
                'srcTitle': s['title'], 'note': s.get('note', ''),
            })
            keep += 1
        print(f'  [页面] {i}/{len(sources)} {s["title"][:24]} -> 图片 {len(pairs)} / 候选 {keep}', flush=True)
        time.sleep(0.25)
    return out


def so360_objects(doc):
    """360 图片检索结果页内嵌的 JSON 对象：img 原图 / link 真实来源页 / title 图注。"""
    out = []
    for m in re.finditer(r'\{"id":"[0-9a-f]{20,}"', doc):
        s = doc[m.start():]
        depth, end = 0, None
        for k, c in enumerate(s):
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    end = k + 1
                    break
        if not end:
            continue
        try:
            o = json.loads(s[:end])
        except Exception:
            continue
        if o.get('img') and o.get('link'):
            out.append(o)
    return out


def collect_360(per_person=10, per_topic=18):
    out, quota = [], {}
    tasks = [(f'87版红楼梦 {c} {a} 剧照', [c]) for c, a in F.BING_TARGETS]
    tasks += [(t, None) for t in SO360_TOPICS]
    for qi, (kw, force) in enumerate(tasks, 1):
        key = force[0] if force else 'TOPIC:' + kw
        limit = per_person if force else per_topic
        u = 'https://image.so.com/i?q=' + urllib.parse.quote(kw)
        try:
            doc = F.get(u, 22, referer='https://image.so.com/')
        except Exception as e:
            print(f'  [检索失败] {kw[:24]} {repr(e)[:60]}', flush=True)
            continue
        got = 0
        for o in so360_objects(doc):
            if quota.get(key, 0) >= limit:
                break
            mu = html.unescape(str(o.get('img') or '')).replace('\\/', '/')
            pu = html.unescape(str(o.get('link') or '')).replace('\\/', '/')
            t = F.clean_text(html.unescape(str(o.get('title') or '')))
            if not mu.startswith('http') or not pu.startswith('http'):
                continue
            if re.search(r'360\.|so\.com|qhimg|qhres', urllib.parse.urlparse(pu).netloc):
                continue
            if BAD_PAGE.search(pu):
                continue
            if F.BAD_URL.search(mu) or BAD_EXTRA.search(mu) or BAD_TITLE.search(t):
                continue
            if not TOPIC_OK.search(t) or not IMG_WORD.search(t):
                continue
            # 定向人物的图必须是短标题，长文章标题往往是「提到该角色」而非画面是该角色
            if force and len(t) > 45:
                continue
            if force and not (force[0] in t or any(a in t for c, a in F.BING_TARGETS if c == force[0])):
                continue
            site = str(o.get('site') or o.get('dspurl') or urllib.parse.urlparse(pu).netloc)
            item = {
                'url': mu, 'page': pu, 'ctx': t[:90], 'title': t[:90],
                'host': site, 'origin': '公开图片检索',
                'srcTitle': '360 图片检索：' + kw, 'note': '',
            }
            if force:
                item['force'] = force
            out.append(item)
            quota[key] = quota.get(key, 0) + 1
            got += 1
        print(f'  [检索] {qi}/{len(tasks)} {kw[:30]} -> {got}', flush=True)
        time.sleep(0.25)
    return out


def download(cands, existing):
    """同 F.download，但对图片 CDN 增加 Referer 兜底（部分站点校验来源页）。"""
    seen, results, rejects = set(existing), [], []
    def dl(it):
        for u in [it['url'], it.get('thumb', '')]:
            if not u or not u.startswith('http'):
                continue
            parts = urllib.parse.urlsplit(u)
            refs = [it.get('page'), parts.scheme + '://' + parts.netloc + '/', None]
            for ref in refs:
                try:
                    b = F.get(u, 15, referer=ref, binary=True)
                except Exception:
                    continue
                ext = F.sniff(b)
                if not ext or ext == 'gif' or len(b) < 8000:
                    continue
                d = F.dims(b, ext)
                if not d or min(d) < 200 or max(d) < 300:
                    continue
                w, h = d
                if not (0.3 < w / h < 3.6):
                    continue
                return dict(it, data=b, ext=ext, w=w, h=h, dlurl=u)
        return None
    import hashlib
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = {ex.submit(dl, it): it for it in cands}
        for n, f in enumerate(as_completed(futs), 1):
            r = f.result()
            if not r:
                rejects.append({'url': futs[f]['url'], 'why': '下载失败/尺寸不足/非图片'})
                continue
            h = hashlib.md5(r['data']).hexdigest()
            if h in seen:
                rejects.append({'url': r['url'], 'why': '重复（与已有图库或本轮其他图相同）'})
                continue
            seen.add(h)
            results.append((h, r))
            if n % 200 == 0:
                print(f'  ...已处理 {n}/{len(cands)}，可用 {len(results)}', flush=True)
    return results, rejects


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0, help='只处理前 N 个图文源')
    ap.add_argument('--only', choices=['pages', '360', 'all'], default='all')
    ap.add_argument('--dry', action='store_true', help='只统计候选，不下载不写盘')
    ap.add_argument('--per-person', type=int, default=10)
    ap.add_argument('--per-topic', type=int, default=18)
    args = ap.parse_args()

    sources = json.load(open(SRC_FILE, encoding='utf-8'))['sources']
    if args.limit:
        sources = sources[:args.limit]
    print(f'本轮图文源 {len(sources)} 个；人物词表 {len(F.NAMES)} 人', flush=True)

    cands = []
    if args.only in ('pages', 'all'):
        cands += collect_pages(sources)
    if args.only in ('360', 'all'):
        cands += collect_360(args.per_person, args.per_topic)

    # 同原始地址只下一次；与既有 manifest 的原始图片地址也去重
    known = set()
    try:
        for m in json.load(open(os.path.join(TMP, 'web_manifest.json'), encoding='utf-8')):
            if m.get('source'):
                known.add(m['source'])
    except Exception:
        pass
    uniq, seen = [], set()
    for c in cands:
        if c['url'] in seen or c['url'] in known:
            continue
        seen.add(c['url'])
        uniq.append(c)
    print(f'候选 {len(cands)} -> URL 去重后 {len(uniq)}', flush=True)
    json.dump(uniq, open(CAND_FILE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    by = {}
    for c in uniq:
        by[c['origin']] = by.get(c['origin'], 0) + 1
    print('分渠道候选：', by, flush=True)
    if args.dry:
        print('dry-run：未下载、未写盘', flush=True)
        return

    existing = F.existing_hashes()
    print(f'已有图片哈希 {len(existing)} 个', flush=True)
    results, rejects = download(uniq, existing)
    print(f'下载可用 {len(results)} 张，过滤/失败 {len(rejects)} 张', flush=True)
    json.dump(rejects, open(os.path.join(TMP, 'more_rejects.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    manifest = F.save(results)
    print('写入图库记录', F.build_js(manifest), '条 -> data/photos-web.js', flush=True)
    by2 = {}
    for m in manifest:
        by2[m['origin']] = by2.get(m['origin'], 0) + 1
    print('全库分渠道：', by2, flush=True)


if __name__ == '__main__':
    main()
