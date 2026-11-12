# -*- coding: utf-8 -*-
"""剔除本轮补采中混入的非《红楼梦》图片，并重建图库数据。

剔除依据（两类，都可在 exclude.json / 本文件规则里复核）：
  1) 人工目检名单 scripts/exclude.json（logo、印章、广告、视频封面、推荐位）；
  2) 门户页规则：公开图文页 + 配文不含任何红楼主题词 + 配文较长，
     判为侧栏「相关推荐」位图片（典型：网易号底部黄仁勋/英伟达话题封面）。

被剔除的图片移到 _tmp/excluded/ 保留，不直接删除；随后可直接跑
  python scripts/fetch_web_photos.py --reindex
重算人物归属。

用法： python scripts/curate_photos.py
"""
import os, re, sys, json, shutil

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.path.join(ROOT, '_tmp')
DEST = os.path.join(ROOT, 'assets', 'photos')
EXCLUDED = os.path.join(TMP, 'excluded')
os.makedirs(EXCLUDED, exist_ok=True)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_web_photos import TOPIC, build_js  # noqa: E402

AD_HOC = re.compile(r'下载APP|关注 确定不再关注|赛博对话|走电影|营业厅|'
                    r'网络有限公司|点击上方|长按指纹|扫码|视频号')


def main():
    mf = os.path.join(TMP, 'web_manifest.json')
    manifest = json.load(open(mf, encoding='utf-8'))
    cfg = json.load(open(os.path.join(ROOT, 'scripts', 'exclude.json'), encoding='utf-8'))
    stems = set(cfg.get('stems', []))
    ranges = cfg.get('ranges', [])
    reasons = {}

    def in_ranges(stem):
        m = re.match(r'web-(\d{4})$', stem)
        if not m:
            return False
        n = int(m.group(1))
        return any(a <= n <= b for a, b in ranges)

    kept = []
    for m in manifest:
        stem = os.path.splitext(m['file'])[0]
        why = ''
        if stem in stems:
            why = '目检名单：logo / 印章 / 广告 / 非影像'
        elif in_ranges(stem):
            why = '目检名单：门户页「相关推荐」位视频封面'
        else:
            ctx = (m.get('ctx') or '').strip()
            if AD_HOC.search(ctx):
                why = '推广/APP/栏目文字'
            elif m.get('origin') == '公开图文页' and len(ctx) > 8 and not TOPIC.search(ctx):
                why = '配文与红楼主题无关（侧栏推荐位）'
        if why:
            reasons[m['file']] = why
            files = [m['file'], m.get('thumb', '')]
            # web-NNNN.* 的缩略图命名规则固定为 webt-NNNN.jpg，manifest 里不存该字段，
            # 剔除时一并移走，避免 assets/photos/ 留下孤儿缩略图。
            if stem.startswith('web-'):
                files.append('webt-' + stem.replace('web-', '', 1) + '.jpg')
            for f in files:
                src = os.path.join(DEST, f) if f else ''
                if src and os.path.exists(src):
                    shutil.move(src, os.path.join(EXCLUDED, f))
        else:
            kept.append(m)

    json.dump(kept, open(mf, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    n = build_js(kept)
    print(f'剔除 {len(reasons)} 张，保留 {n} 张；被剔除图片移至 _tmp/excluded/')
    by = {}
    for f, why in reasons.items():
        by[why] = by.get(why, 0) + 1
    for k, v in by.items():
        print(f'  {v:3d}  {k}')
    json.dump(reasons, open(os.path.join(TMP, 'curate_reasons.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
