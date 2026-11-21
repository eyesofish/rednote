"""Create the two local example accounts and notes without rewriting user changes."""

from io import BytesIO

from PIL import Image, ImageDraw
from sqlalchemy import select

from app.auth import hash_password
from app.db import SessionLocal
from app.models import Note, User
from app.notes import create_note_record


DEMO_PASSWORD = "notebook-demo"


def sample_image(motif: str) -> bytes:
    """Draw small original illustrations of a desk and a hill for offline use."""
    canvas = Image.new("RGB", (420, 300), "#e9dcc9" if motif == "desk" else "#d5e7ec")
    pen = ImageDraw.Draw(canvas)
    if motif == "desk":
        pen.rectangle((0, 198, 420, 300), fill="#985c42")
        pen.rounded_rectangle((99, 48, 326, 202), radius=8, fill="#3a4347")
        pen.rectangle((108, 59, 317, 183), fill="#ebe6cb")
        for row, width in enumerate((96, 141, 83, 119)):
            pen.rectangle((133, 84 + 21*row, 133 + width, 87 + 21*row), fill="#658078")
        pen.polygon(((99, 202), (326, 202), (354, 224), (69, 224)), fill="#d3c5ac")
    else:
        pen.ellipse((270, 35, 321, 86), fill="#f4c877")
        pen.polygon(((0, 172), (123, 100), (256, 184), (420, 75), (420, 300), (0, 300)), fill="#79978e")
        pen.polygon(((0, 223), (185, 146), (339, 212), (420, 164), (420, 300), (0, 300)), fill="#507569")
        pen.line(((150, 300), (240, 240), (202, 219), (250, 194)), fill="#dfc79d", width=8)
    buffer = BytesIO()
    canvas.save(buffer, format="PNG")
    return buffer.getvalue()


def seed() -> None:
    with SessionLocal.begin() as db:
        for username, display_name in (("lune", "阿月"), ("kai", "小凯")):
            user = db.scalar(select(User).where(User.username == username))
            if user is None:
                db.add(User(username=username, display_name=display_name, password_hash=hash_password(DEMO_PASSWORD)))
        db.flush()
        author = db.scalars(select(User).where(User.username == "lune")).one()
        samples = (
            ("weekend", "周末面试笔记", "整理美团面试问题。", "hill"),
            ("interview", "美团一面复盘", "记录面试中的数据库问题。", "desk"),
        )
        for key, title, body, motif in samples:
            if db.scalar(select(Note.id).where(Note.seed_key == key)) is None:
                create_note_record(db, author, title, body, [("image/png", sample_image(motif))], key)


if __name__ == "__main__":
    seed()
