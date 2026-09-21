// 前端点对应纯函数测试：从 index.html 提取纯函数并验证
//  1. 单成员组（滚边条）也能产出两个端点（组起点/组终点）
//  2. 交叉对应 A起点↔B终点、A终点↔B起点
const fs = require("fs");
const path = require("path");

const html = fs.readFileSync(
  path.join(__dirname, "..", "seam-preview", "index.html"),
  "utf8"
);
const a = html.indexOf("<script>");
const b = html.indexOf("</script>", a);
const script = html.slice(a + 8, b);

// 提取指定函数（含其完整函数体）到独立代码段
function extractFn(src, name) {
  const start = src.indexOf("function " + name + "(");
  if (start < 0) throw new Error("function " + name + " not found");
  let i = start;
  while (i < src.length && src[i] !== "{") i++;
  if (i >= src.length) throw new Error("no brace for " + name);
  let depth = 0;
  let j = i;
  for (; j < src.length; j++) {
    const c = src[j];
    if (c === "{") depth++;
    else if (c === "}") {
      depth--;
      if (depth === 0) break;
    }
  }
  return src.slice(start, j + 1);
}
// 取非 0x25->string 的引号转义函数（esc）
const fns = [
  "esc",
  "sdCoreRoundCoord",
  "sdCoreVKey",
  "sdCoreFormatDirection",
  "sdCoreEdgeInfo",
  "sdCoreRefValue",
  "sdCoreParseRef",
  "sdCoreResolveGroupMembers",
  "sdCoreEndpointOptions",
  "sdCoreEndpointChoice",
  "sdCoreCrossMatches",
];
// detectBindingNeckline 依赖常量 BODICE_PANEL_ROLES，随被测函数一并携带
const BODY_ROLES_DECL = `
const BODICE_PANEL_ROLES = new Set([
  "front_bodice","back_bodice","right_front_bodice","left_front_bodice",
  "right_back_bodice","left_back_bodice","back_yoke",
]);`;
const code =
  BODY_ROLES_DECL +
  "\n" +
  ["detectBindingNeckline", "bindingNecklineMatches"]
    .map((n) => extractFn(script, n))
    .join("\n\n") +
  "\n" +
  fns.map((n) => extractFn(script, n)).join("\n\n");

let PASS = 0,
  FAIL = 0;
function check(label, cond) {
  PASS += cond ? 1 : 0;
  FAIL += cond ? 0 : 1;
  console.log(`  [${cond ? "PASS" : "FAIL"}] ${label}`);
}

// ---- 用例数据 -------------------------------------------------
// 单成员组（滚边条）：A/B 两侧大边各为一条竖向成员小边
const bindA = {
  panel_id: "bindA",
  role: "binding_strip",
  edges: [
    { edge_id: "bindA.line", start_point: [10, 60], end_point: [10, 20], length: 40, role: "seam_edge" },
  ],
  edge_groups: [{ group_id: "bindA.g1", member_edge_ids: ["bindA.line"] }],
};
const bindB = {
  panel_id: "bindB",
  role: "binding_strip",
  edges: [
    { edge_id: "bindB.line", start_point: [40, 60], end_point: [40, 20], length: 40, role: "seam_edge" },
  ],
  edge_groups: [{ group_id: "bindB.g1", member_edge_ids: ["bindB.line"] }],
};
// 多成员组（普通大边）：两侧各含两条成员小边
const multiA = {
  panel_id: "mA",
  role: "binding_strip",
  edges: [
    { edge_id: "mA.e1", start_point: [0, 50], end_point: [50, 50], length: 50, role: "seam_edge" },
    { edge_id: "mA.e2", start_point: [50, 50], end_point: [100, 50], length: 50, role: "seam_edge" },
  ],
  edge_groups: [{ group_id: "mA.g1", member_edge_ids: ["mA.e1", "mA.e2"] }],
};
const multiB = {
  panel_id: "mB",
  role: "binding_strip",
  edges: [
    { edge_id: "mB.e1", start_point: [200, 50], end_point: [150, 50], length: 50, role: "seam_edge" },
    { edge_id: "mB.e2", start_point: [150, 50], end_point: [100, 50], length: 50, role: "seam_edge" },
  ],
  edge_groups: [{ group_id: "mB.g1", member_edge_ids: ["mB.e1", "mB.e2"] }],
};

