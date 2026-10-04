/* 生成图库采集状态清单（有图/缺图），输出 markdown */
global.window = {HLM87:{}};
require('C:/Users/liang_jia/Desktop/Other/Dream_of_the_Red_Chamber/data/characters.js');
require('C:/Users/liang_jia/Desktop/Other/Dream_of_the_Red_Chamber/data/photos.js');
const C = window.HLM87.characters;
const P = window.HLM87.photos.items || [];

const byChar = {};
P.forEach(p => { if(!byChar[p.char]) byChar[p.char]=[]; byChar[p.char].push(p); });

const order = {core:0, important:1, entry:2, mentioned:3};
const label = {core:"核心", important:"重要", entry:"一般", mentioned:"提及"};
const groups = {};
let withPhoto = 0;
C.forEach(c => {
  const phs = byChar[c.name] || [];
  if (phs.length) withPhoto++;
  const key = c.status;
  if(!groups[key]) groups[key] = [];
  groups[key].push({name:c.name, n:phs.length, files:phs.map(p=>p.file)});
});

let md = "# 87版《红楼梦》图库采集状态（2026-10-03）\n\n";
md += "## 总览\n\n";
const charNames = {};
C.forEach(c => { charNames[c.name] = true; });
const groupShots = P.filter(p => !charNames[p.char]).length;
md += `- 收录人物：${C.length} 人\n- 已入库图片：${P.length} 张（其中多人合影/剧组照 ${groupShots} 张）\n- 有图人物：${withPhoto} 人\n- 缺图人物：${C.length - withPhoto} 人\n\n`;
md += "> 图源均为网络公开流传剧照/生活照，已本地入库并标注出处页面；缺图人物如实标注『待补』，宁缺毋滥。\n\n";

Object.keys(groups).sort((a,b)=>order[a]-order[b]).forEach(k => {
  const arr = groups[k].sort((a,b)=>b.n-a.n || a.name.localeCompare(b.name,"zh"));
  md += `## ${label[k]}级（${arr.length} 人）\n\n`;
  md += "| 人物 | 图片数 | 文件 |\n|---|---|---|\n";
  arr.forEach(g => {
    md += `| ${g.name} | ${g.n>0?"✅ "+g.n:"❌ 待补"} | ${g.n>0?g.files.join("、"):"—"} |\n`;
  });
  md += "\n";
});

const fs = require('fs');
const BOM = '\uFEFF';
fs.writeFileSync('C:/Users/liang_jia/Desktop/Other/Dream_of_the_Red_Chamber/图库采集状态.md', BOM + md, 'utf8');
console.log("written, chars:", md.length);
console.log("photos:", P.length, "withPhoto:", withPhoto, "missing:", C.length - withPhoto);
