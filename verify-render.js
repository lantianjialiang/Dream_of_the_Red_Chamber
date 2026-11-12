// 87版红楼梦资料站 · 渲染冒烟测试（node 运行）
// v2.3：「女儿册」不再是独立册页 / 册卡区块，只是「全部人物」下拉里的一个分类；
// 21 位人物的双线故事、判词、年表、幕后、诗作、语录与影像全部并入各自的人物详情页。
// 图库 = 资料馆 149 + 女儿册 201 + 网络补采（动态数量），逐张带出处。
const fs = require("fs");
const path = require("path");
const root = __dirname;

// ---- 读取并加载 data/*.js ----
const dataDir = path.join(root, "data");
const files = fs.readdirSync(dataDir).filter(f => f.endsWith(".js"));
const HLM = {};
global.window = HLM;
for (const f of files) {
  const code = fs.readFileSync(path.join(dataDir, f), "utf8");
  eval(code); // 每个文件执行 window.HLM87.xxx = ...
  if (f === "photos-nverce.js") console.log("[data] extraPhotos:", (HLM.HLM87.extraPhotos || []).length);
  if (f === "photos-web.js") console.log("[data] webPhotos:", (HLM.HLM87.webPhotos || []).length);
}
// 人物深度资料（双线故事 / 判词 / 信源 / 索引），主站 index.html 通过 <script> 引入
["nverce/data/content.js", "nverce/data/people-extra.js", "nverce/data/memoir.js", "nverce/data/bridge.js"].forEach(function (f) {
  eval(fs.readFileSync(path.join(root, f), "utf8"));
});
console.log("[data] loaded:", files.length, "main files + 4 profile files; keys:", Object.keys(HLM).join(", "));

// ---- DOM shim ----
const app = { innerHTML: "" };
const registry = {}; // 记录具 id 元素，供抽查实际渲染结果
function makeEl() {
  return {
    innerHTML: "", value: "", dataset: {}, style: {},
    classList: { toggle() {}, add() {}, remove() {} },
    addEventListener() {},
  };
}
global.document = {
  getElementById(id) {
    if (id === "app") return app;
    if (!registry[id]) registry[id] = makeEl();
    return registry[id];
  },
  querySelectorAll() { return []; },
};
global.location = { hash: "#/list", href: "" };
global.window.addEventListener = function(){};
global.window.scrollTo = function(){};

// ---- 加载主页面内联脚本并渲染每个视图 ----
const html = fs.readFileSync(path.join(root, "index.html"), "utf8");
const inline = html.match(/<script>([\s\S]*?)<\/script>/)[1];
eval(inline);

// book/* 为旧册页地址，仅作兼容，应直接渲染对应人物详情
const views = ["home","list","book/daiyu","book/baochai","char/林黛玉","char/薛宝钗","episodes","relations","timeline","music","behind","crew","gossip","memorial","compare","sources","photos"];
let ok = 0, fail = 0;
for (const v of views) {
  try {
    location.hash = "#/" + v;
    render();
    const len = app.innerHTML.length;
    const hasTag = app.innerHTML.indexOf("<") >= 0;
    console.log("[view] #/" + v + "  len=" + len + "  html=" + (len > 300 ? "OK" : "TOO SHORT") + (hasTag ? "" : "  NO-HTML"));
    ok++;
  } catch (e) {
    fail++;
    console.log("[view] #/" + v + "  ERROR: " + e.message);
  }
}

// ---- 关键内容抽查 ----
function check(label, cond) {
  console.log((cond ? "[PASS] " : "[FAIL] ") + label);
  if (!cond) fail++;
}
location.hash = "#/episodes"; render();
check("episodes 含『第36集 · 白茫茫厚地高天』", app.innerHTML.indexOf("白茫茫厚地高天") > 0);
location.hash = "#/behind"; render();
check("behind 合并页含『剧组轶闻』与幕后故事", app.innerHTML.indexOf("幕后故事") > 0 && app.innerHTML.indexOf("剧组轶闻") > 0);

location.hash = "#/list"; render();
check("list 含『人物图鉴』且卡片渲染缩略图 pt", app.innerHTML.indexOf("人物图鉴") > 0 && (registry["lres"].innerHTML.indexOf("class=\"pt\"") > 0));
check("list 缩略图含林黛玉剧照", registry["lres"].innerHTML.indexOf("assets/photos/lindaiyu.jpg") > 0);
check("人物图鉴不再有女儿册册卡网格与独立板块", app.innerHTML.indexOf("bookgrid") < 0 && app.innerHTML.indexOf("bookcard") < 0 && app.innerHTML.indexOf("女儿册 · 人物故事与影像") < 0);
check("女儿册是「全部人物」下拉里的一个分类", app.innerHTML.indexOf('id="lb"') > 0 && app.innerHTML.indexOf("女儿册人物（21）") > 0 && registry["lres"].innerHTML.indexOf("bk-badge") < 0);

location.hash = "#/book/daiyu"; render();
check("旧册页地址直接渲染人物详情，无独立册页 / 双卷标签页", app.innerHTML.indexOf("卷一 · 书中的她") < 0 && app.innerHTML.indexOf("pane-real") < 0 && app.innerHTML.indexOf("书中故事 · 按回目编排") > 0 && app.innerHTML.indexOf("资料依据") > 0 && app.innerHTML.indexOf("#/book/") < 0);
check("黛玉详情含第五回判词与出处链接", app.innerHTML.indexOf("可叹停机德") > 0 && app.innerHTML.indexOf("查看出处") > 0);
check("黛玉详情含影像与图库跳转入口", app.innerHTML.indexOf("#/photos") > 0 && app.innerHTML.indexOf("photos-mini") > 0);
location.hash = "#/book/baochai"; render();
check("宝钗详情含金锁故事与央广网出处", app.innerHTML.indexOf("金锁初现") > 0 && app.innerHTML.indexOf("央广网") > 0);
check("人物详情含返回人物图鉴链接", app.innerHTML.indexOf("#/list") > 0);

