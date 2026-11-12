# -*- coding: utf-8 -*-
"""87版《红楼梦》图库补采：微信公众号图文 + 公开图文页 + 定向图片检索。

用法：
  python scripts/fetch_web_photos.py --limit 3        # 小批量试跑（前 3 个图源）
  python scripts/fetch_web_photos.py                   # 全量图文采集
  python scripts/fetch_web_photos.py --bing            # 追加定向图片检索
  python scripts/fetch_web_photos.py --build-only      # 只依据已下载清单重建 JS 数据

产出：
  assets/photos/web-NNNN.{jpg|png|webp}   原图（缩略图由 make_web_thumbs.ps1 生成 webt-*.jpg）
  data/photos-web.js                      图库记录（window.HLM87.webPhotos）
  _tmp/web_manifest.json                  逐张采集明细（含原始图片地址与配文）
  _tmp/web_candidates.json                全部候选（含被过滤原因，便于复核）

出处口径：每张图保留 原文页面 URL、出处站点/公众号名、文章标题、采集日期、
原始图片地址与紧邻配文。人物归属由配文中的角色名/演员名推断，推断不出的
统一记为「剧组 · 花絮」，不强行安到某个人名下。图片版权归原权利人所有。
"""
import os, re, io, sys, json, time, html, hashlib, argparse, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.path.join(ROOT, '_tmp')
DEST = os.path.join(ROOT, 'assets', 'photos')
os.makedirs(TMP, exist_ok=True)
os.makedirs(DEST, exist_ok=True)

TODAY = '2026-11-11'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

# ---------------------------------------------------------------- 人物词表
# 简称/剧中俗称 -> 资料馆正式人物名（避免把「宝玉」当成新人物）
ALIASES = {
    '宝玉': '贾宝玉', '宝二爷': '贾宝玉', '黛玉': '林黛玉', '林妹妹': '林黛玉',
    '颦儿': '林黛玉', '宝钗': '薛宝钗', '宝姐姐': '薛宝钗', '凤姐': '王熙凤',
    '凤辣子': '王熙凤', '琏二奶奶': '王熙凤', '元春': '贾元春', '元妃': '贾元春',
    '迎春': '贾迎春', '探春': '贾探春', '惜春': '贾惜春', '湘云': '史湘云',
    '可卿': '秦可卿', '小红': '林红玉', '红玉': '林红玉', '玉钏': '玉钏儿',
    '金桂': '夏金桂', '金钏': '金钏儿', '宝琴': '薛宝琴', '岫烟': '邢岫烟',
    '尤二姐': '尤二姐', '尤三姐': '尤三姐', '刘姥姥': '刘姥姥', '老祖宗': '贾母',
    '史太君': '贾母', '琏二爷': '贾琏', '宝蟾': '宝蟾', '傻大姐': '傻大姐',
    # 合称：一张合影里同时出现多位，拆开索引后各人物页都能看到
    '宝黛钗凤': ['林黛玉', '贾宝玉', '薛宝钗', '王熙凤'],
    '宝黛': ['贾宝玉', '林黛玉'], '黛钗': ['林黛玉', '薛宝钗'],
    '宝钗凤': ['薛宝钗', '王熙凤'], '宝黛钗': ['贾宝玉', '林黛玉', '薛宝钗'],
    '四春': ['贾元春', '贾迎春', '贾探春', '贾惜春'],
    '三春': ['贾迎春', '贾探春', '贾惜春'],
    '晓旭': '林黛玉', '怡红公子': '贾宝玉', '蘅芜君': '薛宝钗', '潇湘妃子': '林黛玉',
}

