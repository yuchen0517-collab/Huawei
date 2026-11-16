import zipfile, os

z = zipfile.ZipFile(r"D:\RainbowKATE\大学研究生时\华为杯\Diplomat-components.zip")
out = "_inspect_components"
os.makedirs(out, exist_ok=True)
for n in z.namelist():
    fixed = n.replace("\\", "/")
    if fixed.endswith("/"):
        continue
    target = os.path.join(out, fixed.replace("/", "__"))
    with open(target, "wb") as f:
        f.write(z.read(n))
print("done")
