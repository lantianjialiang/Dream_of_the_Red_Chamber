# -*- coding: utf-8 -*-
"""从「逐页看图像转录」分片生成《宝黛话红楼》文字书籍与 EPUB3。

输入: _tmp/hy4_pages/part_*.md，每页以 `## PDF 第 N 页` 开头（N=1..260）
输出: data/books/text/宝黛话红楼.md
      data/books/text/宝黛话红楼.epub

分片由多模态模型逐页查看扫描页图像转录，不依赖 OCR 结果。
EPUB 为纯标准库生成的 EPUB3（同时带 toc.ncx 兼容 EPUB2 阅读器）。
用法: python scripts/build_hy4_book.py
"""
import pathlib
import re
import uuid
import zipfile
from datetime import datetime, timezone
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape as xesc

from PIL import Image, ImageOps

SHARDS = pathlib.Path("_tmp/hy4_pages")
OUT_DIR = pathlib.Path("data/books/text")
MD = OUT_DIR / "宝黛话红楼.md"
EPUB = OUT_DIR / "宝黛话红楼.epub"
COVER_SRC = pathlib.Path("_tmp/pdf_pages/baodai/p0001.jpg")
TOTAL = 260

TITLE = "宝黛话红楼"
AUTHORS = ["陈晓旭", "邓婕", "欧阳奋强", "王贵娥"]
PUBLISHER = "花山文艺出版社"
YEAR = "1987"

# (起始 PDF 页, 结束 PDF 页, 卷名)，依据原书目录页（PDF 第 6 页）与篇章标题位置
VOLUMES = [
    (1, 6, "卷首 · 前言与目录"),
    (7, 61, "「选美」纪实 · 王贵娥"),
    (62, 189, "「宝玉」日记 · 欧阳奋强"),
    (190, 225, "梦里三年 · 陈晓旭"),
    (226, 260, "我演凤姐 · 邓婕"),
]

XML_DECL = '<?xml version="1.0" encoding="utf-8"?>\n'
XHTML_OPEN = '<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="zh-CN" lang="zh-CN">\n'
NAV_OPEN = ('<html xmlns="http://www.w3.org/1999/xhtml" '
            'xmlns:epub="http://www.idpf.org/2007/ops" '
            'xml:lang="zh-CN" lang="zh-CN">\n')

STYLE = """body { font-family: "Songti SC", "SimSun", "Noto Serif CJK SC", serif;
  line-height: 1.85; margin: 1.1em 1em; color: #1a1a1a; }
h1, h2 { text-align: center; font-weight: bold; }
h2 { font-size: 1.25em; margin: 1.4em 0 1em; }
p { text-indent: 2em; margin: 0.35em 0; text-align: justify; }
p.pageno { text-indent: 0; font-size: 0.72em; color: #8a8a8a;
  border-top: 1px solid #ddd; margin-top: 1.3em; padding-top: 0.35em; }
p.note { text-indent: 0; color: #666; font-style: italic; }
img.cover { max-width: 100%; height: auto; display: block; margin: 0 auto; }
"""


def load_pages():
    pages = {}
    for f in sorted(SHARDS.glob("part_*.md")):
        text = f.read_text(encoding="utf-8")
        for m in re.finditer(
            r"^## PDF 第 (\d+) 页[ \t]*\n(.*?)(?=^## PDF 第 |\Z)", text, re.S | re.M
        ):
            n = int(m.group(1))
            if n in pages:
                raise SystemExit(f"重复页码 {n}（{f.name}）")
            pages[n] = m.group(2).strip()
    missing = [i for i in range(1, TOTAL + 1) if i not in pages]
    extra = sorted(set(pages) - set(range(1, TOTAL + 1)))
    if missing or extra:
        raise SystemExit(f"页码不完整：missing={missing[:20]} extra={extra[:20]}")
    return pages