// 前后片（滚边条↔领口一对多用例）
const frontB = {
  panel_id: "frontB",
  role: "front_bodice",
  bbox: { min_x: 0, max_x: 200, min_y: 70, max_y: 120 },
  edges: [{ edge_id: "frontB.neck", start_point: [0, 80], end_point: [50, 80], length: 50, role: "neckline_edge" }],
  edge_groups: [{ group_id: "frontB.neck.g", member_edge_ids: ["frontB.neck"] }],
};
const backB = {
  panel_id: "backB",
  role: "back_bodice",
  bbox: { min_x: 300, max_x: 500, min_y: 30, max_y: 80 },
  edges: [{ edge_id: "backB.neck", start_point: [0, 40], end_point: [50, 40], length: 50, role: "neckline_edge" }],
  edge_groups: [{ group_id: "backB.neck.g", member_edge_ids: ["backB.neck"] }],
};

const garment = { panels: [bindA, bindB, multiA, multiB, frontB, backB] };
const makeRegistry = (panels) => {
  const reg = new Map();
  for (const p of panels)
    for (const e of p.edges) {
      reg.set(e.start_point[0] + "|" + e.start_point[1], { name: "N", id: e.edge_id + "@s" });
      reg.set(e.end_point[0] + "|" + e.end_point[1], { name: "N", id: e.edge_id + "@e" });
    }
  return reg;
};
const sdRegistry = makeRegistry(garment.panels);

// 构造 API（被测函数以 garment / sdRegistry 自由变量、reg 形式参数访问数据）
const api = new Function(
  "garment",
  "sdRegistry",
  code +
    "\nreturn { sdCoreEndpointOptions, sdCoreEndpointChoice, sdCoreCrossMatches, sdCoreRefValue, sdCoreParseRef, detectBindingNeckline, bindingNecklineMatches };"
)(garment, sdRegistry);

console.log("== 1. 单成员组（滚边条）下拉应产出两个端点 ==");
const stitch1 = { stitch_id: "st1", a_groups: ["bindA.g1"], b_groups: ["bindB.g1"] };
const aOpts = api.sdCoreEndpointOptions(stitch1, "A", sdRegistry);
const bOpts = api.sdCoreEndpointOptions(stitch1, "B", sdRegistry);
check("A 侧恰好 2 个端点选项", aOpts.length === 2);
check("B 侧恰好 2 个端点选项", bOpts.length === 2);
check("A 侧含组起点(bindA.line|start)", aOpts.some((o) => o.value === "bindA.line|start"));
check("A 侧含组终点(bindA.line|end)", aOpts.some((o) => o.value === "bindA.line|end"));
check("B 侧含组起点(bindB.line|start)", bOpts.some((o) => o.value === "bindB.line|start"));
check("B 侧含组终点(bindB.line|end)", bOpts.some((o) => o.value === "bindB.line|end"));

console.log("== 2. 交叉对应 A起点↔B终点、A终点↔B起点 ==");
const cross = api.sdCoreCrossMatches(
  api.sdCoreEndpointChoice(stitch1, "A", "start", sdRegistry),
  api.sdCoreEndpointChoice(stitch1, "A", "end", sdRegistry),
  api.sdCoreEndpointChoice(stitch1, "B", "start", sdRegistry),
  api.sdCoreEndpointChoice(stitch1, "B", "end", sdRegistry)
);
check("恰好 2 组", cross.length === 2);
check(
  "match[0] = A起点 ↔ B终点",
  cross[0].a.edge_id === "bindA.line" && cross[0].a.endpoint === "start" &&
    cross[0].b.edge_id === "bindB.line" && cross[0].b.endpoint === "end"
);
check(
  "match[1] = A终点 ↔ B起点",
  cross[1].a.edge_id === "bindA.line" && cross[1].a.endpoint === "end" &&
    cross[1].b.edge_id === "bindB.line" && cross[1].b.endpoint === "start"
);

