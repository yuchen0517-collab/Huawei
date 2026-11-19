import re
import zipfile

path = r"Diplomat_webdemo2.0/智能体设计说明书_webdemo2.0.docx"
with zipfile.ZipFile(path) as archive:
    xml = archive.read("word/document.xml").decode("utf-8")

xml = re.sub(r"</w:p>", "\n", xml)
text = re.sub(r"<[^>]+>", "", xml)
for line in text.splitlines():
    line = line.strip()
    if re.search(r"R[1-7]", line):
        print(line[:600])