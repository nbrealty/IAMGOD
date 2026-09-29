import sys, json, urllib.parse, urllib.request
q = sys.argv[1]
url = "https://api.crossref.org/works?" + urllib.parse.urlencode({"query.bibliographic": q, "rows": 1, "select": "title,DOI,container-title,issued,author,volume,issue,page,type"})
d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "research-check (mailto:nelsao1994@gmail.com)"}), timeout=30))
for it in d["message"]["items"]:
    a = "; ".join((x.get("family", "") + ", " + x.get("given", "")[:1]) for x in it.get("author", [])[:4])
    print(f"{a} | {it.get('title',[''])[0]} | {it.get('container-title',[''])[0]} {it.get('volume','')}({it.get('issue','')}) {it.get('page','')} | {it['issued']['date-parts'][0][0]} | doi:{it['DOI']}")
