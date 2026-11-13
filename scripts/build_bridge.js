/* 生成 data/bridge.js —— 人物深度资料的共享索引
 * 用法： node scripts/build_bridge.js
 * v2.3：「女儿册」不再是独立册页或册卡区块，21 位人物的双线故事、判词与影像
 *       全部并入主站人物详情页 #/char/<姓名>；「女儿册」只是人物图鉴下拉里的一个分类。
 *       本索引只提供人数、故事数、影像数与新增信源，id 仅作 BOOKS 数据键。
 * 每次增删人物 / 故事 / 照片后重跑一次，主站里的数字会自动校准。
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '..');            // 资料馆根（脚本已并入 scripts/）
const ctx = vm.createContext({ window: {}, console: console });

function load(p) {
  vm.runInContext(fs.readFileSync(p, 'utf8'), ctx, { filename: p });
}

load(path.join(ROOT, 'data/jinling.js'));
load(path.join(ROOT, 'data/photos.js'));
load(path.join(ROOT, 'data/books-content.js'));
load(path.join(ROOT, 'data/people-extra.js'));
load(path.join(ROOT, 'data/nv-photos-source.js'));

const w = ctx.window;
const BOOKS = w.BOOKS || {};
const PEOPLE = w.PEOPLE || [];
const CHAR2ID = w.CHAR2ID || {};
const REF = w.REF || {};
const photos = w.PHOTOS || [];
const arch = ((w.HLM87 && w.HLM87.photos) || {}).items || [];

/* 照片计数：与主站 photosIndex 同一套人物映射规则 */
const counts = {};
photos.forEach(() => { counts.daiyu = (counts.daiyu || 0) + 1; });
arch.forEach(function (p) {
  const id = CHAR2ID[p.char] && BOOKS[CHAR2ID[p.char]] ? CHAR2ID[p.char] : 'archive';
  counts[id] = (counts[id] || 0) + 1;
});

const people = {};
const totalStories = Object.keys(BOOKS).reduce(function (n, id) {
  const b = BOOKS[id];
  return n + (b.chapters || []).length + (b.timeline || []).length + (b.behind || []).length;
}, 0);

PEOPLE.filter(function (p) { return p.status === 'done' && BOOKS[p.id]; }).forEach(function (p) {
  const b = BOOKS[p.id];
  people[p.name] = {
    id: p.id,                                       // BOOKS 数据键，不再是路由
    route: '#/char/' + encodeURIComponent(p.name), // 实际站内地址
    actor: p.actor,
    volume: b.volume || '',
    stories: p.bookStories || 0,
    photos: counts[p.id] || 0
  };
});

/* 新增信源（含可点击 URL），供主站信源页引用 */
const sources = [];
(w.EXTRA_SOURCES || []).forEach(function (k) {
  const r = REF[k];
  if (r && r.url && r.url.indexOf('http') === 0) sources.push({ name: r.name, url: r.url });
});

const bridge = {
  updated: '2026-11-12',
  base: '#/char/',
  edition: w.SITE.edition,
  peopleCount: Object.keys(people).length,
  totalStories: totalStories,
  totalPhotos: photos.length + arch.length,
  daiyuPhotos: photos.length,
  archivePhotos: arch.length,
  people: people,
  sources: sources
};

const out = '/* 人物深度资料索引 · 由 scripts/build_bridge.js 自动生成，请勿手工编辑\n' +
            ' * 21 位人物的双线故事 / 判词 / 影像已并入主站人物详情页（#/char/<姓名>），\n' +
            ' * 「女儿册」仅为人物图鉴下拉筛选中的一个分类；id 为数据键，route 为站内地址。\n' +
            ' * 生成时间：' + new Date().toISOString().slice(0, 10) + '\n' +
            ' */\n' +
            'window.NVERCE = ' + JSON.stringify(bridge, null, 2) + ';\n';

fs.writeFileSync(path.join(ROOT, 'data/bridge.js'), out, 'utf8');
console.log('bridge.js 已生成：' + bridge.peopleCount + ' 位人物 / ' +
            bridge.totalStories + ' 则故事 / ' + bridge.totalPhotos + ' 帧影像 / ' +
            sources.length + ' 条新增信源');
Object.keys(people).forEach(function (n) {
  console.log('  ' + n + ' → ' + people[n].route + ' · 故事 ' + people[n].stories + ' · 影像 ' + people[n].photos);
});
