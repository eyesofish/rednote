"""Read the offline campus-note delivery format without extracting files or opening a DB."""
import csv
import hashlib
import lzma
import stat
import zlib
from collections import Counter
from dataclasses import dataclass, field
from io import BytesIO, StringIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from PIL import Image


TOPICS = ("校园自习", "求职面试", "租房通勤", "宿舍做饭", "周末活动")
SOURCES = {"本人拍摄", "本人绘制", "AI 生成"}
NOTE_COLUMNS = ("id", "topic", "title", "body", "image_path", "image_source")
CASE_COLUMNS = ("query", "title_id", "body_only_id")
IMAGE_TYPES = {"PNG": (".png",), "JPEG": (".jpeg", ".jpg"), "WEBP": (".webp",)}
MAX_IMAGE_BYTES = 4 * 1024**2


@dataclass(frozen=True)
class PackNote:
    id: str
    topic: str
    title: str
    body: str
    image_path: str
    image_source: str
    image_bytes: bytes = field(repr=False)
    media_type: str


@dataclass(frozen=True)
class SearchCase:
    query: str
    title_id: str
    body_only_id: str


@dataclass
class Pack:
    notes: list[PackNote]
    cases: list[SearchCase]
    warnings: list[str]


def _image_path(name: str) -> bool:
    prefix, separator, basename = name.partition("/")
    return (prefix == "images" and bool(separator and basename)
            and "/" not in basename and "\\" not in basename and ":" not in basename
            and basename not in {".", ".."} and Path(basename).suffix.lower() in {".jpg", ".jpeg", ".webp", ".png"})


def _check_members(archive: ZipFile, count: int) -> set[str]:
    names = set()
    csv_limits = {"notes.csv": count * 64 * 1024, "search-cases.csv": 32 * 1024}
    for info in archive.infolist():
        name = info.filename
        if name in names or info.orig_filename != name:
            raise ValueError(f"重复或无效的 ZIP 文件名：{name!r}")
        names.add(name)
        if stat.S_ISLNK(info.external_attr >> 16) or info.flag_bits & 1:
            raise ValueError(f"不支持链接或加密文件：{name}")
        if name in csv_limits:
            limit = csv_limits[name]
        elif name == "images/" and info.is_dir():
            limit = 0
        elif _image_path(name):
            limit = MAX_IMAGE_BYTES
        else:
            raise ValueError(f"ZIP 路径不符合交付结构：{name!r}")
        if info.file_size > limit:
            raise ValueError(f"{name} 超过文件大小限制（{limit} 字节）")
    if not csv_limits.keys() <= names:
        raise ValueError("ZIP 根目录需要 notes.csv 和 search-cases.csv")
    images = names - csv_limits.keys() - {"images/"}
    if len(images) != count:
        raise ValueError(f"需要 {count} 个独立图片文件，实际 {len(images)} 个")
    return images


def _rows(archive: ZipFile, name: str, columns: tuple[str, ...], max_rows: int) -> list[dict[str, str]]:
    try:
        text = archive.read(name).decode("utf-8-sig")
        reader = csv.reader(StringIO(text, newline=""), strict=True)
        header = next(reader, [])
        if len(header) != len(columns) or set(header) != set(columns):
            raise ValueError(f"{name} 需要列 {','.join(columns)}")
        rows = []
        for values in reader:
            if not values:
                continue
            if len(values) != len(header):
                raise ValueError(f"{name} 第 {reader.line_num} 行的列数与表头不一致")
            rows.append(dict(zip(header, (value.strip() for value in values), strict=True)))
            if len(rows) > max_rows:
                raise ValueError(f"{name} 最多允许 {max_rows} 条记录")
        return rows
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ValueError(f"{name} 无法按 UTF-8 CSV 读取：{exc}") from exc


def _open_image(raw: bytes, name: str) -> tuple[str, int, int]:
    try:
        with Image.open(BytesIO(raw)) as image:
            fmt = image.format
            if fmt not in IMAGE_TYPES or Path(name).suffix.lower() not in IMAGE_TYPES[fmt]:
                raise ValueError("需要扩展名与内容一致的 PNG、JPEG 或 WebP")
            width, height = image.size
            if width * height > 16_000_000:
                raise ValueError("超过 1600 万像素")
            image.verify()
        with Image.open(BytesIO(raw)) as image:
            image.load()
        return "image/" + fmt.lower(), width, height
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as exc:
        raise ValueError(f"{name} 图片无效：{exc}") from exc