# 判定一段配文是否真的在讲 87 版《红楼梦》；用于剔除门户页「相关推荐」位图片
TOPIC = re.compile(
    r'红楼|宝玉|黛玉|宝钗|熙凤|凤姐|贾母|贾琏|贾政|贾赦|贾珍|贾芸|贾环|贾瑞|'
    r'袭人|晴雯|平儿|鸳鸯|紫鹃|香菱|妙玉|湘云|探春|迎春|惜春|元春|可卿|李纨|'
    r'巧姐|刘姥姥|丫鬟|丫头|大观园|潇湘|怡红|蘅芜|太虚|金陵|十二钗|曹雪芹|'
    r'王扶林|欧阳奋强|陈晓旭|邓婕|张莉|87版|八七版|1987|剧组|定妆|剧照|扮演者|'
    r'演员|试妆|片场|幕后|花絮|合影|旧照|老照片|培训班|学习班|聚首|重聚|再聚首|'
    r'剧版|电视剧|选角|造型|扮相|戏曲|黄梅戏|陈力|王立平|'
    # v2.7：图注常用合称/场景名，旧词表会把「宝黛初次相会」「柳湘莲悔婚」
    # 「元妃省亲」误判成与红楼无关，进而被 curate_photos.py 当作侧栏推荐位剔除
    r'宝黛|黛钗|宝黛钗|林妹妹|宝姐姐|柳湘莲|元妃|省亲|仪仗|悔婚|读西厢|'
    r'裙钗|群芳|芍药|葬花|夜宴|出殡|挂历|扑克|共读|意绵绵|蒲柳|风姿|'
    r'杨树云|史延芹|李耀宗|邓云乡')
# 演员名 -> 角色（一个演员可能对应多个角色）
ACTOR_FIX = {
    '侯长荣': ['北静王', '柳湘莲'], '欧阳奋强': ['贾宝玉'], '陈晓旭': ['林黛玉'],
    '张莉': ['薛宝钗'], '邓婕': ['王熙凤'], '郭霄珍': ['史湘云'],
    '郭宵珍': ['史湘云'], '姬培杰': ['妙玉'], '姬玉': ['妙玉'],
    '张静林': ['晴雯'], '安雯': ['晴雯'], '袁玫': ['袭人'], '沈琳': ['平儿'],
    '沈玲': ['平儿'], '陈剑月': ['香菱'], '郑铮': ['鸳鸯'], '徐丽霞': ['紫鹃'],
    '东方闻樱': ['贾探春'], '东方闻樱': ['贾探春'], '胡泽红': ['贾惜春'],
    '金莉莉': ['贾迎春'], '牟一': ['贾迎春'], '成梅': ['贾元春'],
    '张蕾': ['秦可卿'], '夏丽蓉': ['秦可卿'], '孙梦泉': ['李纨'],
    '李婷': ['贾母'], '周贤珍': ['王夫人'], '夏明辉': ['邢夫人'],
    '王贵娥': ['尤氏'], '李凤英': ['薛姨妈'], '苏秋冬': ['赵姨娘'],
    '战爱霞': ['赵姨娘'], '李伊': ['邢岫烟'], '王羊': ['薛宝琴'],
    '周月': ['尤三姐'], '张明明': ['尤二姐'], '沙玉华': ['刘姥姥'],
    '高宏亮': ['贾琏'], '高亮': ['贾琏'], '吴晓东': ['贾芸'], '马广儒': ['贾瑞'],
    '李志新': ['贾珍'], '李颉': ['贾赦'], '杨俊勇': ['贾蓉'], '罗立平': ['贾蔷'],
    '王蔚': ['贾环'], '陈洪海': ['薛蟠'], '杨晓玲': ['夏金桂'], '阎青妤': ['宝蟾'],
    '沈璐': ['秋桐'], '李曼': ['彩云'], '刘玲玲': ['莺儿'], '李楠': ['茗烟'],
    '李玥': ['板儿'], '李文辉': ['板儿'], '李端': ['巧姐'], '王暄': ['巧姐'],
    '于洁': ['玉钏儿'], '程荣': ['龄官'], '孔繁洁': ['芳官'], '侯华': ['蒋玉菡'],
    '马明妹': ['雪雁'], '谷彤': ['司棋'], '谷童': ['司棋'], '韩流流': ['麝月'],
    '刘继红': ['林红玉'], '张海燕': ['傻大姐'], '孙彩虹': ['周瑞家的'],
    '金淑媛': ['王善保家的'], '颜燕': ['坠儿'], '房方': ['贾兰'],
    '刘宗佑': ['贾雨村'], '王忠信': ['甄士隐'], '马加奇': ['贾政'],
    '马明妹': ['雪雁'], '卓金燕': ['瑞珠'], '孙桂珍': ['南妃'],
}


