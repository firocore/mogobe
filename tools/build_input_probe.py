"""Build a standalone TextField reproduction from repo assets, without game controllers."""
import argparse
import shutil
import subprocess
from pathlib import Path

from build_loading_stub import build

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--java", default=shutil.which("java") or "java")
    parser.add_argument("--ffdec", required=True)
    args = parser.parse_args()
    folder = ROOT / "verification/input-fields"
    source = folder / "source"
    source.mkdir(parents=True, exist_ok=True)
    text = (ROOT / "tools/probes/MogobeInputProbe.as").read_text(encoding="utf-8")
    host = (ROOT / "tools/host/MogobeHost.as").read_text(encoding="utf-8")
    begin, end = "// BEGIN SHARED INPUT COMPATIBILITY", "// END SHARED INPUT COMPATIBILITY"
    shared = host.split(begin, 1)[1].split(end, 1)[0] if begin in host else "private function updateFocusedInput():void {}"
    (source / "MogobeInputProbe.as").write_text(text.replace("/* SHARED_INPUT_COMPATIBILITY */", shared), encoding="utf-8")
    stub = folder / "stub.swf"
    movie = bytearray(build("MogobeInputProbe", root=True))
    movie[3] = (ROOT / "assets/compat/MogobeHost.swf").read_bytes()[3]
    stub.write_bytes(movie)
    out = folder / "probe.swf"
    result = subprocess.run([args.java, "-Djava.awt.headless=true", "-jar", args.ffdec,
                             "-importScript", str(stub), str(out), str(source)],
                            capture_output=True, text=True, timeout=120)
    print(result.stdout[-3000:])
    print(result.stderr[-3000:])
    result.check_returncode()
    if not out.exists():
        raise SystemExit("Probe compiler did not produce a SWF")
    print(out)


if __name__ == "__main__":
    main()
