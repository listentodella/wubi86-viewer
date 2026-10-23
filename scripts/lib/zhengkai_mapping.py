"""Confirmed ZhengKai choices, deliberately separate from WenKai's review map."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REVIEW_MAP = REPO / "scripts" / "zhengkai-roots-review.json"
MMH = REPO / "data-src" / "hanzi-writer-data"
ROOT_ID = re.compile(r"^[0-9a-f]{4,6}$")


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_digest(value) -> str:
    return digest_bytes(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                   separators=(",", ":"), allow_nan=False).encode("utf-8"))


def validate_root_id(rid: str) -> int:
    if not isinstance(rid, str) or not ROOT_ID.fullmatch(rid):
        raise ValueError(f"无效的字根编号：{rid!r}")
    cp = int(rid, 16)
    if not (0xE000 <= cp <= 0xF8FF or 0xF0000 <= cp <= 0xFFFFD or 0x100000 <= cp <= 0x10FFFD):
        raise ValueError(f"{rid} 不是 PUA 字根码位")
    return cp


def validate_selection(source: str, strokes: list[int], source_hash: str | None = None,
                       mmh: Path = MMH) -> dict:
    if not isinstance(source, str) or len(source) != 1 or source in "/\\\0":
        raise ValueError("源字必须是一个汉字")
    path = mmh / f"{source}.json"
    if not path.is_file():
        raise ValueError(f"源字「{source}」没有 MMH 笔画数据")
    raw = path.read_bytes()
    if source_hash is not None and source_hash != digest_bytes(raw):
        raise ValueError(f"源字「{source}」的 MMH 数据已变化，请重新生成审阅页")
    data = json.loads(raw)
    paths = data.get("strokes", [])
    if (not isinstance(strokes, list) or not strokes or
            any(type(i) is not int or not 0 <= i < len(paths) for i in strokes) or
            strokes != sorted(set(strokes))):
        raise ValueError(f"「{source}」的取笔索引必须有效、升序、非空且不重复：{strokes!r}")
    if any(not isinstance(paths[i], str) or not paths[i].strip() for i in strokes):
        raise ValueError(f"「{source}」含空笔画")
    return data


def load_review_map(path: Path = REVIEW_MAP, mmh: Path = MMH) -> dict:
    if not path.exists():
        return {"version": 1, "roots": {}}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or type(value.get("version")) is not int or value["version"] != 1 or not isinstance(value.get("roots"), dict):
        raise ValueError(f"正楷确认表格式错误：{path}")
    for rid, entry in value["roots"].items():
        validate_root_id(rid)
        if not isinstance(entry, dict) or entry.get("confirmed") is not True:
            raise ValueError(f"{rid.upper()}：正式确认表只接受人工 confirmed=true 的记录")
        if entry.get("decision") not in ("keep", "replace"):
            raise ValueError(f"{rid.upper()}：无效的确认操作")
        if not isinstance(entry.get("note", ""), str):
            raise ValueError(f"{rid.upper()}：备注必须是文字")
        if entry["decision"] == "replace":
            source_hash = entry.get("sourceHash")
            if not isinstance(source_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", source_hash):
                raise ValueError(f"{rid.upper()}：缺少有效的 MMH 来源指纹")
            validate_selection(entry.get("source"), entry.get("strokes"), source_hash, mmh)
            if entry.get("fit") is not None:
                validate_root_id(entry["fit"])
    return value


def merge_derived(legacy: dict, path: Path = REVIEW_MAP, mmh: Path = MMH) -> dict:
    """Unconfirmed suggestions never reach the font; unrelated legacy specs survive."""
    out = dict(legacy)
    for rid, entry in load_review_map(path, mmh)["roots"].items():
        if entry["decision"] != "replace":
            continue
        spec = (entry["source"], list(entry["strokes"]))
        if entry.get("fit"):
            spec += ({"fit": entry["fit"]},)
        out[int(rid, 16)] = spec
    return out


def resolve_current(rid: str, info: dict, mapping: dict, names: dict, cmap: dict) -> dict:
    """Use the same PUA-first, actual-mapping-then-label order as the root chart.

    A rejected WenKai guess is not an existing ZhengKai glyph. A named root may
    still legitimately fall back to its label (e.g. 隹); the reviewer then checks
    whether that complete character is really the intended component.
    """
    cp = int(rid, 16)
    if cp in cmap:
        return {"present": True, "codepoint": cp, "glyph": cmap[cp], "label": "已抽笔画正楷"}
    entry = mapping.get(rid)
    char = ""
    if isinstance(entry, str):
        char = entry
    elif isinstance(entry, dict) and not entry.get("rejected") and not entry.get("removed"):
        if entry.get("compose"):
            compose = entry["compose"]
            char = "".join(compose) if isinstance(compose, (list, tuple)) else str(compose)
        else:
            char = entry.get("ch") or ""
    label = (info.get("n") or names.get(rid) or char or "?").strip()
    if isinstance(entry, dict) and entry.get("label"):
        label = entry["label"]
    probe = char if len(char) == 1 else label if len(label) == 1 else ""
    if probe and ord(probe) in cmap:
        return {"present": True, "codepoint": ord(probe), "glyph": cmap[ord(probe)], "label": probe}
    return {"present": False, "codepoint": None, "glyph": None, "label": "正楷缺字"}
