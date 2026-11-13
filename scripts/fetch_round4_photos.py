# -*- coding: utf-8 -*-
"""v2.8 第四轮图库补采：360 图片分页 API 深度 + 必应图片异步分页 + 33 个新图文页。

与前三轮共用同一套去重、下载、归属与落盘逻辑：新图仍追加进
_tmp/web_manifest.json 与 data/photos-web.js，不新增第五路数据文件，
站内来源筛选仍是既有的「微信公众号图文 / 公开图文页 / 公开图片检索」三类。

第三轮（fetch_more_photos.py）的 360 检索只取 HTML 首页约 60–90 条；本轮改用
https://image.so.com/j?q=...&pn=180 的分页接口，一次可取约 150–162 条，
并新增必应 https://www.bing.com/images/async 的真分页（每页 35 条）。
两个渠道都同时给出原图地址与真实来源页，符合站内「出处可核查」规范。

不可用的渠道如实记录、不编造出处：
  百度图片 acjson  -> {"antiFlag":1,"message":"Forbid spider access"}
  搜狗图片 napi    -> {"status":1,"info":"forbid"}
  搜狗图片 HTML    -> link 只指向 pic.sogou.com/d 中转页，非原文页面，故不采
  微博图片搜索      -> 登录墙（仅 9.6KB 壳页）
  知乎搜索         -> 403
  今日头条 / 文学城 / kknews 繁体页 / 多彩贵州网 -> 403 / 502 / 反爬壳页

用法：
  python scripts/fetch_round4_photos.py --dry
  python scripts/fetch_round4_photos.py --only pages
  python scripts/fetch_round4_photos.py --only search
  python scripts/fetch_round4_photos.py

产出：
  assets/photos/web-NNNN.*          原图（缩略图另由 make_web_thumbs.py 增量生成）
  data/photos-web.js                重建后的图库记录
  _tmp/web_manifest.json            追加后的逐张采集明细
  _tmp/round4_candidates.json       本轮全部候选
"""
import os, re, sys, json, time, html, argparse, urllib.parse
from concurrent.futures import ThreadPoolExecutor

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fetch_web_photos as F       # noqa: E402
import fetch_more_photos as M      # noqa: E402

# M 在 import 时把日期固定成上一轮，这里覆盖为本轮
F.TODAY = '2026-11-13'
ROOT, TMP, DEST = F.ROOT, F.TMP, F.DEST
SRC_FILE = os.path.join(HERE, 'sources-round4.json')
CAND_FILE = os.path.join(TMP, 'round4_candidates.json')

# 第四轮新增主题词：场景、物件、时间节点、幕后工种（与第三轮 SO360_TOPICS 互补）
EXTRA_TOPICS = [
    '87版红楼梦 黛玉葬花 剧照', '87版红楼梦 宝钗扑蝶 剧照',
    '87版红楼梦 共读西厢 剧照', '87版红楼梦 黛玉焚稿 剧照',
    '87版红楼梦 宝玉挨打 剧照', '87版红楼梦 王熙凤 弄权 剧照',
    '87版红楼梦 中秋夜宴 剧照', '87版红楼梦 元宵 灯会 剧照',
    '87版红楼梦 大观园 题对额 剧照', '87版红楼梦 黑白 老剧照',
    '87版红楼梦 高清修复 剧照', '87版红楼梦 连环画 剧照',
    '87版红楼梦 明信片 剧照', '87版红楼梦 宣传画 老照片',
    '87版红楼梦 画册 剧照 内页', '87版红楼梦 开机 老照片',
    '87版红楼梦 杀青 合影', '87版红楼梦 试妆 定妆 对比',
    '87版红楼梦 杨树云 化妆 剧照', '87版红楼梦 史延芹 服装 剧照',
    '87版红楼梦 王扶林 片场 老照片', '87版红楼梦 陈力 演唱会 旧照',
    '87版红楼梦 35周年 聚首 照片', '87版红楼梦 人民大会堂 聚首',
    '87版红楼梦 红楼梦中人 再聚首', '87版红楼梦 剧组 合影 老照片',
    '87版红楼梦 演员 现代装 合影', '87版红楼梦 剧照 罕见 珍藏',
    '1987 红楼梦 电视剧 剧照 组图', '陈晓旭 欧阳奋强 剧照 合影',
    '张莉 邓婕 87版红楼梦 剧照', '金陵十二钗 87版 剧照 图集',
]

# 必应标题里带高亮用的私用区字符，先清掉再走闸门
HILITE = re.compile(r'[\ue000-\uf8ff]')
BAD_HOST = re.compile(r'360\.|so\.com|qhimg|qhres|bing\.com|microsoft', re.I)


def clean(s):
    return F.clean_text(HILITE.sub('', html.unescape(str(s or ''))))


def get_text(url, referer, timeout=22):
    return F.get(url, timeout, referer=referer)


def so360_deep(kw):
    """360 图片分页接口：pn 是返回上限（一次最多约 162 条），不是起始偏移。"""
    q = urllib.parse.quote(kw)
    u = f'https://image.so.com/j?q={q}&pd=1&pn=180&correct={q}&adstar=0&tab=all'
    try:
        d = json.loads(get_text(u, 'https://image.so.com/'))
        return d.get('list', []) or []
    except Exception:
        return []


