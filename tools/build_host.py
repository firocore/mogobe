"""Recompile only our SWF adapter. Original game SWFs are never patched.

python tools/build_host.py --java path/to/java.exe --ffdec path/to/ffdec.jar
Normal client builds reuse the checked-in compiled adapter and do not need Java.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--java", default=shutil.which("java") or "java")
    parser.add_argument("--ffdec", required=True)
    args = parser.parse_args()
    movie = ROOT / "assets/compat/MogobeHost.swf"
    output = movie.with_name("MogobeHost.compiled.swf")
    completed = subprocess.run(
        [args.java, "-Djava.awt.headless=true", "-jar", args.ffdec, "-importScript",
         str(movie), str(output), str(ROOT / "tools/host")],
        capture_output=True, text=True, timeout=120,
    )
    print(completed.stdout[-10000:])
    print(completed.stderr[-10000:])
    completed.check_returncode()
    if not output.exists():
        raise SystemExit("SWF compiler did not create the adapter")
    output.replace(movie)
    movie.with_suffix(".source.json").write_text(json.dumps({
        "original_game_asset": False,
        "source": "tools/host/MogobeHost.as",
        "source_sha256": hashlib.sha256((ROOT / "tools/host/MogobeHost.as").read_bytes()).hexdigest(),
        "compiler": "JPEXS 26.3.0",
        "role": "Load original login, saved-avatar picker, registration alerts, Main, world map, rooms and avatar; retain original preloader until room, panel and avatar are ready",
        "sha256": hashlib.sha256(movie.read_bytes()).hexdigest(),
    }, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
