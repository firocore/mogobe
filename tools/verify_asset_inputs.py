"""Validate repository-owned compat inputs and the pinned self-hosted runtime."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def verify_inputs(root: Path = ROOT):
    root = root.resolve()
    checked = set()

    def check(relative, expected=None):
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            raise ValueError(f"Asset input points outside repository: {relative}")
        if not path.is_file():
            raise ValueError(f"Missing repository asset input: {relative}")
        if expected and hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Asset checksum mismatch or stale compiled resource: {relative}")
        checked.add(path.relative_to(root).as_posix())

    for metadata in (root / 'assets/compat').glob('*.source.json'):
        data = json.loads(metadata.read_text(encoding='utf-8'))
        source = data.get('source')
        if isinstance(source,str) and source.startswith(('assets/','tools/','client/','server/')):
            check(source,data.get('source_sha256'))
        for key in ('build_inputs','runtime_inputs'):
            for relative in data.get(key,[]):
                check(relative)
        if data.get('sha256'):
            stem = metadata.name.removesuffix('.source.json')
            candidates = [p for p in metadata.parent.glob(stem+'.*') if p != metadata]
            if len(candidates) != 1:
                raise ValueError(f"Cannot resolve compiled resource for {metadata.name}")
            check(candidates[0].relative_to(root),data['sha256'])
    runtime = json.loads((root/'assets/ruffle/source.json').read_text(encoding='utf-8'))
    check('assets/ruffle/ruffle.js')
    for relative, digest in runtime.get('vendored_files',{}).items():
        check('assets/ruffle/'+relative,digest)
    for license_file in ('LICENSE_MIT','LICENSE_APACHE'):
        check('assets/ruffle/'+license_file)
    return {'checked_inputs':sorted(checked),'input_count':len(checked),'external_archive_required':False}


if __name__ == '__main__':
    print(json.dumps(verify_inputs(),ensure_ascii=False,indent=2))
