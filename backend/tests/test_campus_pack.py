import csv
import warnings
from io import BytesIO, StringIO
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image
import pytest

from app.campus_pack import CASE_COLUMNS, NOTE_COLUMNS, TOPICS, load_pack


def csv_bytes(columns, rows):
    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")


def fixture_data(final=False):
    count = 100 if final else 10
    cases = []
    for pair, word in enumerate(("错题便签", "白板练习", "雨天通勤", "焖饭锅", "山间步道")[:5 if final else 1]):
        cases.append({"query": word, "title_id": f"N{pair*2+1:03}", "body_only_id": f"N{pair*2+2:03}"})
    cases.append({"query": "鲸鱼邮差", "title_id": "", "body_only_id": ""})
    rows = []
    files = {}
    for num in range(1, count + 1):
        ident = f"N{num:03}"
        title = "夜读 " + ident
        body = '吃过饭，洗好杯子。\n今天的计划写在纸上，旁边还有 "午后" 和一个英文逗号,留给晚饭以后再做。' * 2
        for case in cases:
            if case["title_id"] == ident:
                title += case["query"]
            elif case["body_only_id"] == ident:
                body += case["query"]
        filename = f"images/{ident}.png"
        image = BytesIO()
        Image.new("RGB", (16, 12), (num, 150, 100)).save(image, "PNG")
        files[filename] = image.getvalue()
        rows.append({"id": ident, "topic": TOPICS[(num-1) % 5], "title": title, "body": body,
                     "image_path": filename, "image_source": "AI 生成"})
    return rows, cases, files


def write_zip(path, rows, cases, files):
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("images/", b"")
        archive.writestr("notes.csv", csv_bytes(NOTE_COLUMNS, rows))
        archive.writestr("search-cases.csv", csv_bytes(CASE_COLUMNS, cases))
        for filename, content in files.items():
            archive.writestr(filename, content)


@pytest.mark.parametrize(("stage", "count", "case_count"), [("pilot", 10, 2), ("final", 100, 6)])
def test_accepts_real_images_and_utf8_csv_in_either_stage(tmp_path, stage, count, case_count):
    rows, cases, files = fixture_data(stage == "final")
    path = tmp_path / "pack.zip"
    write_zip(path, rows[::-1], cases, files)
    pack = load_pack(path, stage)
    assert [note.id for note in pack.notes] == [row["id"] for row in rows]
    assert len(pack.notes) == count
    assert pack.notes[0].body == rows[0]["body"]
    assert pack.notes[0].image_bytes == files["images/N001.png"]
    assert pack.notes[0].media_type == "image/png"
    assert len(pack.cases) == case_count
    assert pack.cases[-1].title_id == pack.cases[-1].body_only_id == ""
    assert pack.warnings == []


def test_pilot_is_valid_with_just_one_pair_and_soft_image_text_recommendations(tmp_path):
    rows, cases, files = fixture_data()
    image = BytesIO()
    Image.new("RGB", (14, 19), "red").save(image, "JPEG")
    rows[0].update(body="短文", image_path="images/example.jpg")
    del files["images/N001.png"]
    files["images/example.jpg"] = image.getvalue()
    path = tmp_path / "pilot.zip"
    write_zip(path, rows, cases[:1], files)
    pack = load_pack(path, "pilot")
    assert pack.notes[0].media_type == "image/jpeg"
    assert len(pack.warnings) == 2


@pytest.mark.parametrize(("change", "message"), [
    ("third_match", "实际标题命中"), ("wrong_id", "实际标题命中"), ("zero_collision", "实际标题命中"),
    ("incomplete_pair", "两个不同编号"), ("missing_zero", "正式包需要"), ("repeated_id", "唯一编号"),
    ("wrong_topic", "每个主题"), ("bad_source", "image_source"), ("corrupt", "图片无效"),
    ("mismatch_extension", "图片无效"), ("unused_image", "一一对应"),
    ("identical_images", "同一份图片"), ("unsafe_path", "ZIP 路径")
])
def test_rejects_mismatched_corpus_before_import(tmp_path, change, message):
    final = change == "missing_zero"
    rows, cases, files = fixture_data(final)
    if change == "third_match":
        rows[2]["body"] += cases[0]["query"]
    elif change == "wrong_id":
        cases[0]["title_id"] = "N003"
    elif change == "zero_collision":
        rows[2]["title"] += cases[-1]["query"]
    elif change == "incomplete_pair":
        cases[0]["body_only_id"] = ""
    elif change == "missing_zero":
        cases.pop()
    elif change == "repeated_id":
        rows[-1]["id"] = "N001"
    elif change == "wrong_topic":
        rows[0]["topic"] = TOPICS[1]
    elif change == "bad_source":
        rows[0]["image_source"] = "未知"
    elif change == "corrupt":
        files["images/N001.png"] = b"truncated"
    elif change == "mismatch_extension":
        rows[0]["image_path"] = "images/N001.webp"
        files["images/N001.webp"] = files.pop("images/N001.png")
    elif change == "unused_image":
        rows[0]["image_path"] = "images/N002.png"
    elif change == "identical_images":
        files["images/N001.png"] = files["images/N002.png"]
    elif change == "unsafe_path":
        files["images/../../unexpected.png"] = files.pop("images/N001.png")
    path = tmp_path / "pack.zip"
    write_zip(path, rows, cases, files)
    with pytest.raises(ValueError, match=message):
        load_pack(path, "final" if final else "pilot")


def test_duplicate_archive_names_and_bad_csv_are_rejected(tmp_path):
    rows, cases, files = fixture_data()
    path = tmp_path / "pack.zip"
    write_zip(path, rows, cases, files)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with ZipFile(path, "a") as archive:
            archive.writestr("notes.csv", "id")
    with pytest.raises(ValueError, match="ZIP 文件名"):
        load_pack(path, "pilot")
    with ZipFile(path, "w") as archive:
        archive.writestr("notes.csv", b"\xff\xfe")
        archive.writestr("search-cases.csv", csv_bytes(CASE_COLUMNS, cases))
        for filename, content in files.items():
            archive.writestr(filename, content)
    with pytest.raises(ValueError, match="UTF-8 CSV"):
        load_pack(path, "pilot")
