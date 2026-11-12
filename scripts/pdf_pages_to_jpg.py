# -*- coding: utf-8 -*-
"""把扫描 PDF 逐页导出为 JPG，供 OCR 与人工目检使用。

优先直接抽取页面内嵌的原图（无损、最快）；没有内嵌图时才重新渲染。
用法:
  python scripts/pdf_pages_to_jpg.py --match 宝黛 --out _tmp/pdf_pages/baodai --pages 1,2,3
  python scripts/pdf_pages_to_jpg.py --match 宝黛 --out _tmp/pdf_pages/baodai
"""
import argparse
import io
import pathlib

import pymupdf
from PIL import Image

BOOKS = pathlib.Path("data/books")
MAX_SIDE = 1800


def pick_page_image(doc, page):
    """返回该页最大的内嵌图片字节，或 None。"""
    best = None
    best_area = 0
    for info in page.get_images(full=True):
        xref = info[0]
        try:
            raw = doc.extract_image(xref)
        except Exception:
            continue
        area = raw.get("width", 0) * raw.get("height", 0)
        if area > best_area:
            best_area, best = area, raw
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--match", required=True, help="PDF 文件名包含的关键字")
    ap.add_argument("--out", required=True, help="输出目录")
    ap.add_argument("--pages", default="", help="页码(1 起)，逗号分隔；留空为全部")
    args = ap.parse_args()

    pdfs = [p for p in BOOKS.glob("*.pdf") if args.match in p.name]
    if len(pdfs) != 1:
        raise SystemExit(f"匹配到 {len(pdfs)} 本 PDF，请给更精确的关键字: {[p.name[:30] for p in pdfs]}")

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(pdfs[0])
    total = doc.page_count
    pages = [int(x) for x in args.pages.split(",") if x.strip()] if args.pages else list(range(1, total + 1))

    for pno in pages:
        if not 1 <= pno <= total:
            continue
        page = doc[pno - 1]
        path = out / f"p{pno:04d}.jpg"
        raw = pick_page_image(doc, page)
        if raw and raw.get("ext") in ("jpeg", "jpg"):
            data = raw["image"]
            with Image.open(io.BytesIO(data)) as im:
                im = im.convert("RGB")
                if max(im.size) > MAX_SIDE:
                    im.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
                im.save(path, "JPEG", quality=88)
        elif raw:
            with Image.open(io.BytesIO(raw["image"])) as im:
                im = im.convert("RGB")
                if max(im.size) > MAX_SIDE:
                    im.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
                im.save(path, "JPEG", quality=88)
        else:
            page.get_pixmap(dpi=160).save(path)

    print(f"exported {len(pages)} pages -> {out}  (total {total})")
    doc.close()


if __name__ == "__main__":
    main()
