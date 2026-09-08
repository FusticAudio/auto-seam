# -*- coding: utf-8 -*-
"""回归测试：批量处理 缝合关系文件 下所有 .reviewed.dxf，输出统计摘要。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app.core.service import annotate_dxf_file  # noqa: E402

DATA_DIR = ROOT.parent / "缝合关系文件"


def main() -> None:
    dxfs = sorted(p for p in DATA_DIR.rglob("*.dxf") if p.is_file())
    print(f"共发现 {len(dxfs)} 个 DXF 文件\n")
    failures: list[str] = []
    total_panels = 0
    total_stitches = 0
    for dxf in dxfs:
        name = dxf.parent.name.replace(".review-package", "")
        try:
            result = annotate_dxf_file(dxf)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{name}: {type(exc).__name__}: {exc}")
            print(f"  [FAIL] {name}: {exc}")
            continue
        garment = result["garment"]
        seam = result["seam"]
        summary = result["summary"]
        panels = summary["panels"]
        stitches = summary["stitches"]
        total_panels += len(panels)
        total_stitches += len(stitches)
        roles = ",".join(p["role"] for p in panels)
        rels = ",".join(s["relation"] for s in stitches)
        print(f"  [OK]   {name}")
        print(f"        版片 {len(panels)}: {roles}")
        print(f"        缝合 {len(stitches)}: {rels}")
        # 输出文件写入到 outputs 目录
        out_dir = ROOT / "outputs" / name
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{summary['garment_id']}.garment.json").write_text(
            json.dumps(garment, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (out_dir / f"{summary['garment_id']}.seam.json").write_text(
            json.dumps(seam, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(f"\n完成: {len(dxfs) - len(failures)}/{len(dxfs)} 成功, "
          f"共 {total_panels} 版片 / {total_stitches} 缝合关系")
    if failures:
        print("\n失败清单:")
        for item in failures:
            print(" ", item)


if __name__ == "__main__":
    main()
