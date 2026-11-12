# -*- coding: utf-8 -*-
"""把《1987，我们的红楼梦》（欧阳奋强 著，2017）文字版拆成一材料，
按人物并入各册已有的 behind（幕后细节）/ quotes（她说）字段。

原则：
  1. 只摘原书现成句子，不改写、不补写、不推测；截断处加「……」。
  2. 每条 src 写明书名、年份与章节，可在 data/books/text/ 的文字书籍里核查。
  3. quotes 只收书中明确以第一人称自述的引语，from 注明「欧阳奋强记述」，
     避免被误读为演员直接接受本站采访。
  4. 不新增页面 / 板块 / 按钮；产出仅为 nverce/data/memoir.js，
     由 index.html 在运行时追加到 window.BOOKS。
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'data/books/text/1987我们的红楼梦-欧阳奋强.md')
OUT = os.path.join(ROOT, 'nverce/data/memoir.js')

# 原书章节标题 → 人物册 id（与 nverce/data/bridge.js 一致）
MAP = {
    '林黛玉 陈晓旭': 'daiyu',
    '薛宝钗 张莉': 'baochai',
    '王熙凤 邓婕': 'xifeng',
    '元春 成梅': 'yuanchun',
    '迎春 金莉莉': 'yingchun',
    '迎春 牟一': 'yingchun',
    '探春 东方闻樱': 'tanchun',
    '惜春 胡泽红': 'xichun',
    '史湘云 郭霄珍': 'xiangyun',
    '妙玉 姬培杰（姬玉）': 'miaoyu',
    '秦可卿 张蕾': 'keqing',
    '李纨 孙梦泉': 'liwan',
    '袭人 袁玫': 'xiren',
    '晴雯 张静林（安雯）': 'qingwen',
    '平儿 沈琳': 'pinger',
    '香菱 陈剑月': 'xiangling',
    '紫鹃 徐丽霞': 'zijuan',
    '鸳鸯 郑铮': 'yuanyang',
    '贾母 李婷': 'jiamu',
    '尤三姐 周月': 'yousanjie',
}

BOOK = '欧阳奋强《1987，我们的红楼梦》（2017）'
PROMO = re.compile(r'读累了|休息一会|充值|VIP|电子书|二维码|关注我们|版权所有')
QUOTE = re.compile(r'[「“]([^」”]{12,90})[」”]')


def clean(p):
    p = re.sub(r'\s+', ' ', p).strip()
    if p.startswith('### '):
        return p
    if not p or p.startswith('#') or p.startswith('>') or p.startswith('---'):
        return ''
    if PROMO.search(p):
        return ''
    return p


def cut(text, limit=190):
    """在句号/分号处截断，保留原句。"""
    if len(text) <= limit:
        return text
    s = text[:limit]
    for mark in ('。', '！', '？', '；'):
        i = s.rfind(mark)
        if i >= limit - 55:
            return s[:i + 1] + '……'
    return s + '……'


def chapter_blocks(md):
    """返回 [(章节标题, 正文段落列表)]。"""
    out = []
    for block in re.split(r'(?m)^## ', md)[1:]:
        head, _, body = block.partition('\n')
        head = head.strip()
        paras = [clean(x) for x in body.split('\n')]
        out.append((head, [x for x in paras if x]))
    return out


def split_sections(paras, chapter):
    """按 ### 小标题切段；无小标题的短章按每 3 段一块切成 2–3 条。"""
    if not any(p.startswith('### ') for p in paras):
        out = []
        for i, start in enumerate(range(0, min(len(paras), 9), 3)):
            title = chapter + ('', ' · 续', ' · 续二')[i]
            out.append((title, paras[start:start + 3]))
        return out
    sections, cur_title, cur = [], None, []
    for p in paras:
        if p.startswith('### '):
            if cur:
                sections.append((cur_title or chapter, cur))
            cur_title, cur = p[4:].strip(), []
        else:
            cur.append(p)
    if cur:
        sections.append((cur_title or chapter, cur))
    return sections


def main():
    md = open(SRC, encoding='utf-8').read()
    chapters = chapter_blocks(md)
    data, stat = {}, {}

    for head, paras in chapters:
        pid = MAP.get(head)
        if not pid:
            continue
        item = data.setdefault(pid, {'behind': [], 'quotes': []})
        src = BOOK + '·〈' + head + '〉'
        from_ = BOOK + '·〈' + head + '〉，欧阳奋强记述'

        for title, body in split_sections(paras, head):
            if len(item['behind']) >= 3:
                break
            text = cut(''.join(body[:3]))
            if len(text) < 40:
                continue
            item['behind'].append({'title': title, 'text': text, 'src': src})

        # 第一人称自述引语（明确带「我 / 我们」）
        for p in paras:
            if len(item['quotes']) >= 2:
                break
            for q in QUOTE.findall(p):
                # 只收成段的自述，滤掉「我刚有事完」这类零星对话
                if '我' not in q or len(q) < 22 or PROMO.search(q):
                    continue
                if any(q == x['t'] for x in item['quotes']):
                    continue
                item['quotes'].append({'t': q, 'from': from_})
                break

        stat[pid] = (len(item['behind']), len(item['quotes']))

    header = (
        '/* ============================================================\n'
        ' * 回忆录一手材料 · 由 scripts/memoir_to_stories.py 生成，勿手工编辑\n'
        ' * 来源：欧阳奋强《1987，我们的红楼梦》（2017），文字版见\n'
        ' *       data/books/text/1987我们的红楼梦-欧阳奋强.md\n'
        ' * 说明：仅摘原书现成句子，逐条标注章节；quotes 为书中所记的\n'
        ' *       第一人称自述，非本站采访。运行时追加到各人物册已有的\n'
        ' *       「幕后细节」「她说」，不新增页面或板块。\n'
        ' * ============================================================ */\n'
    )
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(header + 'window.MEMOIR = ' +
                json.dumps(data, ensure_ascii=False, indent=2) + ';\n')

    print('生成', OUT)
    print('覆盖人物册', len(data), '/ 21；幕后条目',
          sum(v[0] for v in stat.values()), '；语录', sum(v[1] for v in stat.values()))


if __name__ == '__main__':
    main()
