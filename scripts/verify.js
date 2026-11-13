/* 资料馆 · 集成校验（v2.3：人物深度资料并入人物详情页，图库三路合并）
 * 用法： node scripts/verify.js
 * 检查：人物册数据可加载、每则故事与每张照片均有出处、全部图片在唯一图库目录中存在、
 *       网络补采影像逐张带出处/渠道/归属方式、bridge.js 索引与实际数据一致、
 *       主站不再引用黑色子站、不再有独立册页/册卡，旧 #/book/ 地址仅作兼容。
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '..');   // 资料馆根（数据与脚本已并入 data/ 与 scripts/）
let pass = 0, fail = 0;
function check(label, cond, extra) {
  if (cond) { pass++; console.log('  [PASS] ' + label); }
  else { fail++; console.log('  [FAIL] ' + label + (extra ? ' → ' + extra : '')); }
}

/* ---------- 1. 加载全部数据（与主站 index.html 同序） ---------- */
const ctx = vm.createContext({ window: {}, console: console });
function load(p) { vm.runInContext(fs.readFileSync(p, 'utf8'), ctx, { filename: p }); }
['data/characters.js','data/photos.js','data/photos-nverce.js','data/photos-web.js','data/photos-book.js','data/jinling.js','data/content.js']
  .forEach(function (f) { load(path.join(ROOT, f)); });
['data/books-content.js','data/people-extra.js','data/memoir.js','data/nv-photos-source.js','data/bridge.js']
  .forEach(function (f) { load(path.join(ROOT, f)); });

const w = ctx.window;
const HLM = w.HLM87 || {};
const ARCH = HLM.photos || {};
const EXTRA = HLM.extraPhotos || [];
const WEB = HLM.webPhotos || [];
const BOOK = HLM.bookPhotos || [];
const MEMOIR = w.MEMOIR || {};
const ALL = (ARCH.items || []).concat(EXTRA, WEB, BOOK);  // 主站运行时合并后的完整图库
const BOOKS = w.BOOKS || {}, REF = w.REF || {}, PEOPLE = w.PEOPLE || [],
      NV = w.NVERCE || {}, PHOTOS = w.PHOTOS || [], SOURCES = w.SOURCES || [];

console.log('\n【1】数据加载与图库合并');
check('人物册字典 BOOKS 共 21 册', Object.keys(BOOKS).length === 21, Object.keys(BOOKS).length + ' 册');
check('已收录人物 PEOPLE.status=done 与册数一致', PEOPLE.filter(function (p) { return p.status === 'done'; }).length === Object.keys(BOOKS).length);
check('信源表 REF 可加载', Object.keys(REF).length >= 15, Object.keys(REF).length + ' 条');
check('资料馆原图库 149 张', (ARCH.items || []).length === 149, (ARCH.items || []).length + ' 张');
check('女儿册专采 201 帧已生成为合并记录', EXTRA.length === 201 && PHOTOS.length === 201);
check('网络补采影像已加载（微信公众号 / 公开图文 / 图片检索）', WEB.length > 0, WEB.length + ' 张');
check('书籍影像已加载（回忆录插图 + 纪念画册扫描页）', BOOK.length > 0, BOOK.length + ' 张');
check('四路合并后图库 = 149 + 201 + ' + WEB.length + ' + ' + BOOK.length + ' 张', ALL.length === 149 + 201 + WEB.length + BOOK.length, ALL.length + ' 张');
check('判词数据（第五回）可读取', !!(HLM.jinling && HLM.jinling.groups));
check('第一册文字信源 12 条', SOURCES.length === 12, SOURCES.length + ' 条');

