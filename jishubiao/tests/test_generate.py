from jishubiao.engine.export import export_docx, export_markdown
from jishubiao.engine.generate import generate_bid, parse_tender_flags, select_codes


def test_codes_for_residential_frame_shear():
    codes = select_codes("房屋建筑", "框剪", residential=True)
    nums = {c["code"] for c in codes}
    assert "GB 55008-2021" in nums
    assert "GB 55038-2025" in nums
    assert "GB 50204-2015" in nums
    assert "CJJ 1-2008" not in nums
    assert "GB 50010-2002" not in nums


def test_codes_for_municipal_road():
    codes = select_codes("市政道路", "不适用（市政/公路）")
    nums = {c["code"] for c in codes}
    assert "CJJ 1-2008" in nums
    assert "GB 55008-2021" not in nums
    assert "GB 55001-2021" in nums


def test_tender_flags_inject_bim_and_pc():
    flags = parse_tender_flags("本工程应用 BIM 管线综合，装配率 50%，创建市优。")
    assert "BIM" in flags and "装配式" in flags and "创优" in flags
    doc = generate_bid(
        {
            "name": "测试住宅",
            "specialty": "房屋建筑",
            "structure": "框剪",
            "residential": True,
            "tender_text": "须应用 BIM，装配式施工，创建市级文明工地。",
            "bidder": "某某建设",
        }
    )
    titles = " ".join(doc["toc"])
    assert "BIM" in titles
    assert "装配式" in titles or any("装配式" in s["heading"] + s["body"] for ch in doc["chapters"] for s in ch["sections"])
    assert any(c["code"].startswith("GB/T 51269") or c["code"].startswith("GB/T 51226") for c in doc["codes"])
    assert "GB 55008-2021" in " ".join(c["code"] for c in doc["codes"])


def test_export_docx_and_markdown(tmp_path):
    doc = generate_bid({"name": "导出试验工程", "specialty": "房屋建筑", "structure": "框架", "residential": False})
    md = export_markdown(doc)
    assert "编制依据" in md
    assert "GB 55001-2021" in md
    path = export_docx(doc, tmp_path / "t.docx")
    assert path.exists() and path.stat().st_size > 2000
