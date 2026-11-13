# Dream_of_the_Red_Chamber

87版红楼梦信息汇集 · 纯本地静态站（双击 `index.html` 即可离线浏览，无构建、无后端、无第三方库）。

## 站点结构

- `index.html` — 唯一页面，单页 hash 路由：人物图鉴（248 人，其中 21 位的人物详情页内含双线故事）、36 集分集剧情、关系图、时间线、音乐、幕后、纪念、结局对照、图库（**3416 张**）、信源勘误。全站统一浅色主题。
- `data/*.js` — 主站数据与 21 册人物深度资料（全局 `window.HLM87` / `window.BOOKS` 等）。
  - `data/photos.js` — 资料馆原有 149 张图库记录（逐张 `host` / `srcUrl` / `date`）。
  - `data/photos-nverce.js` — 由 `scripts/merge_photos.js` 生成的 201 帧专采照片（`window.HLM87.extraPhotos`）。
  - `data/photos-web.js` — v2.2 / v2.4 / v2.7 / v2.8 网络补采 2646 张（`window.HLM87.webPhotos`），由 `scripts/fetch_web_photos.py --build-only` 从 `_tmp/web_manifest.json` 重建；第三轮由 `scripts/fetch_more_photos.py`、第四轮由 `scripts/fetch_round4_photos.py` 采集并追加到同一清单；逐张含原文标题、采集渠道、原文配文与人物归属方式。
  - `data/photos-book.js` — 书籍影像 420 张（`window.HLM87.bookPhotos`），由 `scripts/import_book_photos.py` 生成：回忆录 EPUB 插图 148 张 + 纪念画册扫描页 272 张；逐张含书名、章节/页码、原书图注与归属方式。
  - 四组数据在运行时 concat 进 `H.photos.items`，形成全站唯一图库。
- `assets/photos/` — **唯一图库目录**，3416 张原图与对应缩略图（`nv-`/`nvt-`、`web-`/`webt-`、`bk-`/`bkt-`、`bkp-`/`bkpt-` 前缀）。
- `data/books/` — 原始书籍（出处依据）：欧阳奋强回忆录 EPUB、两本李耀宗纪念画册 PDF、1987 年《宝黛话红楼》PDF；`data/books/text/` 为整理出的文字书籍。
- **v2.9 起已无 `nverce/` 目录**：原「女儿册」的数据、工具与跳转页全部并入主目录，不再是独立页面或独立结构。
  - `data/books-content.js` — 林黛玉 / 陈晓旭（双线故事、判词、诗作、语录、12 条信源、考据说明）。
  - `data/people-extra.js` — 其余 20 位人物的双线故事、`REF` 信源表、`CHAR2ID` 照片映射、出处规范。
  - `data/memoir.js` — 回忆录一手材料（19 册、56 条幕后 + 28 条语录），由 `scripts/memoir_to_stories.py` 生成；运行时追加到各册已有的 `behind` / `quotes`，不新增板块。
  - `data/bridge.js` — 人物 → `route`（`#/char/<姓名>`）、故事数、影像数、新增信源；由 `scripts/build_bridge.js` 生成，勿手工编辑。
  - `data/nv-photos-source.js` — 201 帧专采照片的采集源清单（`window.PHOTOS`），供 `scripts/merge_photos.js` 复采；主站运行时不加载。
  - `nverce-redirect.html` — 旧地址的浅色跳转页，指向主站 `#/list`（原 `nverce/index.html`）。
  - `scripts/` — 采集、复采、缩略图、索引生成与两套校验脚本（原 `nverce/tools/` 的 4 个脚本已并入）。
  - 402 个与 `assets/photos/nv-*`、`nvt-*` **逐字节相同**的采集底本（约 56MB）已移出仓库，归档到 `_archive/retired/nverce-source/{images,thumbs}`（本地保留、不入库）；已停用的黑色子站 `assets/app.js` / `style.css`、旧台账 `data_photos.json` 同在 `_archive/retired/`。

## 人物图鉴与人物详情页（v2.3 起）

