"""Import the existing verified originals; generate adapted HTML in a separate tree.

Usage: python tools/prepare_assets.py
All sources for normal builds are stored in this repository's assets directory.
Originals are copied byte-for-byte to assets/original and never patched there.
"""
import filecmp
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

from prepare_item_assets import prepare_items
from verify_asset_inputs import verify_inputs

ROOT = Path(__file__).resolve().parents[1]


def copy_resource(source, destination):
    # Unchanged runtime files can be memory-mapped by Windows. They do not
    # need to be overwritten to prepare an identical embedded resource.
    if Path(destination).is_file() and filecmp.cmp(source, destination, shallow=False):
        return destination
    return shutil.copy2(source, destination)


def main():
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "assets"
    original = ROOT / "assets/original"
    if source.resolve() != (ROOT / "assets").resolve():
        shutil.copytree(source / "original", original, dirs_exist_ok=True, copy_function=copy_resource)
        compat = ROOT / "assets/compat"
        compat.mkdir(parents=True, exist_ok=True)
        for name in ["MogobeHost.swf", "OriginalPreloader.swf"]:
            copy_resource(source / "compat" / name, compat / name)
            metadata = source / "compat" / name.replace(".swf", ".source.json")
            if metadata.exists():
                copy_resource(metadata, compat / metadata.name)
        shutil.copytree(source / "ruffle", ROOT / "assets/ruffle", dirs_exist_ok=True, copy_function=copy_resource)
        copy_resource(source / "ui/app.ico", ROOT / "client/build/windows/icon.ico")

    audit = verify_inputs(ROOT)
    print(f"Verified {audit['input_count']} repository asset inputs; no external archive required")

    web = ROOT / "client/frontend"
    manifest = []
    for path in original.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(original)
        manifest.append({"path": relative.as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        if relative.parts[0] in {"registration-assets", "registration-pages", "site"}:
            continue
        if relative.parts[:2] == ("Swf", "Items"):
            continue  # Only prepared thumbnails and combined animations are embedded below.
        dest = web / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        copy_resource(path, dest)
    for path in (original / "registration-assets").iterdir():
        name = path.name.split("_", 1)[-1]
        if name == "MogoStyle.css":
            relative = Path("css/MogoStyle.css")
        elif name.endswith(".js"):
            continue  # Expired ASP.NET and tracking scripts are not executed.
        else:
            relative = Path("Media/images/Registration") / name
        dest = web / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        copy_resource(path, dest)
        if name in {"CleanBG.png", "tab.gif"}:
            copy_resource(path, web / "Media/images" / name)
    for path in (ROOT / "assets/ruffle").iterdir():
        if path.is_file() and not path.name.endswith(".map"):
            dest = web / "runtime" / path.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            copy_resource(path, dest)
    shutil.copytree(ROOT / "assets/compat", web / "compat", dirs_exist_ok=True, copy_function=copy_resource, ignore=shutil.ignore_patterns("item-animations"))
    prepare_items(ROOT, web / "items")
    loading = web / "Swf/Assets/LoadingScreens/LoadingScreen_0.swf"
    loading.parent.mkdir(parents=True, exist_ok=True)
    copy_resource(ROOT / "assets/compat/LoadingScreen_0.swf", loading)
    (web / "servises/lang.aspx").write_bytes((ROOT / "assets/compat/lang-numeric-levels.xml").read_bytes())
    for page in (original / "registration-pages").glob("*.html"):
        step = page.name.removesuffix(".aspx.html").removeprefix("Registration")
        step = int(step) if step.isdigit() else "confirm"
        html = page.read_text(encoding="utf-8")
        html = re.sub(r"<script\b[^>]*>.*?</script>", "", html, flags=re.I | re.S)
        html = re.sub(r'<input[^>]+(?:__VIEWSTATE|__EVENTVALIDATION)[^>]*>', '', html, flags=re.I)
        html = re.sub(r'\s+on\w+\s*=\s*(?:"[^"]*"|\x27[^\x27]*\x27)', '', html, flags=re.I)
        html = html.replace('href="javascript:window.close()"', 'href="/"')
        # The old pages always navigate within this local client.
        html = re.sub(r'(?:(?:https?://[^/\s"\x27]+)?/)?Media/images/', '/Media/images/', html, flags=re.I)
        head = ('<meta charset="utf-8"><script src="/runtime-config.js"></script>'
                f'<script>window.MOGO_REG_STEP={json.dumps(step)};</script>'
                '<link rel="stylesheet" href="/registration-popups.css">'
                '<script defer src="/runtime/ruffle.js"></script>'
                '<script defer src="/registration-popups.js"></script><script defer src="/registration.js"></script>')
        html = html.replace('</head>', head + '</head>')
        (web / page.name.removesuffix(".html")).write_text(html, encoding="utf-8")
    (ROOT / "assets/manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Indexed {len(manifest)} original resources; prepared SWFs and registration pages")


if __name__ == "__main__":
    main()
