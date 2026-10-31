"""Create a simple original desktop icon, no upstream branding."""
from pathlib import Path
from PIL import Image, ImageDraw

root = Path(__file__).resolve().parents[1] / "assets"
root.mkdir(exist_ok=True)
image = Image.new("RGBA", (1024, 1024))
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((20, 20, 1004, 1004), radius=225, fill="#216b56")
draw.rounded_rectangle((252, 660, 772, 800), radius=60, fill="#4f9d79")
draw.line([(398, 220), (626, 220)], fill="#ecf4df", width=48)
draw.line([(430, 230), (430, 435), (265, 725), (265, 760), (298, 790), (726, 790), (759, 760), (759, 725), (594, 435), (594, 230)], fill="#ecf4df", width=42, joint="curve")
draw.line([(355, 618), (675, 618)], fill="#b4d990", width=32)
for x, y, r in [(477, 560, 23), (559, 502, 17), (521, 675, 28), (710, 310, 22), (788, 420, 31)]:
    draw.ellipse((x-r, y-r, x+r, y+r), fill="#d8edb7")
image.save(root / "NaNoBO.png")
image.save(root / "NaNoBO.icns")
image.save(root / "NaNoBO.ico", sizes=[(16, 16), (32, 32), (48, 48), (128, 128), (256, 256)])
