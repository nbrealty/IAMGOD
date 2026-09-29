#!/usr/bin/env python3
# usage: h.py URL [maxchars] [grep-regex]  -> prints stripped text of a web page
import sys, re, subprocess, html
url=sys.argv[1]; mx=int(sys.argv[2]) if len(sys.argv)>2 else 3000
pat=sys.argv[3] if len(sys.argv)>3 else None
r=subprocess.run(['curl','-sSL','--max-time','60','-A','Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36','-w','\n@@HTTP %{http_code} %{content_type}\n',url],capture_output=True)
b=r.stdout.decode('utf-8','ignore')
i=b.rfind('@@HTTP'); meta=b[i:].strip(); b=b[:i]
b=re.sub(r'(?is)<(script|style|noscript)[^>]*>.*?</\1>','',b)
b=re.sub(r'(?s)<[^>]+>',' ',b)
b=html.unescape(b)
b=re.sub(r'[ \t\r\f\v]+',' ',b)
b=re.sub(r'\n\s*\n+','\n',b)
print(meta, 'len',len(b))
if pat:
    for m in re.finditer(pat,b,flags=re.I):
        s=max(0,m.start()-300); e=min(len(b),m.end()+500)
        print('...',b[s:e].replace('\n',' '),'...\n')
else:
    print(b[:mx])