def parse_blocks(pages):
    """把每页文本切成 (页码, 类型, 文本)；类型 h=小节标题 / p=正文 / note=插图说明。"""
    blocks = []
    for n in range(1, TOTAL + 1):
        for para in re.split(r"\n\s*\n", pages[n]):
            para = para.strip()
            if not para:
                continue
            if para.startswith("### "):
                blocks.append((n, "h", para[4:].strip()))
            elif para.startswith("_") and para.endswith("_"):
                blocks.append((n, "note", para.strip("_")))
            else:
                blocks.append((n, "p", para))
    return blocks


def build_chapters(blocks):
    chapters = []
    cur = {"title": "卷首", "start": 1, "blocks": []}
    for b in blocks:
        if b[1] == "h":
            if cur["blocks"]:
                chapters.append(cur)
            cur = {"title": b[2], "start": b[0], "blocks": []}
            continue
        cur["blocks"].append(b)
    if cur["blocks"]:
        chapters.append(cur)
    return chapters


def volume_index(page):
    for i, (a, b, _) in enumerate(VOLUMES):
        if a <= page <= b:
            return i
    return len(VOLUMES) - 1


def write_markdown(pages):
    head = [
        f"# {TITLE}",
        "",
        f"> {'、'.join(AUTHORS)} 等著，{PUBLISHER}，{YEAR} 年。",
        f"> 本文由扫描 PDF（{TOTAL} 页、无文字层）**逐页查看页面图像重新识别**整理，共约 10.5 万字。",
        "> 生成脚本：`python scripts/build_hy4_book.py`；逐页转录原稿在 `_tmp/hy4_pages/`（本地保留、不入库）。",
        "> 按原书逐字转录，个别模糊字以「□」标注；引用请以原书扫描页为准。",
        "> 每页以「## PDF 第 N 页」标注，便于与扫描页逐页对照核查。",
        "",
    ]
    body = "\n\n".join(f"## PDF 第 {n} 页\n\n{pages[n]}" for n in range(1, TOTAL + 1))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    MD.write_text("\n".join(head) + "\n" + body + "\n", encoding="utf-8")
    return MD


def chapter_xhtml(chapter):
    out = [XML_DECL, XHTML_OPEN,
           f'<head><title>{xesc(chapter["title"])}</title>'
           '<link rel="stylesheet" type="text/css" href="style.css"/></head>\n<body>\n',
           f'<h2>{xesc(chapter["title"])}</h2>\n']
    last_page = None
    for page, kind, text in chapter["blocks"]:
        if page != last_page:
            out.append(f'<p class="pageno">PDF 第 {page} 页</p>\n')
            last_page = page
        cls = ' class="note"' if kind == "note" else ""
        escaped = xesc(text).replace("\n", "<br/>\n")
        out.append(f"<p{cls}>{escaped}</p>\n")
    out.append("</body>\n</html>\n")
    return "".join(out)


def cover_xhtml():
    return (XML_DECL + XHTML_OPEN +
            '<head><title>封面</title><link rel="stylesheet" type="text/css" href="style.css"/></head>\n'
            '<body>\n<img class="cover" src="cover.jpg" alt="《宝黛话红楼》封面"/>\n'
            "</body>\n</html>\n")


def title_xhtml():
    lines = [XML_DECL, XHTML_OPEN,
             '<head><title>书名页</title><link rel="stylesheet" type="text/css" href="style.css"/></head>\n<body>\n',
             f"<h1>{xesc(TITLE)}</h1>\n"]
    for line in [
        f"{'、'.join(AUTHORS)} 等著",
        f"{PUBLISHER} · {YEAR}",
        "本电子版由 1987 年原书扫描页逐页查看图像转录整理，仅供本地资料检索。",
        "正文保留原书用字与标点，模糊处以「□」标注；每节标注 PDF 页码便于核查。",
    ]:
        lines.append(f'<p style="text-indent:0;text-align:center">{xesc(line)}</p>\n')
    lines.append("</body>\n</html>\n")
    return "".join(lines)