def load_characters():
    """从 data/characters.js 读出 248 人及其演员，构建 关键词 -> 正式角色名 映射。"""
    src = open(os.path.join(ROOT, 'data', 'characters.js'), encoding='utf-8').read()
    names, kw = [], {}
    for line in src.splitlines():
        m = re.search(r'\{id:"([^"]+)",\s*name:"([^"]+)"', line)
        if not m:
            continue
        name = m.group(2)
        names.append(name)
        kw[name] = [name]
        am = re.search(r'actor:"([^"]*)"', line)
        if am:
            actor = am.group(1)
            if actor and actor not in ('—', '待核', ''):
                for a in re.split(r'[·/、,，]', actor):
                    a = a.strip()
                    if len(a) >= 2:
                        kw.setdefault(a, []).append(name)
        alm = re.search(r'aliases:"([^"]*)"', line)
        if alm:
            for a in re.split(r'[·/、,，]', alm.group(1)):
                a = a.strip()
                if len(a) >= 2:
                    kw.setdefault(a, []).append(name)
    for short, fulls in ALIASES.items():
        for full in (fulls if isinstance(fulls, (list, tuple)) else [fulls]):
            if full in names:
                kw.setdefault(short, [])
                if full not in kw[short]:
                    kw[short].append(full)
    for actor, chars in ACTOR_FIX.items():
        for c in chars:
            if c in names:
                kw.setdefault(actor, [])
                if c not in kw[actor]:
                    kw[actor].append(c)
    # 长词优先，避免「贾迎春」被「迎春」抢先截断
    keys = sorted(kw.keys(), key=lambda x: -len(x))
    return names, kw, keys


NAMES, KW, KEYS = load_characters()


def who(text):
    """从逐图图注推断人物，返回 (角色名列表, 归属方式)。

    v2.4 加固：只有**短图注**（<=40 字）才允许归到具体人物。
    早先允许「长段落里只提到 1–3 人」也算归属，结果把新闻导语、门户侧栏正文
    里的角色名套到了图片上；现在一律记「剧组 · 花絮」，宁可少归也不错归。
    """
    if not text:
        return [], '未判定'
    raw = text.strip()
    if len(raw) > 40 or re.search(r'style=|id=|data-|class=|<|>', raw):
        return [], '未判定'
    t = raw[:160]
    found, seen = [], set()
    for k in KEYS:
        if len(k) < 2 or k in seen:
            continue
        if k in t:
            seen.add(k)
            for c in KW[k]:
                if c not in found:
                    found.append(c)
            # 移除被长词包含的短词，避免「林黛玉」又命中「黛玉」
            for s in list(KEYS):
                if s != k and s in k and len(s) >= 2:
                    seen.add(s)
            if len(found) >= 6:
                break
    if not found or len(found) >= 4:
        return [], '未判定'
    if len(found) >= 3 and re.search(r'等|以及|合影|众人|全家福|大合影|群芳', raw):
        return [], '未判定'
    return found[:3], '原文配文'


def is_short_label(t):
    return bool(t) and len(t) <= 40 and not re.search(r'style=|id=|class=|<|>', t)


def choose_ctx(prev, nxt):
    """按图注方位选择一张图真正对应的文字。

    中文图文页常见两种排版：
      ▲ 图注写在图片**之后**（「上图说明」）——正确配文是后文，且整组连续图共用；
      ▽ 图注写在图片**之前**（「下图说明」）——正确配文是前文。
    旧版一律取「图片之前的最后文字」，会把 ▲ 型整组图向前错一位：
    曾把「▲薛宝钗定妆照」组标成上一组的「▲贾宝玉定妆照」。
    """
    p, n = (prev or '').strip(), (nxt or '').strip()
    if re.match(r'^[▲△]', n) and is_short_label(n):
        return n
    if re.search(r'[▽▼]', p) and is_short_label(p):
        return p
    if is_short_label(n) and who(n)[0]:
        return n
    if is_short_label(p) and who(p)[0] and not is_short_label(n):
        return p
    return ''


# ---------------------------------------------------------------- 页面解析
PROMO = re.compile(r'二维码|长按|扫码|识别图|关注我们|点个在看|点赞|赞赏|视频号|'
                   r'转发|推荐阅读|往期|点击上方|广告|营业厅|欢迎关注|点击关注|'
                   r'版权归|免责声明|更多精彩|戳这里|阅读全文|喜欢就')
BAD_URL = re.compile(r'qrcode|/icon|/logo|_logo|/ad[_-]|advert|placeholder|'
                     r'loading|blank\.gif|wx_fmt=gif|mmbiz_gif|/emoji|share\.png', re.I)
IMG_TAG = re.compile(r'(<img\b[^>]*>)', re.I)
TAG = re.compile(r'<[^>]+>')


