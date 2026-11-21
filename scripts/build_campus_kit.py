"""Build the offline campus-note pilot and the classmate's editable handoff."""
import argparse
import base64
import csv
from html import escape
from io import StringIO
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
CAMPUS = ROOT / "content" / "campus"
PILOT = CAMPUS / "pilot"
NOTES = ("id", "topic", "title", "body", "image_path", "image_source")
CASES = ("query", "title_id", "body_only_id")
TOPICS = ("校园自习", "求职面试", "租房通勤", "宿舍做饭", "周末活动")
SUGGESTED_CASES = (
    ("错题索引", "N011", "N012"),
    ("模拟群面", "N029", "N030"),
    ("隔夜燕麦", "N065", "N066"),
    ("周末集市", "N083", "N084"),
)


def read_csv(name):
    with (PILOT / name).open(encoding="utf-8-sig", newline="") as csv_file:
        return list(csv.DictReader(csv_file))


def encode_csv(columns, rows):
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    # Spreadsheet apps on Windows use the BOM to recognize Chinese UTF-8 text.
    return stream.getvalue().encode("utf-8-sig")


def write_zip(path, entries):
    # Fixed metadata keeps outputs identical across different checkout dates and OSes.
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in sorted(entries.items()):
            entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, data, compress_type=zipfile.ZIP_DEFLATED)


def preview(notes, images, *, standalone):
    cards = []
    for note in notes:
        path = note["image_path"]
        if standalone:
            source = "data:image/webp;base64," + base64.b64encode(images[path]).decode("ascii")
        else:
            source = "campus-notes-v1/" + path
        title = escape(note["title"])
        cards.append(
            f'<article><img src="{escape(source, quote=True)}" alt="{title}的配图">'
            f'<div><small>{escape(note["id"])} · {escape(note["topic"])} · 配图来源：'
            f'{escape(note["image_source"])}</small><h2>{title}</h2>'
            f'<p>{escape(note["body"])}</p></div></article>'
        )
    page = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>校园与求职生活 · 首批样稿</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f7f5f0;color:#292421;font-family:"Microsoft YaHei",sans-serif}
main{max-width:1100px;margin:auto;padding:24px}h1{font-size:clamp(1.6rem,4vw,2.5rem)}
section{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:24px}
article{background:#fff;border:1px solid #ded8ce;border-radius:12px;overflow:hidden}
img{display:block;width:100%;height:auto;aspect-ratio:4/3;object-fit:contain;background:#ebe8e2}
article div{padding:18px}small{color:#595249}h2{line-height:1.5;font-size:1.2rem;margin:10px 0}
p{line-height:1.8;margin:0;white-space:pre-line}
</style></head><body><main><h1>校园与求职生活 · 首批样稿</h1><section>"""
    return (page + "\n".join(cards) + "</section></main></body></html>\n").encode("utf-8")


def build(output):
    notes = read_csv("notes.csv")
    cases = read_csv("search-cases.csv")
    images = {row["image_path"]: (PILOT / row["image_path"]).read_bytes() for row in notes}
    brief = (CAMPUS / "BRIEF.md").read_text(encoding="utf-8-sig").encode("utf-8")

    template_notes = list(notes)
    for index in range(11, 101):
        note_id = f"N{index:03}"
        template_notes.append({
            "id": note_id,
            "topic": TOPICS[(index - 11) // 18],
            "image_path": f"images/{note_id}.webp",
        })
    template_cases = cases + [dict(zip(CASES, row)) for row in SUGGESTED_CASES]

    pilot_entries = {"notes.csv": encode_csv(NOTES, notes), "search-cases.csv": encode_csv(CASES, cases), **images}
    template_entries = {**images, "notes.csv": encode_csv(NOTES, template_notes),
                        "search-cases.csv": encode_csv(CASES, template_cases)}
    handoff_entries = {"任务单.md": brief, "样稿预览.html": preview(notes, images, standalone=False)}
    handoff_entries.update({f"campus-notes-v1/{name}": data for name, data in template_entries.items()})

    output.mkdir(parents=True, exist_ok=True)
    write_zip(output / "campus-notes-pilot.zip", pilot_entries)
    write_zip(output / "campus-classmate-kit.zip", handoff_entries)
    (output / "pilot-preview.html").write_bytes(preview(notes, images, standalone=True))
    for name in ("campus-notes-pilot.zip", "campus-classmate-kit.zip", "pilot-preview.html"):
        print(output / name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / ".local" / "campus-deliveries")
    build(parser.parse_args().output)
