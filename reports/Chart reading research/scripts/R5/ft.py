import sys, re, subprocess, html
url = sys.argv[1]; maxc = int(sys.argv[2]) if len(sys.argv) > 2 else 5000; start = int(sys.argv[3]) if len(sys.argv) > 3 else 0
r = subprocess.run(["curl","-sSL","-m","45","-A","Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36","-w","\n__HTTP__%{http_code}",url],capture_output=True,text=True)
out = r.stdout; code = out.rsplit("__HTTP__",1)[-1].strip(); body = out.rsplit("__HTTP__",1)[0]
body = re.sub(r"(?is)<(script|style|noscript|svg|header|footer|nav)[^>]*>.*?</\1>", " ", body)
text = html.unescape(re.sub(r"\s+", " ", re.sub(r"(?s)<[^>]+>", " ", body))).strip()
print("HTTP", code, "chars", len(text)); print(text[start:start+maxc])