def nav_xhtml(chapters, files):
    out = [XML_DECL, NAV_OPEN,
           '<head><title>目录</title><link rel="stylesheet" type="text/css" href="style.css"/></head>\n<body>\n',
           '<nav epub:type="toc" id="toc"><h1>目　录</h1>\n<ol>\n']
    for vi, (a, b, vname) in enumerate(VOLUMES):
        idxs = [i for i, c in enumerate(chapters) if volume_index(c["start"]) == vi]
        if not idxs:
            continue
        first = files[idxs[0]]
        out.append(f'<li class="vol"><a href="{first}">{xesc(vname)}</a>\n<ol>\n')
        for i in idxs:
            out.append(f'<li class="chap"><a href="{files[i]}">{xesc(chapters[i]["title"])}</a></li>\n')
        out.append("</ol>\n</li>\n")
    out.append("</ol>\n</nav>\n</body>\n</html>\n")
    return "".join(out)


def toc_ncx(chapters, files, uid):
    out = [XML_DECL,
           '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">\n<head>\n',
           f'<meta name="dtb:uid" content="{uid}"/>\n</head>\n',
           f"<docTitle><text>{xesc(TITLE)}</text></docTitle>\n<navMap>\n"]
    play = 1
    for vi, (a, b, vname) in enumerate(VOLUMES):
        idxs = [i for i, c in enumerate(chapters) if volume_index(c["start"]) == vi]
        if not idxs:
            continue
        out.append(f'<navPoint id="vol{vi + 1}" playOrder="{play}">'
                   f'<navLabel><text>{xesc(vname)}</text></navLabel>'
                   f'<content src="{files[idxs[0]]}"/>\n')
        play += 1
        for i in idxs:
            out.append(f'<navPoint id="chap{i + 1}" playOrder="{play}">'
                       f'<navLabel><text>{xesc(chapters[i]["title"])}</text></navLabel>'
                       f'<content src="{files[i]}"/></navPoint>\n')
            play += 1
        out.append("</navPoint>\n")
    out.append("</navMap>\n</ncx>\n")
    return "".join(out)


def content_opf(chapters, files, uid):
    modified = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = [XML_DECL,
           '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="BookId">\n',
           '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n',
           f'<dc:identifier id="BookId">{uid}</dc:identifier>\n',
           f"<dc:title>{xesc(TITLE)}</dc:title>\n",
           "".join(f"<dc:creator>{xesc(a)}</dc:creator>\n" for a in AUTHORS),
           f"<dc:publisher>{xesc(PUBLISHER)}</dc:publisher>\n",
           f"<dc:date>{YEAR}</dc:date>\n<dc:language>zh-CN</dc:language>\n",
           f"<dc:description>{xesc('据 1987 年花山文艺出版社原书扫描页逐页看图像转录整理，含 PDF 页码对照。')}</dc:description>\n",
           f'<meta property="dcterms:modified">{modified}</meta>\n',
           '<meta name="cover" content="cover-image"/>\n</metadata>\n<manifest>\n',
           '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>\n',
           '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>\n',
           '<item id="css" href="style.css" media-type="text/css"/>\n',
           '<item id="cover-image" href="cover.jpg" media-type="image/jpeg" properties="cover-image"/>\n',
           '<item id="cover" href="cover.xhtml" media-type="application/xhtml+xml"/>\n',
           '<item id="titlepage" href="title.xhtml" media-type="application/xhtml+xml"/>\n',
           ]
    for i, f in enumerate(files):
        out.append(f'<item id="ch{i + 1:03d}" href="{f}" media-type="application/xhtml+xml"/>\n')
    out.append('</manifest>\n<spine toc="ncx">\n<itemref idref="cover"/>\n<itemref idref="titlepage"/>\n')
    out.extend(f'<itemref idref="ch{i + 1:03d}"/>\n' for i in range(len(files)))
    out.append('</spine>\n</package>\n')
    return "".join(out)


