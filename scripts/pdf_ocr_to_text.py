# -*- coding: utf-8 -*-
"""扫描页 OCR -> Markdown 文字书籍（可断点续跑）。

流程:
  1. python scripts/pdf_pages_to_jpg.py --match 宝黛 --out _tmp/pdf_pages/baodai
  2. python scripts/pdf_ocr_to_text.py
每页识别结果缓存到 _tmp/ocr_cache/<slug>/pNNNN.json，中断后重跑会跳过已完成页。
仅对平均置信度低的页做「反相图」第二遍识别并逐行择优。
人工目检校对只记录在 scripts/ocr_corrections.json，未校对页不宣称已核对。
"""
import argparse
import json
import pathlib
import re
import statistics
import time

from PIL import Image, ImageOps
from rapidocr_onnxruntime import RapidOCR

CACHE_ROOT = pathlib.Path("_tmp/ocr_cache")
CORRECTIONS = pathlib.Path("scripts/ocr_corrections.json")
PAGE_NUM_RE = re.compile(r"^[·•．\.\s]*\d{1,3}[·•．\.\s]*$")


def ocr(engine, path, invert=False):
    target = path
    if invert:
        target = path.with_name(path.stem + "_inv.jpg")
        if not target.exists():
            with Image.open(path) as im:
                ImageOps.invert(im.convert("RGB")).save(target, "JPEG", quality=90)
    res, _ = engine(str(target))
    lines = []
    for box, text, score in (res or []):
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        lines.append({
            "x": round(min(xs), 1),
            "y": round(min(ys), 1),
            "h": round(max(ys) - min(ys), 1),
            "text": text.strip(),
            "conf": round(float(score), 4),
        })
    lines.sort(key=lambda d: (d["y"], d["x"]))
    return lines


def choose_lines(primary, secondary):
    """按 y 近似对齐，逐行取置信度更高的文本；secondary 多出的行忽略。"""
    out = [dict(l) for l in primary]
    for s in secondary:
        cand = [p for p in primary if abs(p["y"] - s["y"]) < max(8, s["h"] * 0.6)]
        if not cand:
            continue
        p = min(cand, key=lambda d: abs(d["y"] - s["y"]))
        if s["conf"] > p["conf"] + 0.05:
            for o in out:
                if o["y"] == p["y"] and o["x"] == p["x"]:
                    o["text"] = s["text"]
                    o["conf"] = s["conf"]
                    break
    return out