console.log("== 3. 多成员组仍正确（回归） ==");
const stitch2 = { stitch_id: "st2", a_groups: ["mA.g1"], b_groups: ["mB.g1"] };
const a2 = api.sdCoreEndpointOptions(stitch2, "A", sdRegistry);
const b2 = api.sdCoreEndpointOptions(stitch2, "B", sdRegistry);
check("多成员组 A 侧 2 端点", a2.length === 2);
check("多成员组 B 侧 2 端点", b2.length === 2);
const c2 = api.sdCoreCrossMatches(
  api.sdCoreEndpointChoice(stitch2, "A", "start", sdRegistry),
  api.sdCoreEndpointChoice(stitch2, "A", "end", sdRegistry),
  api.sdCoreEndpointChoice(stitch2, "B", "start", sdRegistry),
  api.sdCoreEndpointChoice(stitch2, "B", "end", sdRegistry)
);
check(
  "match[0] A首边起点↔B末边终点",
  c2[0].a.edge_id === "mA.e1" && c2[0].a.endpoint === "start" &&
    c2[0].b.edge_id === "mB.e2" && c2[0].b.endpoint === "end"
);
check(
  "match[1] A末边终点↔B首边起点",
  c2[1].a.edge_id === "mA.e2" && c2[1].a.endpoint === "end" &&
    c2[1].b.edge_id === "mB.e1" && c2[1].b.endpoint === "start"
);

console.log("== 4. 滚边条 ↔ 大身前后片领口 一对多四点对应 ==");
const chain = (c) => ({
  panelId: c.panel_id,
  edgeIds: c.edge_groups[0].member_edge_ids.slice(),
  groupIds: [c.edge_groups[0].group_id],
  startPoint: c.edges[0].start_point.slice(),
  endPoint: c.edges[0].end_point.slice(),
  length: c.edges[0].length,
});
// 乱序选择：后片领口、滚边条、前片领口
const sel = [chain(backB), chain(bindA), chain(frontB)];
const det = api.detectBindingNeckline(sel);
check("命中一对多场景", !!det);
check("绑定条被识别为主侧", det && det.bindIndex === 1);
check("领口按前(小x)/后(大x)排序", det && det.neck[0] === 2 && det.neck[1] === 0);
// 重排：binding 置顶、领口按前后片排列（模拟 createManualStitch 行为）
const reordered = [sel[det.bindIndex], sel[det.neck[0]], sel[det.neck[1]]];
const bn = api.bindingNecklineMatches(reordered);
check("命中恰好 4 组点对应", bn.length === 4);
const aFirst = { edge_id: "bindA.line", endpoint: "start" };
const aLast = { edge_id: "bindA.line", endpoint: "end" };
const fRef = { edge_id: "frontB.neck", endpoint: "end" };   // 前片 R
const fRef2 = { edge_id: "frontB.neck", endpoint: "start" }; // 前片 L
const bRef = { edge_id: "backB.neck", endpoint: "start" };   // 后片 L
const bRef2 = { edge_id: "backB.neck", endpoint: "end" };    // 后片 R
check("match[0] a.L ↔ 前片领口 R",
  JSON.stringify(bn[0].a) === JSON.stringify(aFirst) && JSON.stringify(bn[0].b) === JSON.stringify(fRef));
check("match[1] a.R ↔ 前片领口 L",
  JSON.stringify(bn[1].a) === JSON.stringify(aLast) && JSON.stringify(bn[1].b) === JSON.stringify(fRef2));
check("match[2] a.L ↔ 后片领口 L",
  JSON.stringify(bn[2].a) === JSON.stringify(aFirst) && JSON.stringify(bn[2].b) === JSON.stringify(bRef));
check("match[3] a.R ↔ 后片领口 R",
  JSON.stringify(bn[3].a) === JSON.stringify(aLast) && JSON.stringify(bn[3].b) === JSON.stringify(bRef2));

console.log(`\n==== 通过 ${PASS} / 失败 ${FAIL} ====`);
process.exit(FAIL ? 1 : 0);