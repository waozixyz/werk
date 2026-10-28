"""A changed compiler checkout must never reuse the old parser's objects."""
from pathlib import Path
import shutil
from runtime_cache import prepare

root = Path(__file__).resolve().parents[1]
fixture = root / "build/runtime-cache-test"
shutil.rmtree(fixture, ignore_errors=True)
fixture.mkdir(parents=True)
outside = fixture / "keep-output"
outside.write_text("owner output")
cache = fixture / "ziran"
try:
    prepare(root, cache)
    marker = cache / ".toolchain"
    original_time = marker.stat().st_mtime_ns
    object_file = cache / "parser.o"
    object_file.write_text("compiled parser")
    prepare(root, cache)
    assert object_file.exists() and marker.stat().st_mtime_ns == original_time
    marker.write_text("another toolchain checkout\n")
    prepare(root, cache)
    assert not object_file.exists(), "An incompatible parser object survived"
    assert outside.read_text() == "owner output"
    try:
        prepare(root, root / "build")
    except ValueError:
        pass
    else:
        raise AssertionError("The whole build directory must never be cleared")
    print("Runtime cache: reuse, toolchain invalidation and output preservation passed")
finally:
    shutil.rmtree(fixture)