def bing_objects(kw, pages=4):
    """必应图片异步分页：first=1,36,71,106 ... 每页 35 条，m 属性含 murl/purl/t。"""
    q = urllib.parse.quote(kw)
    out = []
    for p in range(pages):
        u = f'https://www.bing.com/images/async?q={q}&first={1 + p * 35}&count=35&adlt=off'
        try:
            doc = get_text(u, 'https://www.bing.com/images/search?q=' + q)
        except Exception:
            continue
        for m in re.findall(r'\sm="(\{[^>]*?\})"', doc):
            try:
                o = json.loads(html.unescape(m))
            except Exception:
                continue
            if o.get('murl'):
                out.append(o)
        time.sleep(0.12)
    return out


def accepted(mu, pu, t, force):
    """两渠道共用的闸门：真实来源页 + 短标题 + 图像类词 + 红楼主题词 + 排除噪声。"""
    if not mu.startswith('http') or not pu.startswith('http'):
        return False
    if BAD_HOST.search(urllib.parse.urlparse(pu).netloc):
        return False
    if M.BAD_PAGE.search(pu) or M.BAD_EXTRA.search(mu) or F.BAD_URL.search(mu):
        return False
    if M.BAD_TITLE.search(t) or not M.TOPIC_OK.search(t) or not M.IMG_WORD.search(t):
        return False
    if len(t) > 45:
        return False
    if force and not (force[0] in t or any(a in t for c, a in F.BING_TARGETS if c == force[0])):
        return False
    return True


def collect_search(per_person=10, per_topic=20):
    tasks = [(f'87版红楼梦 {c} {a} 剧照', [c]) for c, a in F.BING_TARGETS]
    tasks += [(t, None) for t in M.SO360_TOPICS]
    tasks += [(t, None) for t in EXTRA_TOPICS]
    out = []
    for qi, (kw, force) in enumerate(tasks, 1):
        key = force[0] if force else 'TOPIC:' + kw
        limit = per_person if force else per_topic
        # 两个渠道各占一半配额，避免先跑的渠道把名额吃光
        q360 = max(1, int(limit * 0.6))
        qbing = max(1, limit - q360)
        got = {'360': 0, 'bing': 0}

        for o in so360_deep(kw):
            if got['360'] >= q360:
                break
            mu = html.unescape(str(o.get('img') or '')).replace('\\/', '/')
            pu = html.unescape(str(o.get('link') or '')).replace('\\/', '/')
            t = clean(o.get('title'))
            if not accepted(mu, pu, t, force):
                continue
            site = str(o.get('site') or o.get('dspurl') or urllib.parse.urlparse(pu).netloc)
            item = {
                'url': mu, 'page': pu, 'ctx': t[:90], 'title': t[:90],
                'host': site, 'origin': '公开图片检索',
                'srcTitle': '360 图片检索（分页）：' + kw,
                'note': '',
            }
            if force:
                item['force'] = force
            out.append(item)
            got['360'] += 1

        for o in bing_objects(kw, pages=4):
            if got['bing'] >= qbing:
                break
            mu = html.unescape(str(o.get('murl') or '')).replace('\\/', '/')
            pu = html.unescape(str(o.get('purl') or '')).replace('\\/', '/')
            t = clean(o.get('t') or o.get('desc'))
            if not accepted(mu, pu, t, force):
                continue
            site = urllib.parse.urlparse(pu).netloc
            item = {
                'url': mu, 'page': pu, 'ctx': t[:90], 'title': t[:90],
                'host': site, 'origin': '公开图片检索',
                'srcTitle': '必应图片检索（分页）：' + kw,
                'note': '',
            }
            if force:
                item['force'] = force
            out.append(item)
            got['bing'] += 1

        if qi % 10 == 0 or qi == len(tasks):
            print(f'  [检索] {qi}/{len(tasks)} 累计候选 {len(out)}', flush=True)
        time.sleep(0.15)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true', help='只统计候选，不下载不写盘')
    ap.add_argument('--only', choices=['pages', 'search', 'all'], default='all')
    ap.add_argument('--per-person', type=int, default=10)
    ap.add_argument('--per-topic', type=int, default=20)
    args = ap.parse_args()

    sources = json.load(open(SRC_FILE, encoding='utf-8'))['sources']
    print(f'第四轮图文源 {len(sources)} 个；人物 {len(F.BING_TARGETS)} 位；'
          f'主题词 {len(M.SO360_TOPICS) + len(EXTRA_TOPICS)} 组', flush=True)

    cands = []
    if args.only in ('pages', 'all'):
        cands += M.collect_pages(sources)
    if args.only in ('search', 'all'):
        cands += collect_search(args.per_person, args.per_topic)

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
    print(f'候选 {len(cands)} -> 与图库去重后 {len(uniq)}', flush=True)
    json.dump(uniq, open(CAND_FILE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    by = {}
    for c in uniq:
        by[c['origin']] = by.get(c['origin'], 0) + 1
    print('分渠道候选：', by, flush=True)
    if args.dry:
        print('dry-run：未下载、未写盘', flush=True)
        return

    existing = F.existing_hashes()
    print(f'已有图片哈希 {len(existing)} 个，开始下载…', flush=True)
    results, rejects = M.download(uniq, existing)
    print(f'下载可用 {len(results)} 张，过滤/失败/重复 {len(rejects)} 张', flush=True)
    json.dump(rejects, open(os.path.join(TMP, 'round4_rejects.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    manifest = F.save(results)
    print('写入图库记录', F.build_js(manifest), '条 -> data/photos-web.js', flush=True)
    by2 = {}
    for m in manifest:
        by2[m['origin']] = by2.get(m['origin'], 0) + 1
    print('全库分渠道：', by2, flush=True)


if __name__ == '__main__':
    main()