CONTAINER = (XML_DECL +
             '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
             '<rootfiles><rootfile full-path="OEBPS/content.opf" '
             'media-type="application/oebps-package+xml"/></rootfiles>\n</container>\n')


def build_epub(chapters):
    files = [f"ch{i + 1:03d}.xhtml" for i in range(len(chapters))]
    uid = "urn:uuid:" + str(uuid.uuid5(uuid.NAMESPACE_URL, "hlm87/baodai-huahonglou"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 扫描封面为黑底白字反相图，转正后作为 EPUB 封面
    with Image.open(COVER_SRC) as im:
        cover = ImageOps.invert(im.convert("RGB"))
        cover.save(OUT_DIR / "_cover_positive.jpg", "JPEG", quality=88)
    cover_bytes = (OUT_DIR / "_cover_positive.jpg").read_bytes()
    (OUT_DIR / "_cover_positive.jpg").unlink()

    with zipfile.ZipFile(EPUB, "w") as z:
        # mimetype 必须是第一个条目且不压缩
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", CONTAINER, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/content.opf", content_opf(chapters, files, uid),
                   compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/nav.xhtml", nav_xhtml(chapters, files), compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/toc.ncx", toc_ncx(chapters, files, uid), compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/style.css", STYLE, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/cover.xhtml", cover_xhtml(), compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/title.xhtml", title_xhtml(), compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/cover.jpg", cover_bytes, compress_type=zipfile.ZIP_DEFLATED)
        for name, ch in zip(files, chapters):
            z.writestr("OEBPS/" + name, chapter_xhtml(ch), compress_type=zipfile.ZIP_DEFLATED)
    return EPUB, files


def verify_epub(chapters, files):
    with zipfile.ZipFile(EPUB) as z:
        names = z.namelist()
        assert names[0] == "mimetype", "mimetype 不是首个条目"
        assert z.read("mimetype") == b"application/epub+zip"
        assert z.getinfo("mimetype").compress_type == zipfile.ZIP_STORED
        ET.fromstring(z.read("META-INF/container.xml"))
        opf = ET.fromstring(z.read("OEBPS/content.opf"))
        ns = {"opf": "http://www.idpf.org/2007/opf"}
        manifest = [i.get("href") for i in opf.findall("opf:manifest/opf:item", ns)]
        for href in manifest:
            assert "OEBPS/" + href in names, f"manifest 缺文件 {href}"
        spine = [i.get("idref") for i in opf.findall("opf:spine/opf:itemref", ns)]
        assert len(spine) == len(files) + 2, "spine 条目数不符"
        for name in ["nav.xhtml", "title.xhtml", "cover.xhtml"] + files:
            ET.fromstring(z.read("OEBPS/" + name))
        ET.fromstring(z.read("OEBPS/toc.ncx"))
        nav = z.read("OEBPS/nav.xhtml").decode("utf-8")
        assert nav.count('<li class="chap">') == len(files), "nav 章节数与正文不符"
    return len(names), len(files)


def main():
    pages = load_pages()
    blocks = parse_blocks(pages)
    chapters = build_chapters(blocks)
    print(f"pages={len(pages)}  chars={sum(len(v) for v in pages.values())}  "
          f"blocks={len(blocks)}  chapters={len(chapters)}")

    write_markdown(pages)
    print(f"WROTE {MD}  ({MD.stat().st_size} bytes)")

    _, files = build_epub(chapters)
    entries, nch = verify_epub(chapters, files)
    print(f"WROTE {EPUB}  ({EPUB.stat().st_size} bytes, {entries} entries, {nch} chapters) EPUB VERIFY OK")
    print("volumes: " + " | ".join(f"{v[2]}({v[0]}-{v[1]})" for v in VOLUMES))


if __name__ == "__main__":
    main()