- **「女儿册」不是独立页面**：没有专题板块、没有册卡网格、没有额外导航项、没有人物卡徽标。它只是「全部人物」筛选区第三个下拉里的一个分类选项「女儿册人物（21）」。
- **点人物卡进 `#/char/<姓名>`，全部内容都在同一页**，依次是：
  1. 基础档案表（归属、关系、演员、剧中剧情、87版结局、别名、层级、备注 + 别号 / 居所 / 家世 / 侍女 / 籍册 / 花签 / 生卒 / 身份）；
  2. 影像（最多 12 张，逐张带来源与「查看出处 ↗」，超出部分给「查看全部 N 张影像 →」）；
  3. 双线故事：第五回判词与曲子、按回目编排的书中故事、她的诗、扮演者现实人生年表、幕后细节、她自己写的诗、她说；
  4. 资料依据（本人物专用信源、考据说明、站内信源链接；有回忆录材料者附「当事人回忆录」与文字书籍链接）。
- 这些内容**平铺呈现，无标签页、无「读两卷故事」跳转、无上一册/下一册导航**。旧 `#/book/<id>` 地址仅作兼容，直接渲染对应人物详情。
- 图库四路合并为单一 `#/photos`，可按角色 / 演员 / 描述 / 来源站点检索，按剧照 / 生活照与 7 类采集来源筛选，每批渲染 120 张；合影按 `、` 拆分索引，同一张可出现在多位人物页但只计一次。

## v2.4–v2.8 图库扩采与归属修复（2026-11-12 / 11-13）

### 数量与来源

| 渠道 | 张数 | 说明 |
|---|---|---|
| 资料馆原图库 | 149 | 原有 |
| 女儿册专采 | 201 | 原有 |
| 微信公众号图文 | 919 | 累计源 + v2.7 九篇 + v2.8 十篇新公众号 |
| 公开图文页 | 887 | 澎湃、新浪、网易、腾讯新闻与腾讯搜一搜、搜狐、美篇、凤凰网、B站专栏、崇真艺客等 |
| 公开图片检索 | 840 | Bing 定向 + v2.7 360 首页 + v2.8 360 分页接口与必应异步分页（118 组检索词） |
| 回忆录插图 | 148 | 欧阳奋强回忆录 EPUB 内嵌插图 |
| 纪念画册扫描 | 272 | 李耀宗纪念画册上/下册整页扫描（封面/版权/目录/纯文字页已目检剔除 17 页） |
| **合计** | **3416** | v2.8 第四轮净增 636 张 |

### v2.8 第四轮补采（2026-11-13）

- 新增 `scripts/sources-round4.json`（33 个未采过的图文源：欧阳宝玉《高清精美剧照》、微博旅者《87版定妆照》、红楼轶事《杨树云的 8 张设计图》、中国电视《杨树云口述》、大咖SH《史上最全聚首》等 10 篇公众号图文，以及网易号近 150 幅原版画册、澎湃艺非凡、B站专栏杂志封面、凤凰网老挂历、崇真艺客服装设计手稿等）与 `scripts/fetch_round4_photos.py`。
- **360 图片检索换成分页接口** `https://image.so.com/j?q=...&pn=180`：一次可取约 150–162 条（第三轮 HTML 首页只有 60–90 条），字段 `img` / `link` / `title` / `site` 齐全；**另开必应异步分页** `https://www.bing.com/images/async?q=...&first=1,36,71,106`（`m` 属性含 `murl` 原图、`purl` 真实来源页、`t` 图注），两渠道共享每人 10 / 每主题 20 的配额，共 118 组检索词（63 位人物 + 55 组场景/物件/幕后工种主题）。
- 本轮候选 1763 → 与图库去重 952 → 下载可用 **659 张**；14 张拼图逐格目检 + 12 张存疑单图放大复核后剔除 **23 张**（纯文字/书封书页 9、二维码 4、logo 与推广卡 2、无关现代与风景静物 3、其他影视片段截图 1、无关插画 4），净增 **636 张**；网络补采 2010 → 2646 张，全站 2780 → **3416 张**。
- 复核时救回 7 张被子代理误判的 87 版剧照：杨树云造型设计手稿（工笔仕女画/发髻线稿，来自《杨树云的 8 张设计图》，配文明确「对比剧中元春凤冠」「旺儿媳妇」「瑞珠宝珠」）、元春凤冠红袍/黄袍定妆照、柳湘莲剧照特写。**长期规则再确认：87 版总化妆师与服装设计的造型手稿、以及带清晰剧照的挂历/画册内页属收录范围，不得当作「手绘插画/戏曲扮相」剔除。**
- 修正 `curate_photos.py`：门户页逐图图注常带「打开网易新闻 查看精彩图片」引导语，剥掉前缀后再判定；并允许角色名/演员名（`KEYS`）佐证配文相关性，避免误杀 16 张有效逐图图注。
- 不可用渠道如实记录：百度图片 `acjson` 返回 `Forbid spider access`、搜狗图片 `napi` 返回 `forbid`、搜狗图片 HTML 的 `link` 只指向搜狗中转页而非原文页面（故不采）、微博图片搜索登录墙、知乎 403、今日头条固定反爬壳页、文学城 502、kknews 繁体页/多彩贵州网/环球网 403。
- 导航顺序按用户要求调整：「图库」从最后一项移到**倒数第二**（「信源·勘误」之前），样式与路由不变。


