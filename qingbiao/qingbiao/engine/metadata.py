from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

NS = {
    "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
    "ep": "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties",
    "vt": "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes",
}


def _text(root: ET.Element | None, path: str) -> str:
    if root is None:
        return ""
    node = root.find(path, NS)
    return (node.text or "").strip() if node is not None else ""


def _read_xml(zf: zipfile.ZipFile, name: str) -> ET.Element | None:
    try:
        with zf.open(name) as fh:
            return ET.parse(fh).getroot()
    except KeyError:
        return None
    except ET.ParseError:
        return None


def office_openxml_properties(path: Path) -> dict[str, Any]:
    out: dict[str, Any] = {"kind": "openxml", "path": path.name}
    try:
        with zipfile.ZipFile(path) as zf:
            core = _read_xml(zf, "docProps/core.xml")
            app = _read_xml(zf, "docProps/app.xml")
            out.update(
                {
                    "creator": _text(core, "dc:creator"),
                    "last_modified_by": _text(core, "cp:lastModifiedBy"),
                    "created": _text(core, "dcterms:created"),
                    "modified": _text(core, "dcterms:modified"),
                    "revision": _text(core, "cp:revision"),
                    "title": _text(core, "dc:title"),
                    "last_printed": _text(core, "cp:lastPrinted"),
                    "application": _text(app, "ep:Application"),
                    "app_version": _text(app, "ep:AppVersion"),
                    "company": _text(app, "ep:Company"),
                    "manager": _text(app, "ep:Manager"),
                    "template": _text(app, "ep:Template"),
                    "hyperlink_base": _text(app, "ep:HyperlinkBase"),
                    "total_time": _text(app, "ep:TotalTime"),
                }
            )
            names = set(zf.namelist())
            out["has_vba"] = any(n.startswith("xl/vba") or n.endswith("vbaProject.bin") for n in names)
            out["worksheets"] = sorted(n for n in names if n.startswith("xl/worksheets/"))
    except zipfile.BadZipFile:
        out["kind"] = "not-zip"
        out["error"] = "不是 Office Open XML 压缩包"
    return {k: v for k, v in out.items() if v not in ("", None, [])}


def ole_properties(path: Path) -> dict[str, Any]:
    out: dict[str, Any] = {"kind": "ole", "path": path.name}
    try:
        import olefile
    except ImportError:
        out["error"] = "未安装 olefile，无法读取旧版 .xls 属性"
        return out
    if not olefile.isOleFile(path):
        out["error"] = "不是 OLE 复合文档"
        return out
    with olefile.OleFileIO(str(path)) as ole:
        meta = ole.get_metadata()
        mapping = {
            "creator": "author",
            "last_modified_by": "last_saved_by",
            "company": "company",
            "application": "creating_application",
            "title": "title",
            "revision": "revision_number",
        }
        for key, attr in mapping.items():
            val = getattr(meta, attr, None)
            if val:
                out[key] = val if isinstance(val, str) else str(val)
        if meta.create_time:
            out["created"] = str(meta.create_time)
        if meta.last_saved_time:
            out["modified"] = str(meta.last_saved_time)
    return out


def pdf_properties(path: Path) -> dict[str, Any]:
    out: dict[str, Any] = {"kind": "pdf", "path": path.name}
    try:
        from pypdf import PdfReader
    except ImportError:
        out["error"] = "未安装 pypdf"
        return out
    reader = PdfReader(str(path))
    info = reader.metadata or {}
    out["creator"] = str(info.get("/Creator") or info.get("/Author") or "")
    out["last_modified_by"] = str(info.get("/Author") or "")
    out["application"] = str(info.get("/Producer") or "")
    out["created"] = str(info.get("/CreationDate") or "")
    out["modified"] = str(info.get("/ModDate") or "")
    out["title"] = str(info.get("/Title") or "")
    return {k: v for k, v in out.items() if v}


def extract_file_properties(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xlsm", ".docx"}:
        return office_openxml_properties(path)
    if suffix in {".xls", ".doc"}:
        return ole_properties(path)
    if suffix == ".pdf":
        return pdf_properties(path)
    return {"kind": "unknown", "path": path.name, "error": f"暂不解析 {suffix} 属性"}


def fingerprint(props: dict[str, Any]) -> dict[str, str]:
    keys = ("creator", "last_modified_by", "company", "application", "app_version", "template")
    return {k: str(props.get(k) or "").strip() for k in keys if str(props.get(k) or "").strip()}


def compare_file_properties(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """entries: {bidder, filename, props}"""
    findings: list[dict[str, Any]] = []
    n = len(entries)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = entries[i], entries[j]
            pa, pb = fingerprint(a.get("props") or {}), fingerprint(b.get("props") or {})
            same: list[str] = []
            for key in sorted(set(pa) & set(pb)):
                if pa[key] and pa[key] == pb[key]:
                    same.append(f"{key}={pa[key]}")
            created_a = str((a.get("props") or {}).get("created") or "")
            created_b = str((b.get("props") or {}).get("created") or "")
            if created_a and created_a[:16] == created_b[:16] and created_a[:10]:
                same.append(f"创建时间接近:{created_a} / {created_b}")
            if not same:
                continue
            account_keys = [s for s in same if s.startswith("creator=") or s.startswith("last_modified_by=")]
            machine_keys = [s for s in same if s.startswith("application=") or s.startswith("template=") or s.startswith("app_version=")]
            severity = "高" if account_keys else ("中" if len(same) >= 2 else "低")
            kind = []
            if account_keys:
                kind.append("疑似同一账号")
            if machine_keys:
                kind.append("疑似同一计算机/同一套办公软件环境")
            if not kind:
                kind.append("文件属性存在相同项")
            findings.append(
                {
                    "module": "文件属性",
                    "category": "、".join(kind),
                    "severity": severity,
                    "bidders": [a["bidder"], b["bidder"]],
                    "files": [a.get("filename"), b.get("filename")],
                    "detail": "；".join(same),
                }
            )
    return findings
