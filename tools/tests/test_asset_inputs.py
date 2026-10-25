import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from verify_asset_inputs import verify_inputs


def package(root):
    files = {
        'assets/compat/Example.swf': b'compiled',
        'tools/example.as': b'input',
        'assets/ruffle/ruffle.js': b'runtime',
        'assets/ruffle/LICENSE_MIT': b'license',
        'assets/ruffle/LICENSE_APACHE': b'license',
        'assets/ruffle/source.json': b'{}',
    }
    for name, content in files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    metadata = {
        'source': 'tools/example.as',
        'source_sha256': hashlib.sha256(b'input').hexdigest(),
        'sha256': hashlib.sha256(b'compiled').hexdigest(),
        'runtime_inputs': ['assets/compat/Example.swf'],
        'provenance': {'original_archive_entry': 'Z:/missing/archive.swf'},
    }
    (root/'assets/compat/Example.source.json').write_text(json.dumps(metadata))


def test_local_package_ignores_archive_provenance_and_detects_missing_resource(tmp_path):
    package(tmp_path)
    assert verify_inputs(tmp_path)['external_archive_required'] is False
    (tmp_path/'assets/compat/Example.swf').unlink()
    with pytest.raises(ValueError, match='Missing repository asset input'):
        verify_inputs(tmp_path)


def test_changed_adapter_source_cannot_silently_ship_old_compilation(tmp_path):
    package(tmp_path)
    (tmp_path/'tools/example.as').write_bytes(b'new input')
    with pytest.raises(ValueError, match='stale compiled resource'):
        verify_inputs(tmp_path)