### v2.7 第三轮补采（2026-11-12）

- 新增 `scripts/sources-more.json`（50 个未采过的图文源：腾讯搜一搜高清剧照专题、新浪图片 35 张图集、搜狐挂历/杂志/服装手稿、网易幕后合照、9 篇新公众号图文等）与 `scripts/fetch_more_photos.py`（复用既有解析/去重/落盘链路，不新增第五路数据文件）。
- 另开 360 图片检索渠道：每条结果同时给出原图 URL、真实来源页、图片标题与来源站点；按「短标题 + 图像类词 + 主题词 + 每人限量」四道闸门过滤，排除视频页与素材站。共 86 组检索词。
- 本轮下载 792 张，17 张拼图逐格目检后剔除 18 张（二维码 2、纯文字/书封书页 8、无关现代新闻与风景截图 5、其他剧种扮相 1、重复手写稿 2），净增 774 张；网络补采 1236 → 2010 张，全站 2006 → 2780 张。
- 修正 `TOPIC` 主题词表（补「宝黛 / 柳湘莲 / 元妃 / 读西厢」等合称与场景名），避免把真实剧照图注误判成侧栏推荐位；`curate_photos.py` 剔除时同步移走缩略图，不再留孤儿文件。

### 人物归属修复（用户反馈：薛宝钗照片出现在贾宝玉页面）

- **根因**：公众号定妆照图集用 `▲角色名定妆照，演员 饰` 作为**图片之后的图注**，采集器却取图片**之前**的文字，整组错位一位；另把长段导语也当逐图配文。
- **修复**：`scripts/fix_attribution.py` 重抓 17 个图文页，按原图 URL 精确定位并改取后置图注；`scripts/fetch_web_photos.py` 的 `extract_pairs()` / `who()` 同步改为「后置图注优先、长段落不归单人、检索关键词一律标注未逐张核对」。
- **结果**：`w0014/0016/0019/0022` 四张薛宝钗定妆照由「贾宝玉」改归「薛宝钗」，贾宝玉名下从 44 张降到 21 张；`p002`（粉发箍黄坎肩）经图片目检确认确为宝玉本人，旧资料无误。
- 归属方式全站明示：原文配文 / 配文推断 / 检索关键词（未逐张核对） / 未判定（标「剧组 · 花絮」）。
- **二次目检复核**：把当前归入「贾宝玉」的全部图片再拼图逐格核对，又发现 11 张「配文提到宝玉但画面不是宝玉」的误标（典型：「春燕是贾宝玉房内的二等丫鬟」「王导对胡泽红说你反串宝玉都可以」「随书附赠宝黛读西厢卡片」）。其中 5 张静物 / 侧栏推荐位剔除，6 张按画面改归春燕、贾惜春、史湘云等或标「剧组 · 花絮」；规则固化在 `scripts/exclude.json` 的 `reassign` 字段，由 `scripts/fix_person_attrib.py` 复现。**长期规则：配文提到某人 ≠ 画面是某人，长段落一律不据此归单人。** 第三轮把贾宝玉索引再逐格复核并**单图放大确认**：`w0072` 戴通灵宝玉项圈、确是宝玉本人，自动目检一度误判，予以保留；`w1189` 为 AI 风格女性古装像（非 87 版剧照），剔除；`bk0013` 是东方闻樱反串宝玉与黛玉、探春搭戏的排演照，去掉宝玉归属、保留黛玉与探春。最终贾宝玉名下 54 张。