/* ---------- 2. 出处完整性 ---------- */
console.log('\n【2】出处完整性');
let stories = 0; const missingSrc = [], badRef = [], badSources = [];
Object.keys(BOOKS).forEach(function (id) {
  const b = BOOKS[id];
  ['chapters', 'timeline', 'behind'].forEach(function (key) {
    (b[key] || []).forEach(function (it, i) {
      stories++;
      if (!it.src) missingSrc.push(id + '/' + key + '[' + i + ']');
      if (it.ref && !REF[it.ref]) badRef.push(id + '/' + key + '[' + i + '] → ' + it.ref);
    });
  });
  (b.sources || []).forEach(function (k) {
    if (typeof k === 'string' && !REF[k]) badSources.push(id + ' → ' + k);
  });
});
check('每则故事均有 src 出处', missingSrc.length === 0, missingSrc.slice(0, 5).join(', '));
check('每条 ref 指向存在的信源', badRef.length === 0, badRef.slice(0, 5).join(', '));
check('每册 sources 键均有效', badSources.length === 0, badSources.slice(0, 5).join(', '));
check('双线故事总数与索引一致', stories === NV.totalStories, stories + ' vs ' + NV.totalStories);
check(ALL.length + ' 张图片均有 host / srcUrl / date', ALL.every(function (p) { return p.host && p.srcUrl && p.date; }));
check('网络补采影像逐张带出处 / 文章标题 / 渠道 / 归属方式',
  WEB.every(function (p) { return p.host && p.srcUrl && p.date && p.origin && p.title && p.attribution; }));
check('网络补采影像均使用 web- 前缀且文件引用唯一',
  WEB.every(function (p) { return /^web-\d{4}\./.test(p.file); }) &&
  new Set(WEB.map(function (p) { return p.file; })).size === WEB.length);
