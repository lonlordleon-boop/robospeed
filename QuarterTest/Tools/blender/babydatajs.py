# -*- coding: utf-8 -*-
"""乳児期の赤ちゃんの駒を、ページに埋め込む .js にする（2026年9月24日）。
   ページをファイルとして直接開くと（file:///）、ブラウザは .glb を読み込めない（「Failed to fetch」）。
   park12.html と同じく、glb を文字（base64）にして <script src> で読み込ませる。
   4色の立体を丸ごと埋めると 16MB を超えるので、立体は 1P の1つだけにし、2P〜4P は絵（JPEG）だけを入れて、ページ側で絵を差し替える。
   絵は PNG のままだと1枚 1.5MB 前後あるので JPEG（品質 88）にする。
   実行: blender -b --factory-startup -P babydatajs.py -- 1P.glb 2P.glb 3P.glb 4P.glb 出力.js"""
import bpy, sys, os, json, struct, base64, tempfile
a = sys.argv[sys.argv.index("--") + 1:]
SRCS, OUT = a[:4], a[4]
def read_glb(path):
    raw = open(path, 'rb').read(); off = 12; ck = []
    while off < len(raw):
        ln, ty = struct.unpack_from('<II', raw, off); off += 8; ck.append((ty, off, ln)); off += ln
    J = {t: (o, l) for t, o, l in ck}
    G = json.loads(raw[J[0x4E4F534A][0]:J[0x4E4F534A][0] + J[0x4E4F534A][1]].decode('utf-8'))
    BO, BL = J[0x004E4942]
    return G, bytearray(raw[BO:BO + BL])
def to_jpeg(G, bd):
    img = G['images'][0]; bv = G['bufferViews'][img['bufferView']]
    data = bytes(bd[bv.get('byteOffset', 0):bv.get('byteOffset', 0) + bv['byteLength']])
    ext = '.png' if img.get('mimeType', '').endswith('png') else '.jpg'
    t = os.path.join(tempfile.gettempdir(), 'babydata_in' + ext); open(t, 'wb').write(data)
    im = bpy.data.images.load(t)
    sc = bpy.context.scene; sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 88
    o = os.path.join(tempfile.gettempdir(), 'babydata_out.jpg'); im.save_render(o, scene=sc)
    bpy.data.images.remove(im)
    return open(o, 'rb').read()
jpgs = []
for p in SRCS:
    G, bd = read_glb(p); jpgs.append(to_jpeg(G, bd)); print("[data] %s → JPEG %d バイト" % (os.path.basename(p), len(jpgs[-1])))
# 1P の glb の絵を JPEG に入れ替える（バッファを詰め直す）
G, old = read_glb(SRCS[0]); img = G['images'][0]; ib = img['bufferView']
buf = bytearray()
for i, bv in enumerate(G['bufferViews']):
    o = bv.get('byteOffset', 0); data = jpgs[0] if i == ib else old[o:o + bv['byteLength']]
    while len(buf) % 4: buf.append(0)
    bv['byteOffset'] = len(buf); bv['byteLength'] = len(data); buf += data
while len(buf) % 4: buf.append(0)
G['buffers'][0]['byteLength'] = len(buf); img['mimeType'] = 'image/jpeg'
js = json.dumps(G, separators=(',', ':')).encode('utf-8'); js += b' ' * ((4 - len(js) % 4) % 4)
glb = b'glTF' + struct.pack('<II', 2, 12 + 8 + len(js) + 8 + len(buf)) + struct.pack('<II', len(js), 0x4E4F534A) + js + struct.pack('<II', len(buf), 0x004E4942) + bytes(buf)
with open(OUT, 'w', encoding='utf-8') as f:
    f.write('// 乳児期の赤ちゃんの駒（ひじを伸ばしたままのハイハイ）。babydatajs.py で作った。2026年9月24日\n')
    f.write('// ファイルを直接開いても読めるよう、glb を base64 で埋め込む。BABY_GLB は 1P（茶）、BABY_TEX の 1〜3 は 2P 緑・3P 青・4P 紫の絵（JPEG）\n')
    f.write('window.BABY_GLB = "%s";\n' % base64.b64encode(glb).decode('ascii'))
    f.write('window.BABY_TEX = [null, %s];\n' % ', '.join('"data:image/jpeg;base64,%s"' % base64.b64encode(j).decode('ascii') for j in jpgs[1:]))
print("[data] glb %d バイト・書き出し %s（%d バイト）" % (len(glb), OUT, os.path.getsize(OUT)))
