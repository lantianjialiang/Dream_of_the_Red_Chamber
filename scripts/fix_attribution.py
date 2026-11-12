# -*- coding: utf-8 -*-
"""纠正网络补采图片的人物归属（v2.4）。

起因：公众号 / 图文页常用「图片在上、图注在下」排版，图注以 ▲ 开头；
旧采集器 extract_pairs() 取的是图片**之前**的最后一段文字，导致整组图
整体向前错一位——「▲薛宝钗定妆照」组的照片被标成上一组「贾宝玉定妆照」。

本脚本：
  1. 重新抓取 scripts/sources.json 里所有图文页，按 DOM 顺序建立
     「原图 URL -> (前文, 后文)」映射；
  2. ▲ 开头的短图注取「后文」，▽ 结尾的图注取「前文」，长段落一律不归属；
  3. 加固归属规则：只有短图注（<=40 字）可归 1-3 位人物，其余记「剧组 · 花絮」；
  4. 应用 scripts/attribution_fixes.json 的人工目检修正；
  5. 重建 _tmp/web_manifest.json 与 data/photos-web.js（不重新下载图片）。

用法： python scripts/fix_attribution.py [--dry]
"""
import os, sys, re, json, time, urllib.request, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.path.join(ROOT, '_tmp')
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import fetch_web_photos as F  # noqa: E402

MF = os.path.join(TMP, 'web_manifest.json')
FIX = os.path.join(ROOT, 'scripts', 'attribution_fixes.json')
SRC = os.path.join(ROOT, 'scripts', 'sources.json')
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
      'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
IMG = re.compile(r'(<img\b[^>]*>)', re.I)
TAG = re.compile(r'<[^>]+>')


def norm(u):
    """原图 URL 归一化：忽略协议、query 中易变的参数，保留路径主体。"""
    u = re.sub(r'^https?://', '', u or '')
    u = u.split('#')[0]
    # mmbiz 图床的 /0?wx_fmt= 之类后缀可去掉
    u = re.sub(r'\?.*$', '', u)
    return u


def clean(x):
    x = TAG.sub(' ', x).replace('&nbsp;', ' ').replace('&amp;', '&')
    return re.sub(r'\s+', ' ', x).strip()


def body_of(doc, kind):
    if kind == 'weixin':
        i = doc.find('id="js_content"')
        if i > 0:
            gt = doc.find('>', i)
            i = gt + 1 if gt > i else i
            j = doc.find('id="js_pc_qr_code"', i)
            return doc[i:(j if j > i else i + 500000)]
    for marker in ('id="article-content"', 'class="article-content"',
                   'id="content"', 'class="post_body"', 'id="js_content"'):
        i = doc.find(marker)
        if i > 0:
            return doc[i:i + 400000]
    return doc[:500000]


def tokens(url, kind):
    req = urllib.request.Request(url, headers={
        'User-Agent': UA, 'Accept-Language': 'zh-CN,zh;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,image/avif,image/webp,*/*'})
    with urllib.request.urlopen(req, timeout=30) as r:
        doc = r.read().decode('utf-8', 'ignore')
    body = body_of(doc, kind)
    seq = []
    for t in IMG.split(body):
        if t.startswith('<img'):
            m = re.search(r'data-src="([^"]+)"', t) or re.search(r'\bsrc="([^"]+)"', t)
            if m:
                seq.append(('IMG', urllib.parse.urljoin(url, m.group(1))))
        else:
            c = clean(t)
            if c:
                seq.append(('TXT', c[:200]))
    return seq


def neighbors(seq):
    """每张图 -> (最近的前文, 最近的后文)。连续多图共用同一段图注。"""
    out, last = {}, ''
    for k, (kind, val) in enumerate(seq):
        if kind == 'TXT':
            last = val
            continue
        nxt = next((seq[x][1] for x in range(k + 1, len(seq)) if seq[x][0] == 'TXT'), '')
        out.setdefault(norm(val), {'prev': last, 'next': nxt})
    return out


def is_short_label(t):
    return bool(t) and len(t) <= 40 and not re.search(r'style=|id=|class=|<|>', t)


def choose_ctx(prev, nxt):
    """返回 (新配文, 说明)。判定不了就返回空配文，绝不沿用长段落。"""
    p, n = (prev or '').strip(), (nxt or '').strip()
    # ▲ / △ / 「上图」：图注写在图片之后，正确配文是后文
    if re.match(r'^[▲△]', n) and is_short_label(n):
        return n, '后文图注(▲)'
    # ▽ / 「下图」：图注写在图片之前
    if re.search(r'[▽▼]', p) and is_short_label(p):
        return p, '前文图注(▽)'
    # 短图注优先取后文；前文仅在后文是长段落时兜底
    if is_short_label(n) and F.who(n)[0]:
        return n, '后文短图注'
    if is_short_label(p) and F.who(p)[0] and not is_short_label(n):
        return p, '前文短图注'
    return '', '无可判定逐图配文'