def get(url, timeout=25, referer=None, binary=False):
    h = {'User-Agent': UA, 'Accept-Language': 'zh-CN,zh;q=0.9',
         'Accept': 'text/html,application/xhtml+xml,image/avif,image/webp,*/*'}
    if referer:
        h['Referer'] = referer
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    return raw if binary else raw.decode('utf-8', 'ignore')


def img_url(tag, base):
    for attr in ('data-src', 'data-original', 'data-lazy-src', 'data-url', 'src'):
        m = re.search(attr + r'\s*=\s*["\']([^"\']+)["\']', tag, re.I)
        if not m:
            continue
        u = html.unescape(m.group(1)).strip()
        if not u or u.startswith('data:'):
            continue
        if u.startswith('//'):
            u = 'https:' + u
        elif u.startswith('/'):
            u = urllib.parse.urljoin(base, u)
        if u.startswith('http'):
            return u
    return None


def clean_text(s):
    s = html.unescape(TAG.sub(' ', s))
    return re.sub(r'\s+', ' ', s).strip()


def page_title(doc, fallback=''):
    for pat in (r'var msg_title\s*=\s*["\']([^"\']+)',
                r'<meta property="og:title" content="([^"]+)',
                r'<title>([^<]+)</title>'):
        m = re.search(pat, doc)
        if m:
            t = html.unescape(m.group(1)).strip()
            t = re.sub(r'\s*[_|–-]\s*(微信|公众号|网易|新浪|腾讯|搜狐).*$', '', t)
            if len(t) > 3:
                return t[:90]
    return fallback


def account_of(doc, fallback=''):
    m = re.search(r'var nickname\s*=\s*["\']([^"\']+)', doc) or \
        re.search(r'id="js_name"[^>]*>\s*([^<]+)', doc)
    if m:
        return html.unescape(m.group(1)).strip()[:40]
    return fallback


def body_of(doc, kind):
    """尽量把解析范围收窄到正文，减少头像/侧栏/推荐位图片。"""
    if kind == 'weixin':
        i = doc.find('id="js_content"')
        if i > 0:
            # 从该 div 的 '>' 之后开始，避免把 style/data-* 属性残留当成配文
            gt = doc.find('>', i)
            i = gt + 1 if gt > i else i
            j = doc.find('id="js_pc_qr_code"', i)
            return doc[i: (j if j > i else i + 500000)]
    for marker in ('id="article-content"', 'class="article-content"',
                   'id="content"', 'class="post_body"', 'id="js_content"'):
        i = doc.find(marker)
        if i > 0:
            return doc[i:i + 400000]
    return doc[:500000]


def extract_pairs(url, src):
    """返回 [(图片URL, 逐图图注), ...]，并给出页面标题/公众号名。

    v2.4：按 DOM 顺序同时取每张图的前文与后文，交给 choose_ctx() 判断
    图注方位，避免「图片在上、图注在下」型页面整体错位。
    """
    clean = url.split('#')[0]
    doc = get(clean, 28)
    title = page_title(doc, src.get('title', ''))
    account = account_of(doc, src.get('account', '')) if src['type'] == 'weixin' else src.get('account', '')
    body = body_of(doc, src['type'])
    seq = []
    for tok in IMG_TAG.split(body):
        if tok.startswith('<img'):
            u = img_url(tok, clean)
            if u:
                seq.append(('IMG', u))
        else:
            t = clean_text(tok)
            if t:
                seq.append(('TXT', t))
    pairs = []
    for k, (kind, val) in enumerate(seq):
        if kind != 'IMG':
            continue
        prev = next((seq[x][1] for x in range(k - 1, -1, -1) if seq[x][0] == 'TXT'), '')
        nxt = next((seq[x][1] for x in range(k + 1, len(seq)) if seq[x][0] == 'TXT'), '')
        pairs.append((val, choose_ctx(prev, nxt)[:160]))
    return pairs, title, account


# ---------------------------------------------------------------- 图片校验
def sniff(b):
    if b[:2] == b'\xff\xd8': return 'jpg'
    if b[:8] == b'\x89PNG\r\n\x1a\n': return 'png'
    if b[:4] == b'RIFF' and b[8:12] == b'WEBP': return 'webp'
    if b[:3] == b'GIF': return 'gif'
    return None


