# -*- coding: utf-8 -*-
"""诊断 data/books 下 PDF 是否带文字层（OCR 文本层）。

用法: python scripts/check_pdf_text.py
输出: 每本 PDF 的页数、抽样页的文本字符数、含文本页占比。
"""
import pathlib
import fitz  # PyMuPDF

BOOKS = pathlib.Path("data/books")


def main():
    for path in sorted(BOOKS.glob("*.pdf")):
        doc = fitz.open(path)
        n = doc.page_count
        # 均匀抽样 30 页 + 固定前 5 页和末 2 页
        idx = sorted(set(
            list(range(min(5, n)))
            + [int(n * k / 30) for k in range(30)]
            + [max(0, n - 2), max(0, n - 1)]
        ))
        idx = [i for i in idx if i < n]
        lens = [(i, len(doc[i].get_text().strip())) for i in idx]
        nonempty = sum(1 for _, c in lens if c > 20)
        print(f"\n=== {path.name[:60]} ===")
        print(f"  pages={n}  sampled={len(lens)}  with_text(>20ch)={nonempty}/{len(lens)}")
        print(f"  sample: {lens[:12]}")
        first = next((i for i, c in lens if c > 20), None)
        if first is not None:
            preview = doc[first].get_text().strip().replace("\n", " ")[:180]
            print(f"  page{first} preview: {preview}")
        doc.close()

    for path in sorted(BOOKS.glob("*.epub")):
        print(f"\n=== EPUB: {path.name[:60]} ===  ({path.stat().st_size / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    main()
