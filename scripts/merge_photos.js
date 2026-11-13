/* 把「女儿册」专采的 201 帧林黛玉 / 陈晓旭照片并入主站唯一图库
 * 用法： node scripts/merge_photos.js
 *
 * 1) 复制 _archive/retired/nverce-source/images/* → assets/photos/nv-*
 *    _archive/retired/nverce-source/thumbs/*       → assets/photos/nvt-*
 * 2) 依据 data/nv-photos-source.js 的原始出处字段，生成 data/photos-nverce.js
 *    （window.HLM87.extraPhotos），由 index.html 在运行时 concat 进 H.photos.items。
 *
 * 采集底本（与 assets/photos/ 逐字节相同的副本，已移出仓库）保留在
 * _archive/retired/nverce-source/，供 scripts/fetch_nverce_photos.py 复采；
 * 站点实际只读取 assets/photos/ 这一个图库目录。
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const SITE = path.resolve(__dirname, '..');
const SRC = path.join(SITE, '_archive', 'retired', 'nverce-source'); // 采集底本（本地归档，已移出 git）
const DEST = path.join(SITE, 'assets', 'photos');
const ctx = vm.createContext({ window: {}, console: console });
vm.runInContext(fs.readFileSync(path.join(SITE, 'data/nv-photos-source.js'), 'utf8'), ctx, { filename: 'data/nv-photos-source.js' });
const PHOTOS = ctx.window.PHOTOS || [];

function base(p) { return path.basename(p); }
function hostOf(page, imageUrl) {
  const u = page || imageUrl || '';
  const m = String(u).match(/^https?:\/\/([^/]+)/);
  return m ? m[1] : '公开页面';
}
function kindOf(cat) { return cat === '生活 · 写真' ? '生活照' : '剧照'; }

let copied = 0, skipped = 0;
const items = PHOTOS.map(function (p) {
  const file = 'nv-' + base(p.file);
  const thumb = 'nvt-' + base(p.thumb || p.file);
  [[p.file, file], [p.thumb || p.file, thumb]].forEach(function (pair) {
    const from = path.join(SRC, pair[0]);
    const to = path.join(DEST, pair[1]);
    if (!fs.existsSync(from)) throw new Error('缺少源文件：' + pair[0]);
    if (fs.existsSync(to)) { skipped++; return; }
    fs.copyFileSync(from, to);
    copied++;
  });
  return {
    id: 'nv' + String(p.id).padStart(3, '0'),
    file: file,
    thumb: thumb,
    char: '林黛玉',
    actor: '陈晓旭',
    kind: kindOf(p.cat),
    desc: (p.caption || '陈晓旭 · 林黛玉') + ' · ' + (p.cat || ''),
    host: hostOf(p.page, p.source),
    srcUrl: p.page || p.source || '',
    date: '2026-11-11',
    origin: '女儿册采集',
    cat: p.cat || '',
    title: p.title || '',
    source: p.source || ''
  };
});

const out = '/* 女儿册专采 201 帧（由 scripts/merge_photos.js 生成，请勿手工编辑）\n' +
  ' * 已并入 assets/photos/，与主站原 149 张同属一个图库；\n' +
  ' * 每条保留来源页面 URL、站点域名、采集日期与原始分类。\n' +
  ' * 由 index.html 运行时 concat 进 H.photos.items（避免脚本加载顺序依赖）。\n' +
  ' */\n' +
  'window.HLM87 = window.HLM87 || {};\n' +
  'window.HLM87.extraPhotos = [\n' +
  items.map(function (p) { return '  ' + JSON.stringify(p); }).join(',\n') + '\n' +
  '];\n';
fs.writeFileSync(path.join(SITE, 'data/photos-nverce.js'), out, 'utf8');
console.log('复制 ' + copied + ' 个文件（已存在跳过 ' + skipped + '），生成 ' + items.length + ' 条图库记录');
console.log('assets/photos/ 现有 ' + fs.readdirSync(DEST).filter(function (f) { return /\.(jpg|jpeg|png|gif|webp)$/i.test(f); }).length + ' 张图片');