location.hash = "#/char/林黛玉"; render();
check("char 详情含『焚稿焚帕、泪尽而逝』", app.innerHTML.indexOf("焚稿焚帕") > 0);
check("char 详情含影像区块与本地图片", app.innerHTML.indexOf("photos-mini") > 0 && app.innerHTML.indexOf("assets/photos/lindaiyu.jpg") > 0);
check("char 详情内含双线故事、判词、年表与资料依据，且无册页跳转", app.innerHTML.indexOf("书中故事 · 按回目编排") > 0 && app.innerHTML.indexOf("第五回判词与曲子") > 0 && app.innerHTML.indexOf("扮演者现实人生 · 年表") > 0 && app.innerHTML.indexOf("资料依据") > 0 && app.innerHTML.indexOf("#/book/") < 0);
location.hash = "#/char/薛宝钗"; render();
check("薛宝钗档案内含双线故事与资料依据", app.innerHTML.indexOf("金锁初现") > 0 && app.innerHTML.indexOf("资料依据") > 0 && app.innerHTML.indexOf("#/book/") < 0);
check("回忆录一手材料并入人物详情的既有板块", app.innerHTML.indexOf("幕后细节") > 0 && app.innerHTML.indexOf("欧阳奋强《1987，我们的红楼梦》") > 0);
check("人物详情给出回忆录可核查文字版链接", app.innerHTML.indexOf("当事人回忆录") > 0 && app.innerHTML.indexOf("1987我们的红楼梦-欧阳奋强.md") > 0);

location.hash = "#/relations"; render();
check("relations 含两个 SVG", (app.innerHTML.match(/<svg/g) || []).length >= 2);
location.hash = "#/memorial"; render();
check("memorial 含『郑铮』", app.innerHTML.indexOf("郑铮") > 0);
location.hash = "#/sources"; render();
check("sources 含勘误『周岭』", app.innerHTML.indexOf("周岭") > 0);
check("信源页列出女儿册新增报道信源", app.innerHTML.indexOf("女儿册新增信源") > 0 && app.innerHTML.indexOf("news.cctv.cn") > 0);
check("信源页新增本轮影像信源聚合表", app.innerHTML.indexOf("本轮影像信源") > 0 && app.innerHTML.indexOf("欧阳宝玉") > 0);

const WEB = HLM.HLM87.webPhotos || [];
const BOOK = HLM.HLM87.bookPhotos || [];
const TOTAL = 149 + 201 + WEB.length + BOOK.length;
location.hash = "#/photos"; render();
check("图库总数动态显示为 " + TOTAL + " 张", registry["pres"].innerHTML.indexOf(TOTAL + " 张") > 0);
check("图库分批渲染（当前显示 120 张 + 显示更多）", registry["pres"].innerHTML.indexOf("当前显示 120 张") > 0 && registry["pres"].innerHTML.indexOf("再显示 120 张") > 0);
check("图库渲染本地图片引用不少于 200 处", (registry["pres"].innerHTML.match(/assets\/photos\//g) || []).length >= 200);
check("图库含来源筛选（女儿册采集 / 微信公众号图文）", app.innerHTML.indexOf("女儿册采集") > 0 && app.innerHTML.indexOf("微信公众号图文") > 0 && app.innerHTML.indexOf("id=\"po\"") > 0);
check("图库卡片带出处链接与归属标注", registry["pres"].innerHTML.indexOf("查看出处") > 0);

// ---- 架构约束：不得再出现独立黑色子站入口 / 独立册页 ----
check("主站导航已移除 special 样式按钮", html.indexOf("menu special") < 0);
check("主站不再链接 nverce/index.html", html.indexOf("nverce/index.html") < 0);
check("主站引入人物册数据与四路合并图库数据", html.indexOf("nverce/data/people-extra.js") > 0 && html.indexOf("nverce/data/memoir.js") > 0 && html.indexOf("data/photos-nverce.js") > 0 && html.indexOf("data/photos-web.js") > 0 && html.indexOf("data/photos-book.js") > 0);
check("主站不再有独立册页视图 / 册卡网格 / 双卷标签页", html.indexOf("viewBook(") < 0 && html.indexOf("bookletCards()") < 0 && html.indexOf("bookgrid") < 0 && html.indexOf("pane-real") < 0 && html.indexOf("bookTab(") < 0);
check("人物详情直接拼装双线故事与资料依据", html.indexOf("charStorySections(B,c.name)") > 0 && html.indexOf("charSourceBox(B)") > 0);
check("旧 #/book/ 地址仍兼容，落到人物详情", html.indexOf('case "book"') > 0 && html.indexOf("viewChar(bb&&bb.name") > 0);
check("每张补采影像均有出处字段", WEB.length > 0 && WEB.every(function(p){ return p.host && p.srcUrl && p.date && p.origin && p.title; }));
const sub = fs.readFileSync(path.join(root, "nverce/index.html"), "utf8");
check("nverce/index.html 已改为跳转主站人物图鉴", sub.indexOf("../index.html#/list") >= 0 && sub.indexOf("assets/app.js") < 0);

console.log("\nRESULT: views ok=" + ok + " fail=" + fail);
process.exit(fail ? 1 : 0);
