import urllib.request, re
req = urllib.request.Request('https://www.youtube.com/watch?v=s3Tj4yp6hxE', headers={'User-Agent': 'Mozilla/5.0'})
html = urllib.request.urlopen(req).read().decode('utf-8')
m = re.search(r'"shortDescription":"(.*?)(?<!\\\\)"', html)
print(m.group(1).replace('\\n', '\n') if m else 'not found')
