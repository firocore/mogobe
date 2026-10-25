"""Extract the original Israeli chat-history panel without changing its SWF."""
import hashlib
import json
import struct
import zlib
from pathlib import Path

from build_loading_stub import build
from swf_room_data import SWF, records, rect

ROOT = Path(__file__).resolve().parents[1]


def tag(kind, data=b""):
    return struct.pack("<HI", (kind << 6) | 63, len(data)) + data


def main():
    source = ROOT / "assets/original/Swf/Preserved/ControlPanelIsraelChat.swf"
    swf = SWF(source)
    assert any(p["name"] == "mcPublicMessages" and p["id"] == 302 for p in swf.children(303))
    assert {p["name"] for p in swf.children(302)} == {"mcMessageHolder", "btnPublicMessages"}
    body = swf.header[:-2] + struct.pack("<H", 1) + tag(69, struct.pack("<I", 8))
    for kind, _, encoded in swf.tags:
        if kind in (2,6,7,10,11,14,20,21,22,32,33,34,35,36,37,39,46,48,60,61,62,73,75,83,84,87,88,90,91):
            body += encoded
    name = "MogobeOriginalChatHistory"
    stub = build(name)
    _, offset = rect(stub[8:])
    body += b"".join(raw for kind, _, raw in records(stub[8+offset+4:]) if kind == 82)
    body += tag(76, struct.pack("<HH", 1, 302) + name.encode() + b"\0") + tag(1) + tag(0)
    output = ROOT / "assets/compat/ChatHistory.swf"
    output.write_bytes(b"CWS" + bytes([swf.version]) + struct.pack("<I", len(body)+8) + zlib.compress(body))
    output.with_suffix(".source.json").write_text(json.dumps({
        "original_game_asset": False, "original_graphics": True,
        "source": source.relative_to(ROOT).as_posix(),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "source_archive": "He/MainFiles/ControlPanel[9].swf", "panel_symbol": 302,
        "panel_geometry": {
            "top_left": [-64.1, -152.45], "top_right": [214.85, -152.45],
            "bottom_left": [-49.15, 0.3], "bottom_right": [201.75, 0.3],
            "fill": "#000000", "fill_alpha": 0.4,
        },
        "class": name, "generator": "tools/build_chat_history.py",
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
    }, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print("Extracted original Israeli chat-history panel and toggle button.")


if __name__ == "__main__":
    main()