def page_markdown(lines, corrections):
    """按行重排为段落，返回 (markdown, 书页码, 低置信行数)。"""
    if not lines:
        return "", None, 0
    body = [l for l in lines if len(l["text"]) >= 6]
    left = statistics.median([l["x"] for l in body]) if body else min(l["x"] for l in lines)
    h = statistics.median([l["h"] for l in body]) if body else 20
    book_page = None
    paras, cur, cur_x = [], "", left
    low_conf = sum(1 for l in lines if l["conf"] < 0.6)

    for l in lines:
        t = l["text"].strip()
        if not t:
            continue
        if PAGE_NUM_RE.match(t):
            m = re.search(r"\d+", t)
            if m:
                book_page = int(m.group())
            continue
        for a, b in corrections.items():
            t = t.replace(a, b)
        is_new = bool(cur) and l["x"] > left + h * 0.65
        if is_new:
            paras.append((cur, cur_x))
            cur, cur_x = t, l["x"]
        else:
            cur += t
    if cur:
        paras.append((cur, cur_x))

    rendered = []
    for p, x in paras:
        p = p.strip()
        if not p:
            continue
        # 明显居中、短、无句末标点 -> 视为小节标题
        if len(p) <= 16 and x > left + h * 1.5 and not re.search(r"[，。！？；：,.!?…]$", p):
            rendered.append(f"### {p}")
        else:
            rendered.append(p)
    return "\n\n".join(rendered), book_page, low_conf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", default="baodai")
    ap.add_argument("--dir", default="_tmp/pdf_pages/baodai")
    ap.add_argument("--out", default="data/books/text/宝黛话红楼.md")
    ap.add_argument("--title", default="宝黛话红楼")
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 页（调试用）")
    ap.add_argument("--second-pass-below", type=float, default=0.84)
    args = ap.parse_args()

    pages = sorted(p for p in pathlib.Path(args.dir).glob("p*.jpg")
                   if re.fullmatch(r"p\d{4}\.jpg", p.name))
    if args.limit:
        pages = pages[: args.limit]
    cache = CACHE_ROOT / args.slug
    cache.mkdir(parents=True, exist_ok=True)
    all_fixes = json.loads(CORRECTIONS.read_text(encoding="utf-8")) if CORRECTIONS.exists() else {}
    overrides = all_fixes.get("_overrides", {})

    engine = RapidOCR()
    t0 = time.time()
    for i, path in enumerate(pages, 1):
        cf = cache / (path.stem + ".json")
        if cf.exists():
            data = json.loads(cf.read_text(encoding="utf-8"))
        else:
            lines = ocr(engine, path)
            conf = statistics.mean([l["conf"] for l in lines]) if lines else 0
            if lines and conf < args.second_pass_below:
                lines = choose_lines(lines, ocr(engine, path, invert=True))
            data = {"lines": lines, "avg_conf": round(conf, 4), "second_pass": conf < args.second_pass_below}
            cf.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        if i % 20 == 0 or i == len(pages):
            print(f"  {i}/{len(pages)} pages  {time.time() - t0:.0f}s", flush=True)

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    head = [
        f"# {args.title}",
        "",
        "> 陈晓旭、邓婕、欧阳奋强、王贵娥 等著，花山文艺出版社，1987 年。",
        f"> 本文由扫描 PDF（{len(pages)} 页，无文字层）逐页 OCR 整理，仅供本地资料检索。",
        "> 生成脚本：`python scripts/pdf_ocr_to_text.py`；识别文字可能有误，引用请以原书扫描页为准。",
        "> `scripts/ocr_corrections.json` 的 `_overrides` 与页级替换表为多模态模型目检精校页；其余页为 OCR 自动识别，未逐页人工核对。",
        "",
    ]
    chunks, stats = [], []
    for path in pages:
        cf = cache / (path.stem + ".json")
        data = json.loads(cf.read_text(encoding="utf-8"))
        page_no = int(path.stem[1:])
        key = f"p{page_no:04d}"
        if key in overrides:
            md, book_page, low = overrides[key], None, 0
        else:
            md, book_page, low = page_markdown(data["lines"], all_fixes.get(key, {}))
        stats.append((page_no, len(md), data["avg_conf"], low))
        label = f"## PDF 第 {page_no} 页"
        if book_page:
            label += f"（原书页码 {book_page}）"
        chunks.append(label + "\n\n" + (md if md else "_（本页无可识别文字，或为空白/插图页）_"))

    out.write_text("\n".join(head) + "\n" + "\n\n".join(chunks) + "\n", encoding="utf-8")
    report = {
        "pages": len(pages),
        "chars": sum(s[1] for s in stats),
        "empty_pages": [s[0] for s in stats if s[1] < 20],
        "avg_conf": round(statistics.mean([s[2] for s in stats]), 4),
        "low_conf_pages": [s[0] for s in stats if s[3] >= 3],
        "second_pass_pages": [p.stem for p in cache.glob("*.json")
                              if json.loads(p.read_text(encoding="utf-8")).get("second_pass")],
    }
    pathlib.Path("_tmp/ocr_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"WROTE {out}  chars={report['chars']}  avg_conf={report['avg_conf']}  empty={len(report['empty_pages'])}")
    print(json.dumps(report, ensure_ascii=False)[:800])


if __name__ == "__main__":
    main()
