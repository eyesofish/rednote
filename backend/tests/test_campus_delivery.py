"""The downloadable files must match the editable sources and be usable offline."""
import csv
from codecs import BOM_UTF8
from collections import Counter
from io import StringIO
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[2]


def read_csv(archive, member):
    data = archive.read(member)
    assert data.startswith(BOM_UTF8)
    return list(csv.DictReader(StringIO(data.decode("utf-8-sig"))))


def test_published_handoff_matches_sources_and_preserves_pilot(tmp_path):
    subprocess.run([sys.executable, str(ROOT / "scripts/build_campus_kit.py"),
                    "--output", str(tmp_path)], check=True)
    downloads = ROOT / "content/campus/downloads"
    for name in ("campus-notes-pilot.zip", "campus-classmate-kit.zip"):
        with ZipFile(downloads / name) as published, ZipFile(tmp_path / name) as rebuilt:
            assert sorted(published.namelist()) == sorted(rebuilt.namelist())
            for member in rebuilt.namelist():
                assert published.read(member) == rebuilt.read(member), member
    with (ZipFile(downloads / "campus-notes-pilot.zip") as pilot,
          ZipFile(downloads / "campus-classmate-kit.zip") as handoff):
        original = read_csv(pilot, "notes.csv")
        template = read_csv(handoff, "campus-notes-v1/notes.csv")
        assert len(original) == 10 and original == template[:10]
        assert [row["id"] for row in template] == [f"N{i:03d}" for i in range(1, 101)]
        assert sorted(Counter(row["topic"] for row in template).values()) == [20] * 5
        assert all(not row["title"] and not row["body"] for row in template[10:])
        assert len(read_csv(handoff, "campus-notes-v1/search-cases.csv")) == 6
        preview = handoff.read("样稿预览.html").decode("utf-8")
        for row in original:
            path = row["image_path"]
            assert handoff.read("campus-notes-v1/" + path) == pilot.read(path)
            assert "campus-notes-v1/" + path in preview
    assert (tmp_path / "pilot-preview.html").read_text(encoding="utf-8").count("data:image/webp;base64,") == 10
