# -*- coding: utf-8 -*-
"""把《1987，我们的红楼梦》（欧阳奋强，精排 EPUB）整理成文字书籍 + 图片索引。

产出：
  data/books/text/1987我们的红楼梦-欧阳奋强.md   章节化简体中文文字书籍
  assets/photos/bk-NNNN.jpg                       书中可用插图（>=400px）
  _tmp/book_images_index.json                     逐图出处/章节/人物归属索引
  data/photos-book.js                            可直接并入主站图库的数据

用法： python scripts/book_to_text.py [--text-only]
"""
import os, re, sys, json, html, zipfile, glob, hashlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(ROOT, 'assets', 'photos')
TXT = os.path.join(ROOT, 'data', 'books', 'text')
TMP = os.path.join(ROOT, '_tmp')
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import fetch_web_photos as F  # noqa: E402

EPUB = glob.glob(os.path.join(ROOT, 'data', 'books', '*.epub'))[0]
BOOK = '《1987，我们的红楼梦》'
AUTHOR = '欧阳奋强 著（chenjin5.com 精排电子版，2017）'
MDNAME = '1987我们的红楼梦-欧阳奋强.md'
DATE = '2026-11-12'

TOKEN = re.compile(
    r'(<h[1-4][^>]*>.*?</h[1-4]>|<p\b[^>]*>.*?</p>|'
    r'<div\b[^>]*class="title_pic"[^>]*>.*?</div>|<img\b[^>]*>)', re.I | re.S)
TITLE_PIC = re.compile(r'<div\b[^>]*class="title_pic"[^>]*>(.*?)</div>', re.I | re.S)
PROMO = re.compile(r'kindle精品汇|至臻阅读|想用kindle|关注这个微信号|微信号[:：]|'
                   r'精品图书|chenjin5|万千书友')
IMG_SRC = re.compile(r'<img[^>]+src="([^"]+)"', re.I)
H = re.compile(r'<h([1-4])[^>]*>(.*?)</h\1>', re.I | re.S)


def text_of(s):
    s = re.sub(r'<br\s*/?>', ' ', s, flags=re.I)
    s = re.sub(r'<[^>]+>', '', s)
    s = html.unescape(s).replace('\r', ' ').replace('\x13', ' ')
    return re.sub(r'\s+', ' ', s).strip()


def dims(b):
    return F.dims(b, F.sniff(b) or '') if F.sniff(b) else None


def person_from_heading(h2, caption):
    """h2 形如「贾宝玉 欧阳奋强」；图注可补充同框人物。"""
    chars = []
    if h2:
        hit = F.who(h2)[0]
        # h2 里同时出现角色与演员，通常解析出 1 个角色
        for c in hit:
            if c not in chars:
                chars.append(c)
    for c in F.who(caption or '')[0]:
        if c not in chars and len(chars) < 3:
            chars.append(c)
    if re.search(r'篇章|序|附录|后记|鸣谢', h2 or ''):
        return []
    return chars[:3]


