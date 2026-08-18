from pathlib import Path
import zipfile

root = Path("dist/GongCheng")
out = Path("dist/GongCheng.zip")
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    z.write("打开说明.txt", "GongCheng/ReadMe.txt")
    for path in root.rglob("*"):
        if path.is_file():
            z.write(path, Path("GongCheng") / path.relative_to(root))
print("wrote", out, "bytes", out.stat().st_size)
