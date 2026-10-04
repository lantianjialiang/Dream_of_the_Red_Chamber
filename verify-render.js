// 87版红楼梦资料站 · 渲染冒烟测试（node 运行）
const fs = require("fs");
const path = require("path");
const root = "C:/Users/liang_jia/Desktop/Other/Dream_of_the_Red_Chamber";

// ---- 读取并加载 data/*.js ----
const dataDir = path.join(root, "data");
const files = fs.readdirSync(dataDir).filter(f => f.endsWith(".js"));
const HLM = {};
global.window = HLM;
for (const f of files) {
  const code = fs.readFileSync(path.join(dataDir, f), "utf8");
  eval(code); // 每个文件执行 window.HLM87.xxx = ...
}
console.log("[data] loaded:", files.length, "files; keys:", Object.keys(HLM).join(", "));

// ---- DOM shim ----
const app = { innerHTML: "" };
const registry = {}; // 记录具 id 元素，供抽查实际渲染结果
function makeEl() {
  return {
    innerHTML: "", value: "", dataset: {},
    classList: { toggle() {} },
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

const views = ["home","list","char/林黛玉","episodes","relations","timeline","music","behind","crew","gossip","memorial","compare","sources","photos"];
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
}
location.hash = "#/episodes"; render();
check("episodes 含『第36集 · 白茫茫厚地高天』", app.innerHTML.indexOf("白茫茫厚地高天") > 0);
location.hash = "#/behind"; render();
check("behind 合并页含『剧组轶闻』与幕后故事", app.innerHTML.indexOf("幕后故事") > 0 && app.innerHTML.indexOf("剧组轶闻") > 0);
location.hash = "#/list"; render();
check("list 含『人物图鉴』且卡片渲染缩略图 pt", app.innerHTML.indexOf("人物图鉴") > 0 && (registry["lres"].innerHTML.indexOf("class=\"pt\"") > 0));
check("list 缩略图含林黛玉剧照", registry["lres"].innerHTML.indexOf("assets/photos/lindaiyu.jpg") > 0);
location.hash = "#/char/林黛玉"; render();
check("char 详情含『焚稿焚帕、泪尽而逝』", app.innerHTML.indexOf("焚稿焚帕") > 0);
check("char 详情含『剧照』区块与本地图片", app.innerHTML.indexOf("photos-mini") > 0 && app.innerHTML.indexOf("assets/photos/lindaiyu.jpg") > 0);
location.hash = "#/relations"; render();
check("relations 含两个 SVG", (app.innerHTML.match(/<svg/g) || []).length >= 2);
location.hash = "#/memorial"; render();
check("memorial 含『郑铮』", app.innerHTML.indexOf("郑铮") > 0);
location.hash = "#/sources"; render();
check("sources 含勘误『周岭』", app.innerHTML.indexOf("周岭") > 0);
location.hash = "#/photos"; render();
check("photos 含本地图片引用 assets/photos/", (registry["pres"].innerHTML.indexOf("assets/photos/lindaiyu.jpg") > 0));
check("photos 渲染本地图片引用不少于 119 张", (registry["pres"].innerHTML.match(/assets\/photos\//g) || []).length >= 238);
check("photos 含生活照条目（55 张）", (registry["pres"].innerHTML.match(/生活照/g) || []).length >= 55);
check("photos 含剧照/生活照筛选与检索框", app.innerHTML.indexOf("ph-filter") > 0 && app.innerHTML.indexOf("生活照") > 0);

console.log("\nRESULT: views ok=" + ok + " fail=" + fail);
process.exit(fail ? 1 : 0);