def dims(b, ext):
    try:
        if ext == 'png':
            return int.from_bytes(b[16:20], 'big'), int.from_bytes(b[20:24], 'big')
        if ext == 'jpg':
            i = 2
            while i < len(b) - 9:
                if b[i] != 0xFF:
                    i += 1; continue
                marker = b[i + 1]
                if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                    i += 2; continue
                seglen = int.from_bytes(b[i + 2:i + 4], 'big')
                if marker in (0xC0,0xC1,0xC2,0xC3,0xC5,0xC6,0xC7,0xC9,0xCA,0xCB,0xCD,0xCE,0xCF):
                    return int.from_bytes(b[i + 7:i + 9], 'big'), int.from_bytes(b[i + 5:i + 7], 'big')
                i += 2 + seglen
        if ext == 'gif':
            return int.from_bytes(b[6:8], 'little'), int.from_bytes(b[8:10], 'little')
        if ext == 'webp':
            if b[12:16] == b'VP8X':
                return int.from_bytes(b[24:27], 'little') + 1, int.from_bytes(b[27:30], 'little') + 1
            if b[12:16] == b'VP8 ':
                return int.from_bytes(b[26:28], 'little') & 0x3fff, int.from_bytes(b[28:30], 'little') & 0x3fff
            if b[12:16] == b'VP8L':
                v = int.from_bytes(b[21:25], 'little')
                return (v & 0x3fff) + 1, ((v >> 14) & 0x3fff) + 1
    except Exception:
        return None
    return None


def existing_hashes():
    hs = set()
    for f in os.listdir(DEST):
        if re.search(r'\.(jpg|jpeg|png|webp|gif)$', f, re.I):
            try:
                hs.add(hashlib.md5(open(os.path.join(DEST, f), 'rb').read()).hexdigest())
            except Exception:
                pass
    return hs


def kind_of(text):
    return '生活照' if re.search(r'生活照|幕后|花絮|合影|聚会|培训班|旧照|近照|今昔|重聚|'
                                r'再聚首|试妆|片场|私照|家庭照|赴港|签名|教材', text or '') else '剧照'


def make_desc(ctx, title):
    """图库卡片用短描述；HTML 属性残留直接丢掉，长配文截断。完整配文另存 caption。"""
    c = re.sub(r'\s+', ' ', (ctx or '')).strip()
    if re.search(r'style=|id=|data-|class=|<|>', c):
        c = ''
    short = (c[:48] + '…') if len(c) > 48 else c
    return ((short + ' · ') if short and short not in title else '') + '《' + title + '》'


def clean_caption(ctx):
    c = re.sub(r'\s+', ' ', (ctx or '')).strip()
    return '' if re.search(r'style=|id=|data-|class=|<|>', c) else c[:160]


# ---------------------------------------------------------------- 采集
def collect_from_pages(sources, existing):
    candidates = []
    for i, s in enumerate(sources, 1):
        try:
            pairs, title, account = extract_pairs(s['url'], s)
        except Exception as e:
            print(f'  [页面失败] {i}/{len(sources)} {s["title"][:24]} -> {repr(e)[:90]}', flush=True)
            continue
        keep = 0
        for u, ctx in pairs:
            if BAD_URL.search(u):
                continue
            if PROMO.search(ctx or ''):
                continue
            host = '微信公众号 · ' + account if s['type'] == 'weixin' else (account or urllib.parse.urlparse(s['url']).netloc)
            candidates.append({
                'url': u, 'page': s['url'].split('#')[0], 'ctx': ctx,
                'title': title, 'host': host,
                'origin': '微信公众号图文' if s['type'] == 'weixin' else '公开图文页',
                'srcTitle': s['title'], 'note': s.get('note', ''),
            })
            keep += 1
        print(f'  [页面] {i}/{len(sources)} {title[:26]} -> 图片 {len(pairs)} / 候选 {keep}', flush=True)
        time.sleep(0.3)
    return candidates


