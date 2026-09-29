import sys, urllib.request, re
import xml.etree.ElementTree as ET
ids = sys.argv[1:]
url = "https://export.arxiv.org/api/query?id_list=" + ",".join(ids) + "&max_results=%d" % len(ids)
data = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 research"}), timeout=40).read()
ns = {"a": "http://www.w3.org/2005/Atom"}
for e in ET.fromstring(data).findall("a:entry", ns):
    print("ID:", e.find("a:id", ns).text.strip())
    print("TITLE:", re.sub(r"\s+", " ", e.find("a:title", ns).text.strip()))
    print("AUTHORS:", ", ".join(a.find("a:name", ns).text for a in e.findall("a:author", ns)))
    print("PUBLISHED:", e.find("a:published", ns).text[:10], "UPDATED:", e.find("a:updated", ns).text[:10])
    print("ABSTRACT:", re.sub(r"\s+", " ", e.find("a:summary", ns).text.strip()))
    print()
