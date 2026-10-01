import urllib.request
import urllib.parse
import re

req = urllib.request.Request('https://music.youtube.com/search?q=Blinding+Lights', headers={'User-Agent': 'Mozilla/5.0'})
html = urllib.request.urlopen(req).read().decode('utf-8')
matches = re.findall(r'"([a-zA-Z0-9_-]{11})"', html)
print(matches[:50])