### 书籍整理

- **已完成文字书籍**：
  - 欧阳奋强《1987，我们的红楼梦》（2017）EPUB → `data/books/text/1987我们的红楼梦-欧阳奋强.md`（约 56 万字节，按原书章节顺序转纯文字，`<div class="title_pic">` 图注单独提取）。
  - 《宝黛话红楼》（1987，陈晓旭 / 邓婕 / 欧阳奋强 / 王贵娥 合著）PDF → `data/books/text/宝黛话红楼.md` 与 `data/books/text/宝黛话红楼.epub`。**全书 260 页由多模态模型逐页查看扫描页图像重新识别**（约 10.5 万字、121 个小节），按原书逐字转录、模糊字标「□」，每页保留「## PDF 第 N 页」便于与扫描页对照。逐页原稿在 `_tmp/hy4_pages/`（本地保留、不入库），由 `scripts/build_hy4_book.py` 合并成 md 与 EPUB3（5 卷 / 121 章，含封面、双层目录，每节带页码标记）。早期 RapidOCR 流程（`pdf_pages_to_jpg.py` + `pdf_ocr_to_text.py`）只作参考初稿、**不再是交付文字稿**；引用请以原书扫描页为准，不把识别文本直接当作故事入库。
- **书中图片**：148 张内嵌插图入库（`bk-*`），141 条原书图注逐张对应；289 页画册扫描目检后收录 272 页（`bkp-*`），整页含多帧照片与版面文字，一律不强行归属具体人物。
- **纪念画册不转文字**：两本李耀宗纪念画册（上 / 下册各 145 页）是摄影集，抽样每页仅 30–180 字回目、判词、图注，无长篇正文，故只收录影像，不生成文字书籍。
- **一手材料入库**：`scripts/memoir_to_stories.py` 从回忆录按人物拆出 19 册的 56 条幕后细节与 28 条第一人称语录，逐条标注书名、年份与章节，并入各人物详情页已有的「幕后细节」「她说」，资料依据处给出可核查文字版链接。刘姥姥、薛宝琴原书无专章，不强补。

## 出处约定

- **故事**：每条标注《红楼梦》回目；涉及剧版情节者标注「87版第 N 集」并链接《分集剧情》《结局对照》；扮演者现实故事标注媒体报道名称或回忆录章节，人物详情页底部「资料依据」给出可点击原文。口径不一处并列保留，资料不足处写明「资料有限，待核」。
- **照片**：每张保留来源站点 / 公众号名称、原始页面链接与采集日期，图库与人物详情页「查看出处 ↗」可回到原页面；网络补采另保留 `source`（原始图片地址）、`title`、`origin`、`caption`、`attribution`；书籍影像另保留 `book`、`chapter`/`page`、`source`。
- **人物归属**：依据原文配文或检索关键词推断，**未逐张人工核对**，卡片上均标明归属方式；无法判定者标为「剧组 · 花絮」，如有出入以原文页面为准。
- **判词**：直接读取 `data/jinling.js`，依据《红楼梦》第五回通行本，不手抄。
- **图片版权**：剧照与画册扫描件版权归原权利人所有，本站仅作资料整理与本地展示。

## 维护与校验