def _read_notes(archive: ZipFile, images: set[str], count: int, warnings: list[str]) -> list[PackNote]:
    rows = _rows(archive, "notes.csv", NOTE_COLUMNS, count)
    ids = {f"N{i:03}" for i in range(1, count + 1)}
    if len(rows) != count or {row["id"] for row in rows} != ids:
        raise ValueError(f"notes.csv 需要 N001–N{count:03} 共 {count} 个唯一编号")
    if Counter(row["topic"] for row in rows) != {topic: count // 5 for topic in TOPICS}:
        raise ValueError(f"每个主题应有 {count // 5} 篇：{'、'.join(TOPICS)}")
    if {row["image_path"] for row in rows} != images:
        raise ValueError("image_path 必须与 images/ 中的文件一一对应")

    notes = []
    digests = {}
    for row in sorted(rows, key=lambda item: item["id"]):
        ident, title, body = row["id"], row["title"], row["body"]
        if not (1 <= len(title) <= 160 and 1 <= len(body) <= 12_000):
            raise ValueError(f"{ident} 的标题须为 1–160 字，正文须为 1–12000 字")
        if row["image_source"] not in SOURCES:
            raise ValueError(f"{ident} 的 image_source 应为本人拍摄、本人绘制或 AI 生成")
        raw = archive.read(row["image_path"])
        digest = hashlib.sha256(raw).digest()
        if digest in digests:
            raise ValueError(f"{ident} 与 {digests[digest]} 使用了同一份图片内容")
        digests[digest] = ident
        media_type, width, height = _open_image(raw, row["image_path"])
        if not 80 <= len(body) <= 200:
            warnings.append(f"{ident} 正文 {len(body)} 字，建议 80–200 字")
        if width * 3 != height * 4:
            warnings.append(f"{ident} 图片 {width}×{height}，建议 4:3")
        if len(raw) > 500_000:
            warnings.append(f"{ident} 图片 {len(raw)} 字节，建议不超过 500 KB")
        notes.append(PackNote(**row, image_bytes=raw, media_type=media_type))
    return notes


def _read_cases(archive: ZipFile, notes: list[PackNote], stage: str) -> list[SearchCase]:
    cases = [SearchCase(**row) for row in _rows(archive, "search-cases.csv", CASE_COLUMNS, 6)]
    seen = set()
    pairs = 0
    for case in cases:
        query = case.query
        if not 1 <= len(query) <= 128 or query in seen:
            raise ValueError("搜索词应为 1–128 字，且在 search-cases.csv 中唯一")
        seen.add(query)
        titles = {note.id for note in notes if query in note.title}
        bodies = {note.id for note in notes if query in note.body and note.id not in titles}
        if bool(case.title_id) != bool(case.body_only_id) or (case.title_id and case.title_id == case.body_only_id):
            raise ValueError(f"“{query}”需要两个不同编号，零匹配词的两个编号均留空")
        expected_titles = {case.title_id} if case.title_id else set()
        expected_bodies = {case.body_only_id} if case.body_only_id else set()
        if (titles, bodies) != (expected_titles, expected_bodies):
            raise ValueError(f"“{query}”实际标题命中 {sorted(titles)}，仅正文命中 {sorted(bodies)}，与登记不符")
        pairs += bool(case.title_id)
    zero_count = len(cases) - pairs
    if stage == "pilot" and (pairs != 1 or zero_count not in (0, 1)):
        raise ValueError("样稿需要 1 组成对搜索词，可附 1 个零匹配词")
    if stage == "final" and (pairs != 5 or zero_count != 1):
        raise ValueError("正式包需要 5 组成对搜索词和 1 个零匹配词")
    return cases


def load_pack(path: Path | str, stage: str) -> Pack:
    """Validate a complete ZIP before returning importable notes and search expectations."""
    if stage not in {"pilot", "final"}:
        raise ValueError("stage 应为 pilot 或 final")
    count = 10 if stage == "pilot" else 100
    path = Path(path)
    try:
        if path.stat().st_size > count * (MAX_IMAGE_BYTES + 64 * 1024) + 256 * 1024:
            raise ValueError("ZIP 大小超过该阶段可接收的总量")
        with ZipFile(path) as archive:
            images = _check_members(archive, count)
            warnings = []
            notes = _read_notes(archive, images, count, warnings)
            cases = _read_cases(archive, notes, stage)
            return Pack(notes, cases, warnings)
    except (OSError, BadZipFile, NotImplementedError, EOFError, zlib.error, lzma.LZMAError) as exc:
        raise ValueError(f"无法读取 ZIP：{exc}") from exc
