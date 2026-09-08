# 修复：伪裁片被误分类为有效裁片并错误纳入缝合

## 1. 问题描述

处理 `13FG短袖.reviewed.dxf` 时，系统将本应为 `unknown_panel` 的碎片裁片
（`panel_003`、`panel_006`）错误识别为 `back_bodice` / `front_bodice`，
并错误生成缝合关系（如 `panel_006 ↔ panel_005(binding_strip)` 的 `seam_pair`）。

## 2. 根因分析

- DXF 中存在由碎线/内部标记/残片形成的**极小闭合环**，被 `detect_panels` 检测为面板。
- 这些碎片裁片的 `Piece Name`（如 `FG短袖_后片`、`FG短袖_前片`）与真实裁片相同，
  因此 `assign_roles` 依据名称将其分配了有效角色。
- 有效角色（front/back/sleeve 等）会进入缝合关系生成流程，导致碎片被错误缝合。

### 尺寸证据（13FG）

| panel | piece_name | bbox | 尺寸占比(max/全局) | 判定 |
|---|---|---|---|---|
| panel_002 | 后片 | 646.7×771.0 | 0.996 | 真实 |
| panel_004 | 前片 | 646.7×774.5 | 1.000 | 真实 |
| panel_005 | 领(binding) | 482.0×62.7 | 0.622 | 真实 |
| **panel_003** | 后片 | **68.3×12.7** | **0.088** | **伪** |
| **panel_006** | 前片 | **86.7×76.7** | **0.112** | **伪** |

### 全样本统计（11 款）

- **伪裁片**：`13FG`(0.09/0.11)、`14KITH`(0.13)、`15LV`(0.02×4)、`9BOY`(0.09)，**均 ≤ 0.13**。
- **真实小裁片**：`11CK`门襟(0.24)、拉边(0.24)、`9BOY`袖(0.25)、`10CDG`后袖(0.28)，**均 ≥ 0.24**。
- 存在明显间隙（0.13 ↔ 0.24），取阈值 **0.20** 可完全分离。

## 3. 修复方案与实施步骤

### 3.1 新增尺寸占比判定阈值 `semantics.py`

```python
_UNKNOWN_SIZE_RATIO_MAX = 0.20
```

### 3.2 新增伪裁片重标记函数 `semantics.py`

```python
def mark_spurious_panels_unknown(panels) -> int:
    # 计算本服装最大裁片边长 max_side
    # 对每个 panel：ratio = max(w,h) / max_side
    #   若 ratio < 0.20 且未标记 unknown：role -> "unknown_panel"，role_source -> "size_degenerate"，日志 + 计数
    # 返回标记数量
```

### 3.3 缝合过滤机制（既有 Feature 2，`semantics.py` match_seams 步骤0）

- 对 `role == unknown_panel` 的裁片：写入 `panel["edge_participation_note"]` 提示原因，
  并从缝合范围整体剔除（不进入任何前后片/袖/领/几何兜底步骤）。

### 3.4 编排接入 `service.py`

```python
assign_roles(panels, piece_info["handle_to_piece"])
reclassify_binding_strips(panels)          # 既有：矩形领口滚条 -> binding_strip
mark_spurious_panels_unknown(panels)       # 新增：小尺寸伪裁片 -> unknown_panel
```

## 4. 测试结果

### 4.1 全样本回归（11 款，unknown 识别准确率 100%）

| 样本 | 识别为 unknown 的伪裁片 | 被缝合引用 | 真实裁片保留 |
|---|---|---|---|
| 12后背小熊短袖 | 无 | 无 | 前/后/袖/领 |
| 10CDG短袖 | 无 | 无 | 前/后/领 |
| 11CKPOLO衫 | 无 | 无 | 前/后/袖/门襟/拉边 |
| 12DIOR短袖 | 无 | 无 | 前/后/袖/领 |
| **13FG短袖** | **panel_003, panel_006** | **无** | 前/后/袖/领 |
| **14KITH短袖** | **panel_005** | **无** | 前/后/袖/领 |
| **15LV牛仔短袖** | **panel_006~009** | **无** | 前/后/袖 |
| 32下摆开叉短袖 | 无 | 无 | 前/后/袖/领 |
| 42下摆褶短袖 | 无 | 无 | 前/后/袖/领 |
| 611腰刺绣短袖 | 无 | 无 | 前/后/袖 |
| **9BOY连袖短袖** | **panel_005** | **无** | 前/后/袖/领 |

- 共识别 8 个伪裁片，全部正确标记为 `unknown_panel`，**0 个被任何缝合引用**。
- 真实小裁片（门襟/拉边/后袖）**未被误杀**，其余有效裁片识别与缝合关系不受影响。

### 4.2 13FG 修复前后对比

| 项 | 修复前 | 修复后 |
|---|---|---|
| panel_003 / panel_006 角色 | back/front_bodice | **unknown_panel** |
| 错误缝合 `panel_006↔binding` | 存在（stitch_010/011） | **已清除** |
| 有效缝合（肩/侧/袖山/领滚边） | 保留 | 保留 |
| 不参与缝合原因提示 | 无 | 写入 `edge_participation_note` |

### 4.3 单元测试

`test_features.py` 扩展 **Feature2：伪/琐碎尺寸裁片重标记为 unknown**：
- 大裁片保持 `front_bodice`、小裁片重标记、标记数量正确、`role_source=size_degenerate`、
  缝合结果不引用伪裁片 —— 全通过。

**合计：21/21 用例通过。**

## 5. 结论

修复后系统可正确处理含 `unknown_panel` 的款式：伪/碎片裁片被正确标记为
`unknown_panel`，其所有边缘被完全排除在缝合关系之外，且不影响正常裁片的识别
与缝合关系建立。