check('新增信源 URL 均为 http(s) 且非空', (NV.sources || []).length >= 8 && (NV.sources || []).every(function (s) { return /^https?:\/\//.test(s.url); }), (NV.sources || []).length + ' 条');
check('黛玉专采记录保留来源页面与文章标题', EXTRA.every(function (p) { return p.srcUrl && p.title && p.cat && p.origin === '女儿册采集'; }));
check('书籍影像逐张带书名 / 章节或页码 / 出处 / 原书图注',
  BOOK.every(function (p) { return p.host && p.srcUrl && p.date && p.origin && p.book && (p.chapter || p.page) && p.caption && p.attribution; }));
const memoirIds = Object.keys(MEMOIR);
check('回忆录一手材料覆盖 19 册（刘姥姥 / 薛宝琴原书无专章）', memoirIds.length === 19, memoirIds.length + ' 册');
check('回忆录每条幕后与语录均标注原书章节',
  memoirIds.every(function (id) {
    return MEMOIR[id].behind.every(function (b) { return b.title && b.text && /1987，我们的红楼梦/.test(b.src || ''); }) &&
           MEMOIR[id].quotes.every(function (q) { return q.t && /欧阳奋强记述/.test(q.from || ''); });
  }));
check('回忆录文字书籍可核查（data/books/text/*.md）',
  fs.existsSync(path.join(ROOT, 'data/books/text/1987我们的红楼梦-欧阳奋强.md')));

/* ---------- 3. 唯一图库目录中的图片文件 ---------- */
console.log('\n【3】图片文件（assets/photos/ 单一目录）');
const missImg = [];
ALL.forEach(function (p) {
  if (!fs.existsSync(path.join(ROOT, 'assets/photos', p.file))) missImg.push(p.file);
  if (p.thumb && !fs.existsSync(path.join(ROOT, 'assets/photos', p.thumb))) missImg.push(p.thumb);
});
check('全部原图与缩略图存在（含网络补采 ' + WEB.length + ' 张）', missImg.length === 0, missImg.length + ' 缺失：' + missImg.slice(0, 5).join(', '));
check('文件名无冲突（nv- / nvt- 前缀不与原有 149 张重名）',
  fs.readdirSync(path.join(ROOT, 'assets/photos')).filter(function (f) { return /^nv-/.test(f); }).length === 201 &&
  fs.readdirSync(path.join(ROOT, 'assets/photos')).filter(function (f) { return /^nvt-/.test(f); }).length === 201);
check('目录已合并：nverce/ 不再存在，数据与脚本统一在 data/ 与 scripts/',
  !fs.existsSync(path.join(ROOT, 'nverce')) &&
  fs.existsSync(path.join(ROOT, 'data/books-content.js')) &&
  fs.existsSync(path.join(ROOT, 'scripts/verify.js')));

/* ---------- 4. 主站集成结构 ---------- */
console.log('\n【4】主站集成与链接');
const mainHtml = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
const subHtml = fs.readFileSync(path.join(ROOT, 'nverce-redirect.html'), 'utf8');
check('主站导航已移除 special 异形按钮', mainHtml.indexOf('menu special') < 0);
check('主站不再链接独立子站，数据统一从 data/ 加载', mainHtml.indexOf('nverce/') < 0 && mainHtml.indexOf('data/books-content.js') > 0);
check('主站引入人物册数据（books-content / people-extra / memoir / bridge）',
  mainHtml.indexOf('data/books-content.js') > 0 && mainHtml.indexOf('data/people-extra.js') > 0 &&
  mainHtml.indexOf('data/memoir.js') > 0 && mainHtml.indexOf('data/bridge.js') > 0);
check('主站引入四路图库数据（nverce / web / book）', mainHtml.indexOf('data/photos-nverce.js') > 0 && mainHtml.indexOf('data/photos-web.js') > 0 && mainHtml.indexOf('data/photos-book.js') > 0);
check('回忆录材料并入已有板块，不新增页面 / 板块', mainHtml.indexOf('window.MEMOIR') > 0 && mainHtml.indexOf('B.behind = (B.behind||[])') > 0 && mainHtml.indexOf('viewBook(') < 0);
check('图库页含微信公众号 / 图片检索来源筛选与分批渲染', mainHtml.indexOf('微信公众号图文') > 0 && mainHtml.indexOf('morePhotos') > 0);
check('信源页含本轮影像信源聚合表', mainHtml.indexOf('本轮影像信源') > 0 && mainHtml.indexOf('欧阳宝玉') > 0);
check('人物图鉴不再有册卡网格 / 独立专题板块', mainHtml.indexOf('bookgrid') < 0 && mainHtml.indexOf('bookletCards()') < 0 && mainHtml.indexOf('bookcard') < 0);
check('女儿册是「全部人物」下拉里的一个分类', mainHtml.indexOf('id="lb"') > 0 && mainHtml.indexOf('女儿册人物（') > 0);
check('主站不再有双卷标签页 / 上下册导航', mainHtml.indexOf('pane-real') < 0 && mainHtml.indexOf('bookTab(') < 0 && mainHtml.indexOf('book-nav') < 0);
check('人物详情直接拼装双线故事、判词与资料依据', mainHtml.indexOf('charStorySections(B,c.name)') > 0 && mainHtml.indexOf('charSourceBox(B)') > 0 && mainHtml.indexOf('profileRows(B.profile)') > 0);
check('旧 #/book/ 地址仅兼容，直接渲染人物详情', mainHtml.indexOf('case "book"') > 0 && mainHtml.indexOf('viewBook(') < 0 && mainHtml.indexOf('viewChar(bb&&bb.name') > 0);
check('册页出处块与站内信源链接已改写', mainHtml.indexOf('charSourceBox') > 0 && mainHtml.indexOf('.replace("../index.html","")') > 0);
check('图库页含来源筛选（女儿册采集）', mainHtml.indexOf('id="po"') > 0 && mainHtml.indexOf('女儿册采集') > 0);
check('信源页列出新增报道信源', mainHtml.indexOf('女儿册新增信源') > 0);
check('nverce-redirect.html 为浅色跳转页', subHtml.indexOf('index.html#/list') > 0 && subHtml.indexOf('../index.html') < 0 && subHtml.indexOf('assets/app.js') < 0 && subHtml.indexOf('background:#faf7f2') > 0);
check('bridge.js 人物数与 BOOKS 一致', NV.peopleCount === Object.keys(BOOKS).length, NV.peopleCount + ' vs ' + Object.keys(BOOKS).length);
check('bridge.js 影像总数对应女儿册两路（149+201=350）', NV.totalPhotos === 149 + 201, NV.totalPhotos + ' vs ' + (149 + 201));
check('全站图库 = 女儿册两路 350 + 网络补采 ' + WEB.length + ' + 书籍 ' + BOOK.length, ALL.length === 350 + WEB.length + BOOK.length, ALL.length + ' 张');
check('bridge.js base 指向人物详情页路由', NV.base === '#/char/', NV.base);
check('bridge.js 每位人物带 route 站内地址（#/char/<姓名>）',
  Object.keys(NV.people || {}).length === 21 &&
  Object.keys(NV.people || {}).every(function (n) { return /^#\/char\//.test((NV.people[n] || {}).route || ''); }));

console.log('\nRESULT: pass=' + pass + ' fail=' + fail);
process.exit(fail ? 1 : 0);
