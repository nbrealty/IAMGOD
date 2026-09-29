import sys, re, subprocess, html
url = sys.argv[1]
maxc = int(sys.argv[2]) if len(sys.argv) > 2 else 6000
r = subprocess.run(["curl","-sSL","-m","40","-A","Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36","-w","\n__HTTP__%{http_code}","-e","https://www.google.com/",url],capture_output=True,text=True)
out = r.stdout
code = out.rsplit("__HTTP__",1)[-1].strip()
body = out.rsplit("__HTTP__",1)[0]
body = re.sub(r"(?is)<(script|style|noscript|svg|header|footer|nav)[^>]*>.*?</\1>", " ", body)
text = re.sub(r"(?s)<[^>]+>", " ", body)
text = html.unescape(re.sub(r"\s+", " ", text)).strip()
print("HTTP", code, "chars", len(text))
print(text[:maxc])
