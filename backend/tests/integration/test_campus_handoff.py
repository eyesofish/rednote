"""Exercise the classmate's actual pilot and editable ZIP through the operator's CLI."""
import csv
from io import BytesIO, StringIO
import json
import os
from pathlib import Path
import subprocess
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

import httpx
from PIL import Image
import pytest

from app.campus_pack import load_pack


ROOT = Path(__file__).resolve().parents[3]
PILOT = ROOT / "content/campus/downloads/campus-notes-pilot.zip"
AUTHOR_KIT = PILOT.with_name("campus-classmate-kit.zip")


def build_synthetic_final(path):
    """Fill the 90 empty slots of the downloadable kit with deterministic test fixtures."""
    prefix = "campus-notes-v1/"
    with ZipFile(AUTHOR_KIT) as source, ZipFile(path, "w", ZIP_DEFLATED) as output:
        def rows(name):
            return list(csv.DictReader(StringIO(source.read(prefix + name).decode("utf-8-sig"))))

        notes = rows("notes.csv")
        cases = rows("search-cases.csv")
        output.writestr("search-cases.csv", source.read(prefix + "search-cases.csv"))
        for row in notes:
            if row["title"]:
                output.writestr(row["image_path"], source.read(prefix + row["image_path"]))
                continue
            ident = row["id"]
            row["title"] = f"自动验收合成样本 {ident}"
            row["body"] = f"编号 {ident}。" + "这是用于核对图文包导入、封面与检索结果的测试数据。" * 4
            row["image_source"] = "本人绘制"
            for case in cases:
                if ident == case["title_id"]:
                    row["title"] += "：" + case["query"]
                elif ident == case["body_only_id"]:
                    row["body"] += case["query"]
            pixels = BytesIO()
            Image.new("RGB", (32, 24), (int(ident[1:]), 125, 221)).save(pixels, "WEBP", lossless=True)
            output.writestr(row["image_path"], pixels.getvalue())
        text = StringIO(newline="")
        writer = csv.DictWriter(text, fieldnames=notes[0].keys())
        writer.writeheader()
        writer.writerows(notes)
        output.writestr("notes.csv", text.getvalue().encode("utf-8"))
    return cases


@pytest.mark.skipif(os.getenv("REDNOTE_LIVE") != "1", reason="requires an isolated running Compose project")
def test_offline_pilot_to_full_import_and_real_search(tmp_path):
    project = os.environ["COMPOSE_PROJECT_NAME"]
    assert project.endswith("-test"), "use a separate acceptance project"

    def compose(*args):
        return subprocess.run(["docker", "compose", "-p", project, *args], cwd=ROOT,
                              capture_output=True, text=True, encoding="utf-8", check=True, timeout=70)

    run_id = uuid4().hex
    paths = {stage: f"/tmp/campus-{run_id}-{stage}.zip" for stage in ("pilot", "final")}

    def run(action, *args, stage="pilot"):
        try:
            output = compose("exec", "-T", "api", "python", "-m", "app.campus_import",
                             action, paths[stage], "--stage", stage, *args)
        except subprocess.CalledProcessError as exc:
            pytest.fail(exc.stderr or exc.stdout)
        return json.loads(output.stdout)

    try:
        compose("cp", str(PILOT), "api:" + paths["pilot"])
        assert run("validate") == {"notes": 10, "cases": 2, "warnings": []}
        first = run("import", "--author", "lune")
        second = run("import", "--author", "lune")
        assert first["created"] + first["reused"] == 10
        assert second["created"] == 0 and second["reused"] == 10
        assert second["ids"] == first["ids"]
        ids = first["ids"]
        checked = run("verify")
        assert checked["verified"] == 10
        assert checked["search_cases"] == {"雨天通勤": [ids["N005"], ids["N006"]], "雪地观鲸": []}
        base = os.getenv("TEST_BASE_URL", "http://127.0.0.1:18085")
        with httpx.Client(base_url=base, timeout=4, trust_env=False) as http, ZipFile(PILOT) as archive:
            for note in load_pack(PILOT, "pilot").notes:
                detail = http.get(f"/api/notes/{ids[note.id]}")
                detail.raise_for_status()
                assert (detail.json()["title"], detail.json()["body"]) == (note.title, note.body)
                cover = http.get(detail.json()["cover_url"])
                assert cover.status_code == 200 and cover.content == archive.read(note.image_path)
        final = tmp_path / "campus-synthetic-final.zip"
        cases = build_synthetic_final(final)
        compose("cp", str(final), "api:" + paths["final"])
        assert run("validate", stage="final") == {"notes": 100, "cases": 6, "warnings": []}
        full = run("import", "--author", "lune", stage="final")
        full_ids = full["ids"]
        assert full["created"] + full["reused"] == len(set(full_ids.values())) == 100
        assert full["reused"] >= 10
        assert {key: full_ids[key] for key in ids} == ids
        retry = run("import", "--author", "lune", stage="final")
        assert (retry["created"], retry["reused"], retry["ids"]) == (0, 100, full_ids)
        expected = {case["query"]: [full_ids[key] for key in (case["title_id"], case["body_only_id"]) if key]
                    for case in cases}
        assert sorted(map(len, expected.values())) == [0, 2, 2, 2, 2, 2]
        verified = run("verify", stage="final")
        assert verified["verified"] == 100 and verified["search_cases"] == expected
        with httpx.Client(base_url=base, timeout=4, trust_env=False) as http:
            for query, wanted in expected.items():
                result = http.get("/api/search", params={"q": query})
                result.raise_for_status()
                assert [item["id"] for item in result.json()["items"]] == wanted
    finally:
        compose("exec", "-T", "api", "rm", "-f", *paths.values())