def main():
    text_only = '--text-only' in sys.argv
    os.makedirs(TXT, exist_ok=True)
    z = zipfile.ZipFile(EPUB)
    opf = z.read('EPUB/content.opf').decode('utf-8', 'ignore')
    # OPF 里属性顺序不固定（href 常在 id 之前），逐个 item 解析
    idmap = {}
    for tag in re.findall(r'<item\b[^>]*>', opf):
        i = re.search(r'\bid="([^"]+)"', tag)
        h = re.search(r'\bhref="([^"]+)"', tag)
        if i and h:
            idmap[i.group(1)] = h.group(1)
    spine = re.findall(r'<itemref[^>]*idref="([^"]+)"', opf)
    files = [('EPUB/' + idmap[i].lstrip('/')) for i in spine if i in idmap]

    md = ['# 1987，我们的红楼梦', '',
          f'> 欧阳奋强 著 · 2017 年精排电子版整理 · 内部资料，仅供本站故事考据引用',
          f'> 原始文件：`data/books/{os.path.basename(EPUB)}`',
          f'> 整理日期：{DATE}；本站按原书章节顺序转为纯文字，图片另存图库并标注章节。', '']
    index, n_img, seen_hash = [], 0, set()
    chapter_no = 0
    for fi, name in enumerate(files):
        if name not in z.namelist():
            continue
        doc = z.read(name).decode('utf-8', 'ignore')
        h1 = h2 = h3 = ''
        pending = []          # 等待图注的图片索引
        for tok in TOKEN.findall(doc):
            low = tok.lower()
            if low.startswith('<h'):
                m = H.match(tok)
                if m:
                    lvl, t = int(m.group(1)), text_of(m.group(2))
                    if not t:
                        continue
                    if lvl == 1:
                        h1 = t
                        md += ['', '# ' + t, '']
                    elif lvl == 2:
                        h2, h3 = t, ''
                        chapter_no += 1
                        md += ['', '## ' + t, '']
                    elif lvl == 3:
                        h3 = t
                        md += ['', '### ' + t, '']
                    else:
                        md += ['', '#### ' + t, '']
                continue
            if low.startswith('<img'):
                m = IMG_SRC.search(tok)
                if not m:
                    continue
                src = os.path.normpath(os.path.join(os.path.dirname(name), m.group(1))).replace('\\', '/')
                rec = {'src': src, 'h1': h1, 'h2': h2, 'h3': h3, 'file': fi,
                       'caption': '', 'char': [], 'kept': False}
                index.append(rec)
                pending.append(rec)
                continue
            # 原书图注：紧跟在插图后的 <div class="title_pic">
            if low.startswith('<div') and 'title_pic' in low:
                t = text_of(TITLE_PIC.search(tok).group(1) if TITLE_PIC.search(tok) else tok)
                if pending:
                    for rec in pending:
                        rec['caption'] = t
                    pending = []
                if t:
                    md += ['', '> 〔插图〕' + t, '']
                continue
            t = text_of(tok)
            pending = []          # 图注必须紧跟插图，否则不再回溯配对
            if not t or PROMO.search(t):
                continue
            md += ['', t, '']

    print('章节', chapter_no, '个，正文段落', sum(1 for x in md if x and not x.startswith('#')),
          '，图片引用', len(index), flush=True)
    md += ['', '---', '',
           '## 整理说明', '',
           f'- 来源：{BOOK}{AUTHOR}。',
           '- 本站仅按原书章节顺序重排为纯文本，未改动原文措辞；明显排版空白已合并。',
           '- 原书插图已按所在章节标注来源，收录于本站图库；图片版权归原权利人所有。',
           '- 「宝黛话红楼」（陈晓旭、邓婕、欧阳奋强、王贵娥，花山文艺出版社 1987）'
           '为纯扫描件，本机无可用 OCR 引擎，文字部分暂缺，原书归档保留。', '']
    open(os.path.join(TXT, MDNAME), 'w', encoding='utf-8').write('\n'.join(md))
    print('文字书籍 ->', os.path.join(TXT, MDNAME), flush=True)
    if text_only:
        return

    # 导出可用插图：>=400px、非装饰图、跨书去重
    for rec in index:
        src = rec['src']
        if src not in z.namelist():
            continue
        b = z.read(src)
        d = dims(b)
        if not d or min(d) < 400:
            continue
        hh = hashlib.md5(b).hexdigest()
        if hh in seen_hash:
            continue
        seen_hash.add(hh)
        n_img += 1
        fname = f'bk-{n_img:04d}.jpg'
        # 非 JPEG 的图统一转成 jpg 后缀会损坏，保留原扩展名
        ext = F.sniff(b)
        if ext != 'jpg':
            fname = f'bk-{n_img:04d}.{ext}'
        open(os.path.join(DEST, fname), 'wb').write(b)
        rec['kept'] = True
        rec['out'] = fname
        rec['w'], rec['h'] = d
        chars = person_from_heading(rec['h2'], rec['caption'])
        rec['char'] = chars
    print('导出插图', n_img, '张（>=400px，已按内容去重）', flush=True)
    json.dump(index, open(os.path.join(TMP, 'book_images_index.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('图片索引 -> _tmp/book_images_index.json')


if __name__ == '__main__':
    main()
