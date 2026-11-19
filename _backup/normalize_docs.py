import pathlib

paths = [
    ".gitignore",
    "C 11.12 三指数/docs/C_DELIVERY_CHECKLIST.md",
    "C 11.12 三指数/docs/MERGE_REPORT_1120.md",
    "C 11.12 三指数/docs/SPEC_UPDATE_C.md",
    "Diplomat_webdemo2.0/C 11.11 三指数/DEPRECATED.md",
    "Diplomat_webdemo2.0/C 11.12 引擎/DEPRECATED.md",
]

for raw in paths:
    path = pathlib.Path(raw)
    data = path.read_bytes().replace(bytes([13, 10]), bytes([10]))
    path.write_bytes(data)
    print("normalized", raw, len(data))