BING_TARGETS = [
    ('林黛玉', '陈晓旭'), ('薛宝钗', '张莉'), ('贾宝玉', '欧阳奋强'), ('王熙凤', '邓婕'),
    ('贾元春', '成梅'), ('贾迎春', '金莉莉'), ('贾探春', '东方闻樱'), ('贾惜春', '胡泽红'),
    ('史湘云', '郭霄珍'), ('妙玉', '姬玉'), ('秦可卿', '张蕾'), ('李纨', '孙梦泉'),
    ('袭人', '袁玫'), ('晴雯', '安雯'), ('平儿', '沈琳'), ('香菱', '陈剑月'),
    ('紫鹃', '徐丽霞'), ('鸳鸯', '郑铮'), ('刘姥姥', '沙玉华'), ('贾母', '李婷'),
    ('薛宝琴', '王羊'), ('尤三姐', '周月'), ('巧姐', '王暄'), ('贾琏', '高宏亮'),
    ('贾政', '马加奇'), ('王夫人', '周贤珍'), ('邢夫人', '夏明辉'), ('尤氏', '王贵娥'),
    ('薛姨妈', '李凤英'), ('赵姨娘', '苏秋冬'), ('邢岫烟', '李伊'), ('夏金桂', '杨晓玲'),
    ('尤二姐', '张明明'), ('司棋', '谷彤'), ('麝月', '韩流流'), ('莺儿', '刘玲玲'),
    ('玉钏儿', '于洁'), ('彩云', '李曼'), ('秋桐', '沈璐'), ('宝蟾', '阎青妤'),
    ('龄官', '程荣'), ('芳官', '孔繁洁'), ('傻大姐', '张海燕'), ('贾芸', '吴晓东'),
    ('柳湘莲', '侯长荣'), ('北静王', '侯长荣'), ('蒋玉菡', '侯华'), ('贾瑞', '马广儒'),
    ('贾蔷', '罗立平'), ('贾蓉', '杨俊勇'), ('贾赦', '李颉'), ('贾珍', '李志新'),
    ('薛蟠', '陈洪海'), ('贾环', '王蔚'), ('茗烟', '李楠'), ('林红玉', '刘继红'),
    ('板儿', '李玥'), ('雪雁', '马明妹'), ('周瑞家的', '孙彩虹'), ('坠儿', '颜燕'),
    ('贾兰', '房方'), ('贾雨村', '刘宗佑'), ('甄士隐', '王忠信'),
]
BAD_BING = re.compile(r'素材|模板|免抠|昵图|摄图|众图|包图|矢量|PSD|logo|图标|'
                      r'壁纸网|素材网|下载|表情包|头像|淘宝|京东|拼多多|招聘|'
                      r'新版红楼梦|新版红楼|越剧|电影版|2010版|游戏|手绘|插画|漫画')


def collect_from_bing(per_person=8):
    """定向图片检索：每人限量，宁少勿滥。

    图片检索结果的出处质量天然弱于图文文章，故设四道闸门：
      1) 每人最多 per_person 张；
      2) 图片标题必须点名角色或演员，且带 87版/红楼梦/剧照/定妆 等限定；
      3) 排除素材站、新版红楼梦、越剧/电影版、插画等；
      4) 来源页 purl 必须是真实外部页面（不能是 bing.com 搜索页），
         否则这张图无法给出可核查出处，直接放弃。
    """
    out, quota = [], {}
    for char, actor in BING_TARGETS:
        kw = f'87版红楼梦 {char} {actor} 剧照'
        q = urllib.parse.quote(kw)
        u = f'https://www.bing.com/images/search?q={q}&form=HDRSC2&first=1'
        got = 0
        try:
            doc = get(u, 22)
        except Exception:
            print(f'  [检索失败] {char}', flush=True)
            continue
        for m in re.findall(r'\sm="(\{[^>]*?\})"', doc):
            if quota.get(char, 0) >= per_person:
                break
            try:
                d = json.loads(html.unescape(m))
            except Exception:
                continue
            mu, pu = d.get('murl', ''), d.get('purl', '')
            t = re.sub('<[^>]+>', '', d.get('t', '') or '')
            if not mu.startswith('http') or not pu.startswith('http') or 'bing.com' in pu:
                continue
            if BAD_URL.search(mu) or BAD_BING.search(t):
                continue
            if not (char in t or actor in t):
                continue
            if not re.search(r'87版|八七版|红楼梦|红楼|剧照|定妆|' + re.escape(actor), t):
                continue
            out.append({
                'url': mu, 'page': pu, 'ctx': t[:90],
                'title': t[:90], 'host': urllib.parse.urlparse(pu).netloc,
                'origin': '公开图片检索', 'srcTitle': kw, 'note': '',
                'force': [char],
            })
            quota[char] = quota.get(char, 0) + 1
            got += 1
        print(f'  [检索] {char}/{actor} -> {got}', flush=True)
        time.sleep(0.3)
    return out