```bash
node scripts/merge_photos.js                     # 复采专采后同步 201 帧并重建 data/photos-nverce.js
python scripts/fetch_web_photos.py --build-only # 依据 _tmp/web_manifest.json 重建 data/photos-web.js
python scripts/fix_attribution.py                # 重抓图文页、按后置图注重算人物归属
python scripts/fix_person_attrib.py              # 按 exclude.json 的 reassign 修正目检误标
python scripts/curate_photos.py                  # 按 scripts/exclude.json 剔除目检噪声图
python scripts/make_web_thumbs.py                # 为 web-* 补生成 webt-* 缩略图
python scripts/book_to_text.py                   # EPUB → 文字书籍 + 插图索引
python scripts/check_pdf_text.py                 # 复检扫描 PDF 是否含文字层
python scripts/pdf_pages_to_jpg.py --match 宝黛 --out _tmp/pdf_pages/baodai   # 扫描页 → 内嵌 JPG
python scripts/pdf_ocr_to_text.py                # OCR 参考初稿 → _tmp/ocr_draft_*.md
python scripts/build_hy4_book.py                 # 目检分片 → 宝黛话红楼.md + .epub（最终稿）
python scripts/book_pdf_images.py                # 画册 PDF → 整页 JPEG（_tmp/book_pages/）
python scripts/import_book_photos.py             # 重建 data/photos-book.js
python scripts/make_thumbs_generic.py _tmp/thumb_jobs.json
python scripts/memoir_to_stories.py              # 回忆录 → data/memoir.js
python scripts/fetch_more_photos.py              # v2.7 新增图文页 + 360 图片检索（增量）
python scripts/fetch_round4_photos.py           # v2.8 360 分页 + 必应异步分页 + 33 个新图文源
python scripts/make_web_thumbs.py                # 补生成 webt-* 缩略图（增量）
python scripts/curate_photos.py                  # 按 exclude.json 目检名单剔除并重建数据
node scripts/build_bridge.js                     # 增删人物 / 故事后重建 data/bridge.js
node verify-render.js                            # 主站 17 个视图冒烟测试 + 架构约束
node scripts/verify.js                           # 数据 / 出处 / 3416 张图片存在性 / 站内链接（47 项）
```

交付前两套校验必须全绿；涉及视觉改动时用无头 Chrome（`--headless=new --screenshot --allow-file-access-from-files --window-size=1280,1000 --virtual-time-budget=5000`）截图自查。

## 目录约定（v2.9 整理）

- `.gitignore` 忽略 `_tmp/`（采集明细、目检拼图、被剔除图片留档、浏览器缓存）、`_archive/`（停用资源与历史拼图）、`.workbuddy/`（会话与工作区记忆）、Python 缓存，以及 `data/books/*`：原始 EPUB / 扫描 PDF 约 190MB 且有版权风险，已从 git 索引移除（`git rm --cached`），**本地文件保留**作出处依据。例外 `!data/books/text/` 保证站点「查看本站整理的可核查文字版」链接与校验所依赖的 md 仍在库内。
- 站点运行必需的全部文件（`index.html`、`nverce-redirect.html`、`data/`、`assets/photos/`、`scripts/`、`*.md`、校验脚本、文字书籍）纳入版本管理；原始书籍与 v2.9 移出的 402 张重复采集底本不再纳入。
- 被目检剔除的图片统一移到 `_tmp/excluded/`，不直接删除；名单与原因在 `scripts/exclude.json`。

环境说明：本机为 Windows + Python 3.13。此前「装不了 Pillow / PDF 库」是 pip 源问题：默认清华源失败，改用 `-i https://mirrors.aliyun.com/pypi/simple/` 后 Pillow 13、PyMuPDF 2.1、pdfplumber、pypdf、RapidOCR(onnxruntime) 全部安装成功；系统级 tesseract 仍不可用，中文 OCR 走 RapidOCR。早期手写的 `sniff()` / `dims()`、DCTDecode JPEG 抽取与「本地 HTTP Server + 无头 Chrome Canvas」缩略图方案保留为无依赖回退。
