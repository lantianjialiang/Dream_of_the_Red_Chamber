# -*- coding: utf-8 -*-
"""把「当事人回忆录 + 纪念画册」的可用图片并入主站图库。

两类来源：
  A. 欧阳奋强《1987，我们的红楼梦》精排 EPUB 内嵌插图（bk-*.jpg）
     —— 依据 book_to_text.py 生成的 _tmp/book_images_index.json，
        人物归属来自原书 h2 章节标题与 <div class="title_pic"> 逐图图注。
  B. 李耀宗《1987，我们的红楼梦》纪念画册上/下册扫描页（bkp-*.jpg）
     —— 从 PDF 直接抽出的整页 JPEG；封面/版权/目录/纯文字/章节扉页已目检剔除。
        整页含多张照片与版面文字，不强行归属具体人物，一律记「剧组 · 花絮」。

产出： data/photos-book.js（window.HLM87.bookPhotos）
       _tmp/thumb_jobs.json（供 make_thumbs_generic.py 生成缩略图）

用法： python scripts/import_book_photos.py
"""
import os, re, json, glob, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(ROOT, 'assets', 'photos')
TMP = os.path.join(ROOT, '_tmp')
DATE = '2026-11-12'

EPUB_BOOK = '《1987，我们的红楼梦》· 欧阳奋强 著（2017 精排电子版）'
EPUB_MD = 'data/books/text/1987我们的红楼梦-欧阳奋强.md'
ALBUM_BOOK = '《1987，我们的红楼梦》纪念画册 · 李耀宗 摄影 · 中国轻工业出版社 2018'

# 目检剔除：上册 1-8 为封面/版权/序/目录/纯文字；上-134、下-117 为章节扉页；
# 下-138~144 为人名索引/版权/封底。
SKIP_PAGES = set('上-%03d' % i for i in range(1, 9)) | {'上-134', '下-117'} | \
    set('下-%03d' % i for i in range(138, 145))


def main():
    items, jobs = [], []
    # 按画面目检修正的归属说明（scripts/exclude.json 的 reassign 字段）
    ra = json.load(open(os.path.join(ROOT, 'scripts', 'exclude.json'), encoding='utf-8')).get('reassign', {})
    # ---------------- A. 回忆录插图 ----------------
    idx = json.load(open(os.path.join(TMP, 'book_images_index.json'), encoding='utf-8'))
    n = 0
    for r in idx:
        if not r.get('kept'):
            continue
        n += 1
        stem = os.path.splitext(r['out'])[0]
        thumb = 'bkt-' + stem.replace('bk-', '') + '.jpg'
        cap = r.get('caption') or ''
        chapter = r.get('h2') or '序章'
        chars = r.get('char') or []
        cap_short = (cap[:56] + '…') if len(cap) > 56 else cap
        bid = 'bk' + str(n).zfill(4)
        rule = ra.get(bid, {})
        items.append({
            'id': bid,
            'file': r['out'],
            'thumb': thumb,
            'char': '、'.join(chars) if chars else '剧组 · 花絮',
            'actor': '',
            'kind': '生活照' if re.search(r'合影|幕后|生活|聚会|重聚', cap) else '剧照',
            'desc': (cap_short or chapter) + ' · ' + EPUB_BOOK,
            'host': EPUB_BOOK,
            'srcUrl': EPUB_MD,
            'date': DATE,
            'origin': '回忆录插图',
            'title': chapter,
            'caption': cap or '（原书未附图注，见「' + chapter + '」章）',
            'attribution': rule.get('attribution') or ('原书章节与图注' if chars else '原书图注（未判定人物）'),
            'book': EPUB_BOOK,
            'chapter': chapter,
            'source': 'EPUB/' + r['src'].split('EPUB/')[-1],
        })
        jobs.append({'src': r['out'], 'out': thumb})
    print('回忆录插图', n, '张', flush=True)

    # ---------------- B. 纪念画册扫描页 ----------------
    pages = json.load(open(os.path.join(TMP, 'book_pages', 'index.json'), encoding='utf-8'))
    pdfname = {}
    for r in pages:
        pdfname[r['volume']] = r['source_pdf']
    m = 0
    kept = 0
    for r in pages:
        stem = r['volume'] + '-' + str(r['page']).zfill(3)
        if stem in SKIP_PAGES:
            m += 1
            continue
        kept += 1
        fname = f'bkp-{kept:04d}.jpg'
        src = os.path.join(TMP, 'book_pages', r['file'])
        shutil.copyfile(src, os.path.join(DEST, fname))
        thumb = 'bkpt-' + str(kept).zfill(4) + '.jpg'
        label = r['book'] + ' 第 ' + str(r['page']) + ' 页'
        items.append({
            'id': 'bp' + str(kept).zfill(4),
            'file': fname,
            'thumb': thumb,
            'char': '剧组 · 花絮',
            'actor': '',
            'kind': '画册内页',
            'desc': label + '（整页扫描，含多帧剧照/幕后照与版面文字） · 李耀宗 摄影',
            'host': ALBUM_BOOK,
            'srcUrl': 'data/books/' + pdfname[r['volume']],
            'date': DATE,
            'origin': '纪念画册扫描',
            'title': label,
            'caption': label,
            'attribution': '画册内页（未逐张归属人物）',
            'book': ALBUM_BOOK,
            'page': stem,
            'source': r['source_pdf'] + '#' + stem,
        })
        jobs.append({'src': fname, 'out': thumb})
    print('画册扫描页：收录', kept, '页，剔除', m, '页（封面/文字/扉页）', flush=True)

    out = ('/* 书籍图库（由 scripts/import_book_photos.py 生成，请勿手工编辑）\n'
           ' * A. 欧阳奋强《1987，我们的红楼梦》精排 EPUB 插图 ' + str(n) + ' 张：\n'
           ' *    人物归属依据原书章节标题与逐图图注，文字书籍见 data/books/text/。\n'
           ' * B. 李耀宗《1987，我们的红楼梦》纪念画册扫描页 ' + str(kept) + ' 页：\n'
           ' *    整页扫描含多帧照片与版面文字，不强行归属具体人物；\n'
           ' *    封面、版权、目录、纯文字页与章节扉页已目检剔除。\n'
           ' * 每张保留书名、章节/页码、原文件路径 srcUrl 与采集日期。\n'
           ' * 图片版权归原权利人所有，本站仅作资料整理与本地展示。\n'
           ' */\n'
           'window.HLM87 = window.HLM87 || {};\n'
           'window.HLM87.bookPhotos = [\n' +
           ',\n'.join('  ' + json.dumps(p, ensure_ascii=False) for p in items) +
           '\n];\n')
    open(os.path.join(ROOT, 'data', 'photos-book.js'), 'w', encoding='utf-8').write(out)
    json.dump(jobs, open(os.path.join(TMP, 'thumb_jobs.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('合计', len(items), '条 -> data/photos-book.js；缩略图任务', len(jobs), '条')


if __name__ == '__main__':
    main()