def download(cands, existing):
    seen, results, rejects = set(existing), [], []
    def dl(it):
        for u in [it['url'], it.get('thumb', '')]:
            if not u or not u.startswith('http'):
                continue
            try:
                b = get(u, 18, referer=it.get('page') or 'https://www.bing.com/', binary=True)
            except Exception:
                continue
            ext = sniff(b)
            if not ext or ext == 'gif' or len(b) < 8000:
                continue
            d = dims(b, ext)
            if not d or min(d) < 200 or max(d) < 300:
                continue
            w, h = d
            if not (0.3 < w / h < 3.6):
                continue
            return dict(it, data=b, ext=ext, w=w, h=h, dlurl=u)
        return None
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
            if n % 100 == 0:
                print(f'  ...已处理 {n}/{len(cands)}，可用 {len(results)}', flush=True)
    return results, rejects


def save(results):
    """增量保存：已有 web_manifest.json 视为本脚本既有成果，新图从后续编号续写。
    重复运行不会产生覆盖，也不会把同一张图再收一遍。"""
    mf_path = os.path.join(TMP, 'web_manifest.json')
    manifest = json.load(open(mf_path, encoding='utf-8')) if os.path.exists(mf_path) else []
    # 按「磁盘上最大编号」续写，而不是「记录条数」。剔除过图片后编号会有空洞，
    # 若按条数续写会覆盖仍在使用中的旧文件（v2.2 曾因此覆盖 31 张，见 fix_numbering.py）。
    mx = 0
    for x in manifest:
        m = re.match(r'web-(\d{4})', x.get('file', ''))
        if m:
            mx = max(mx, int(m.group(1)))
    for f in os.listdir(DEST):
        m = re.match(r'web-(\d{4})\.', f)
        if m:
            mx = max(mx, int(m.group(1)))
    start = mx + 1
    for h, r in sorted(results, key=lambda x: (x[1]['origin'], x[1]['title'])):
        name = f'web-{start:04d}.{r["ext"]}'
        open(os.path.join(DEST, name), 'wb').write(r['data'])
        if r.get('force'):
            chars, mode = r['force'], '检索关键词（未逐张核对）'
        else:
            chars, mode = who(r['ctx'])
        manifest.append({
            'id': 'w' + str(start).zfill(4),
            'file': name,
            'char': '、'.join(chars) if chars else '剧组 · 花絮',
            'actor': '',
            'kind': kind_of((r['ctx'] or '') + r['title']),
            'desc': make_desc(r['ctx'], r['title']),
            'host': r['host'],
            'srcUrl': r['page'],
            'date': TODAY,
            'origin': r['origin'],
            'title': r['title'],
            'source': r['dlurl'],
            'note': r.get('note', ''),
            'matched': mode != '未判定',
            'attribution': mode,
            'w': r['w'], 'h': r['h'],
            'ctx': r.get('ctx', ''),                 # 保留原始配文，供 --reindex 重算归属
            **({'force': r['force']} if r.get('force') else {}),
        })
        start += 1
    json.dump(manifest, open(mf_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return manifest


def build_js(manifest):
    items = []
    for m in manifest:
        p = {k: v for k, v in m.items()
             if k not in ('matched', 'w', 'h', 'note', 'source', 'ctx', 'force')}
        p['source'] = m.get('source', '')  # 原始图片地址，用于复核
        cap = clean_caption(m.get('ctx', ''))
        if cap:
            p['caption'] = cap               # 原文逐图说明，供灯箱/详情展示
        # 「逐图标签」易被误读为已人工核对，统一改成说明性措辞
        if p.get('attribution') == '逐图标签':
            p['attribution'] = '原文配文'
        stem = os.path.splitext(m['file'])[0]
        t = 'webt-' + stem.replace('web-', '') + '.jpg'
        if os.path.exists(os.path.join(DEST, t)):
            p['thumb'] = t
        else:
            p.pop('thumb', None)
        items.append(p)
    out = ('/* 网络补采图库（由 scripts/fetch_web_photos.py 生成，请勿手工编辑）\n'
           ' * 来源：微信公众号图文、公开图文页、公开图片检索。共 ' + str(len(items)) + ' 张。\n'
           ' * 每张保留原文页面 srcUrl、出处站点/公众号 host、文章标题 title、\n'
           ' * 原始图片地址 source、采集日期 date 与紧邻配文（写入 desc）。\n'
           ' * 人物由配文中的角色名/演员名推断；无法判定者记为「剧组 · 花絮」，不强行归属。\n'
           ' * 图片版权归原权利人所有，本站仅作资料整理与本地展示。\n'
           ' */\n'
           'window.HLM87 = window.HLM87 || {};\n'
           'window.HLM87.webPhotos = [\n' +
           ',\n'.join('  ' + json.dumps(p, ensure_ascii=False) for p in items) +
           '\n];\n')
    open(os.path.join(ROOT, 'data', 'photos-web.js'), 'w', encoding='utf-8').write(out)
    return len(items)


def reindex():
    """不重新下载，只按最新归属规则重算 char/kind/desc（用于规则调整后的纠错）。"""
    mf_path = os.path.join(TMP, 'web_manifest.json')
    manifest = json.load(open(mf_path, encoding='utf-8'))
    cp = os.path.join(TMP, 'web_candidates.json')
    by_url = {}
    if os.path.exists(cp):
        for c in json.load(open(cp, encoding='utf-8')):
            by_url[c['url']] = c
    for m in manifest:
        ctx = m.get('ctx', '')
        if not ctx and not m.get('force'):
            c = by_url.get(m.get('source', ''))
            ctx = c.get('ctx', '') if c else ''
        m['ctx'] = ctx
        if m.get('force'):
            chars, mode = m['force'], '检索关键词（未逐张核对）'
        else:
            chars, mode = who(ctx)
        m['char'] = '、'.join(chars) if chars else '剧组 · 花絮'
        m['kind'] = kind_of(ctx + m['title'])
        m['desc'] = make_desc(ctx, m['title'])
        m['matched'] = mode != '未判定'
        m['attribution'] = mode
    json.dump(manifest, open(mf_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    n = build_js(manifest)
    hit = sum(1 for x in manifest if x['matched'])
    print(f'重新归属 {n} 张：精确归属 {hit} 张，「剧组 · 花絮」 {n-hit} 张')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0, help='只处理前 N 个图文源（试跑用）')
    ap.add_argument('--skip', type=int, default=0, help='跳过前 N 个已采集的图文源（增量用）')
    ap.add_argument('--bing', action='store_true', help='追加定向图片检索')
    ap.add_argument('--build-only', action='store_true', help='只重建 JS，不重新采集')
    ap.add_argument('--reindex', action='store_true', help='按最新规则重算人物归属，不重新下载')
    args = ap.parse_args()

    if args.reindex:
        reindex()
        return
    if args.build_only:
        mf = os.path.join(TMP, 'web_manifest.json')
        manifest = json.load(open(mf, encoding='utf-8'))
        print('重建 data/photos-web.js：', build_js(manifest), '条')
        return

    sources = json.load(open(os.path.join(ROOT, 'scripts', 'sources.json'), encoding='utf-8'))['sources']
    if args.skip:
        sources = sources[args.skip:]
    if args.limit:
        sources = sources[:args.limit]
    print(f'人物词表：{len(NAMES)} 人 / {len(KEYS)} 个关键词；本轮图源 {len(sources)} 个', flush=True)

    existing = existing_hashes()
    print(f'已有图片哈希 {len(existing)} 个（用于跨源去重）', flush=True)
    cands = collect_from_pages(sources, existing)
    if args.bing:
        cands += collect_from_bing()
    # 同一原始图片地址只下一次
    uniq, seen_url = [], set()
    for c in cands:
        if c['url'] in seen_url:
            continue
        seen_url.add(c['url'])
        uniq.append(c)
    print(f'候选图片 {len(cands)} -> URL 去重后 {len(uniq)}', flush=True)
    json.dump(uniq, open(os.path.join(TMP, 'web_candidates.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)

    results, rejects = download(uniq, existing)
    print(f'下载可用 {len(results)} 张，过滤/失败 {len(rejects)} 张', flush=True)
    json.dump(rejects, open(os.path.join(TMP, 'web_rejects.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    manifest = save(results)
    print('写入图库记录', build_js(manifest), '条 -> data/photos-web.js', flush=True)
    hit = sum(1 for m in manifest if m['matched'])
    print(f'其中按配文成功归属人物 {hit} 张，其余 {len(manifest)-hit} 张记为「剧组 · 花絮」', flush=True)
    by = {}
    for m in manifest:
        by[m['origin']] = by.get(m['origin'], 0) + 1
    print('分渠道：', by, flush=True)


if __name__ == '__main__':
    main()
