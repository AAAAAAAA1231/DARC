from backend.data_sources.lottery import parse_17500_txt, parse_500_xml


SSQ_XML = """<?xml version="1.0" encoding="utf-8"?>
<xml>
<row expect="2025090" opencode="05,06,11,16,21,33|12" opentime="2025-09-01 21:15:00"/>
<row expect="2025089" opencode="01,02,03,04,05,06|07" opentime="2025-08-31 21:15:00"/>
</xml>
"""

D3_XML = """<?xml version="1.0" encoding="utf-8"?>
<xml>
<row expect="2025244" opencode="1,2,3" opentime="2025-09-01"/>
</xml>
"""


def test_parse_500_ssq_xml():
    rows = parse_500_xml(SSQ_XML, "ssq", 10)
    assert len(rows) == 2
    assert rows[0]["issue"] == "2025090"
    assert rows[0]["numbers"]["red"] == ["05", "06", "11", "16", "21", "33"]
    assert rows[0]["numbers"]["blue"] == ["12"]
    assert rows[0]["source"] == "kaijiang.500.com"
    assert rows[0]["draw_time"] is not None


def test_parse_500_3d_digits():
    rows = parse_500_xml(D3_XML, "3d", 5)
    assert rows[0]["numbers"]["digits"] == ["1", "2", "3"]


def test_parse_17500_ssq_newest_first():
    text = "\n".join(
        [
            "2025089 2025-08-31 01 02 03 04 05 06 07",
            "2025090 2025-09-01 05 06 11 16 21 33 12",
        ]
    )
    rows = parse_17500_txt(text, "ssq", 1)
    assert len(rows) == 1
    assert rows[0]["issue"] == "2025090"
    assert rows[0]["numbers"]["blue"] == ["12"]
    assert rows[0]["source"] == "data.17500.cn"