def who2(ctx):
    """加固版归属：只有短图注才允许归到具体人物。"""
    if not ctx or not is_short_label(ctx):
        return [], '未判定'
    chars, _mode = F.who(ctx)
    if not chars:
        return [], '未判定'
    if len(chars) >= 4:
        return [], '未判定'
    # 短图注里若出现「等」「以及」「合影」等罗列词，降级
    if re.search(r'等|以及|合影|众人|全家福|大合影|群芳', ctx):
        if len(chars) >= 3:
            return [], '未判定'
    return chars[:3], '原文配文'


def main():
    dry = '--dry' in sys.argv
    mf = json.load(open(MF, encoding='utf-8'))
    sources = json.load(open(SRC, encoding='utf-8'))['sources']
    type_by_url = {s['url'].split('#')[0]: s['type'] for s in sources}

    pages = sorted({m['srcUrl'] for m in mf if m['origin'] != '公开图片检索'})
    print(f'图文页 {len(pages)} 个，待复核图片 '
          f'{sum(1 for m in mf if m["origin"] != "公开图片检索")} 张', flush=True)
    mapping, failed = {}, []
    for i, p in enumerate(pages, 1):
        try:
            kind = type_by_url.get(p.split('#')[0], 'web')
            mp = neighbors(tokens(p, kind))
            for k, v in mp.items():
                mapping.setdefault(k, v)
            print(f'  [{i}/{len(pages)}] {kind} 图片 {len(mp)} 张', flush=True)
        except Exception as e:
            failed.append(p)
            print(f'  [{i}/{len(pages)}] 失败 {repr(e)[:80]}', flush=True)
        time.sleep(0.2)
    print(f'页面映射 {len(mapping)} 条原图 URL，失败页面 {len(failed)} 个', flush=True)

    fixes = json.load(open(FIX, encoding='utf-8')) if os.path.exists(FIX) else {}
    by_id = {m['id']: m for m in mf}
    stats = {'重配': 0, '降级': 0, '人工修正': 0, '未匹配': 0, '检索保留': 0}
    for m in mf:
        if m['origin'] == '公开图片检索':
            # 定向检索保留关键词归属，但统一标注为「检索关键词 · 未逐张核对」
            m['attribution'] = '检索关键词（未逐张核对）'
            stats['检索保留'] += 1
        else:
            info = mapping.get(norm(m.get('source', '')))
            if info:
                ctx, why = choose_ctx(info['prev'], info['next'])
                if ctx != (m.get('ctx') or ''):
                    stats['重配'] += 1
                m['ctx'] = ctx
                cap = F.clean_caption(ctx)
                if cap:
                    m['caption'] = cap
                else:
                    m.pop('caption', None)
                m['desc'] = F.make_desc(ctx, m['title'])
                chars, mode = who2(ctx)
                m['char'] = '、'.join(chars) if chars else '剧组 · 花絮'
                m['matched'] = mode != '未判定'
                m['attribution'] = mode
                m['kind'] = F.kind_of(ctx + m['title'])
                if mode == '未判定':
                    stats['降级'] += 1
            else:
                # 页面抓不到就保守降级，不再沿用可能错位的旧配文
                stats['未匹配'] += 1
                m['ctx'] = ''
                m.pop('caption', None)
                m['desc'] = '《' + m['title'] + '》'
                m['char'] = '剧组 · 花絮'
                m['matched'] = False
                m['attribution'] = '未判定'
        # 人工目检修正表（最高优先级，覆盖自动结果）
        fix = fixes.get(m['id'])
        if fix:
            m['char'] = fix.get('char', m['char'])
            m['attribution'] = fix.get('attribution', '人工目检')
            if fix.get('note'):
                m['caption'] = fix['note']
                m['desc'] = fix['note'] + ' · 《' + m['title'] + '》'
            m['matched'] = True
            stats['人工修正'] += 1
    print('统计', json.dumps(stats, ensure_ascii=False), flush=True)
    if dry:
        print('DRY RUN：未写文件')
        return
    json.dump(mf, open(MF, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('重建 data/photos-web.js：', F.build_js(mf), '条')


if __name__ == '__main__':
    main()
