# -*- coding: utf-8 -*-
import urllib.request, json, uuid
boundary = '----t' + uuid.uuid4().hex
p = r'd:\project\0824cloth\0901dxf\缝合关系文件\13 FG短袖.review-package\13FG短袖.reviewed.dxf'
data = open(p, 'rb').read()
body = b''
body += ('--' + boundary + '\r\n').encode()
body += ('Content-Disposition: form-data; name="file"; filename="13FG.dxf"\r\n'
         'Content-Type: application/octet-stream\r\n\r\n').encode()
body += data
body += ('\r\n--' + boundary + '--\r\n').encode()
req = urllib.request.Request(
    'http://127.0.0.1:8010/api/annotate', data=body,
    headers={'Content-Type': 'multipart/form-data; boundary=' + boundary}, method='POST')
r = urllib.request.urlopen(req, timeout=30)
res = json.loads(r.read().decode('utf-8'))
seam = res['seam']['stitches']
print('stitch_count =', len(seam))
for s in seam:
    print(' ', s['stitch_id'], s['relation'], s['confidence_source'])