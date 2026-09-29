import sys, re, urllib.request, xml.etree.ElementTree as ET
ids = sys.argv[1:]
url = "http://export.arxiv.org/api/query?id_list=" + ",".join(ids) + "&max_results=%d" % len(ids)
req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
data = urllib.request.urlopen(req, timeout=60).read()
ns = {'a':'http://www.w3.org/2005/Atom', 'ar':'http://arxiv.org/schemas/atom'}
root = ET.fromstring(data)
for e in root.findall('a:entry', ns):
    print("ID:", e.find('a:id', ns).text)
    print("TITLE:", re.sub(r'\s+',' ', e.find('a:title', ns).text))
    print("AUTHORS:", "; ".join(a.find('a:name', ns).text for a in e.findall('a:author', ns)))
    aff = [x.text for a in e.findall('a:author', ns) for x in a.findall('ar:affiliation', ns)]
    if aff: print("AFFIL:", aff)
    print("PUBLISHED:", e.find('a:published', ns).text, " UPDATED:", e.find('a:updated', ns).text)
    print("PRIMARY CAT:", e.find('ar:primary_category', ns).attrib.get('term') if e.find('ar:primary_category', ns) is not None else None)
    c = e.find('ar:comment', ns); print("COMMENT:", c.text if c is not None else None)
    j = e.find('ar:journal_ref', ns); print("JOURNAL_REF:", j.text if j is not None else None)
    print("ABSTRACT:", re.sub(r'\s+',' ', e.find('a:summary', ns).text))
    print("-----")
