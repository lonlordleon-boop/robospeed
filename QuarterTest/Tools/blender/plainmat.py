# -*- coding: utf-8 -*-
"""GLB の材質から「発光」と余計な拡張を外して、普通の色付き材質にする。

   Meshy が出した生の GLB は、色のテクスチャをそのまま発光（emissive）にも入れている。
   three.js（preview / dressup）で読むと自ら光って白っぽく飛んでしまうので、
   発光と KHR_materials_specular / ior を外し、金属度 0・粗さ 0.8 に揃える。
   貼り直し（retexture）を通した GLB には元から無いので、生の GLB を直接使うときだけ要る。
   バイナリ部分は触らず、JSON 部分だけ書き換える。

   実行: python plainmat.py 入力.glb 出力.glb
"""
import json, struct, sys

SRC, DST = sys.argv[1], sys.argv[2]
raw = open(SRC, 'rb').read()
off = 12; chunks = []
while off < len(raw):
    ln, ty = struct.unpack_from('<II', raw, off); off += 8
    chunks.append((ty, raw[off:off+ln])); off += ln
G = json.loads(next(c for t, c in chunks if t == 0x4E4F534A).decode('utf-8'))
n = 0
for m in G.get('materials', []):
    changed = False
    for k in ('emissiveFactor', 'emissiveTexture', 'extensions'):
        if k in m: del m[k]; changed = True
    pbr = m.setdefault('pbrMetallicRoughness', {})
    if pbr.get('metallicFactor', 1.0) != 0.0 or abs(pbr.get('roughnessFactor', 1.0) - 0.8) > 1e-6:
        pbr['metallicFactor'] = 0.0; pbr['roughnessFactor'] = 0.8; changed = True
    if changed: n += 1
    print("PM 材質 %s: 発光なし 金属度 0 粗さ 0.8" % m.get('name'))
for k in ('extensionsUsed', 'extensionsRequired'):
    if k in G:
        G[k] = [e for e in G[k] if e not in ('KHR_materials_specular', 'KHR_materials_ior')]
        if not G[k]: del G[k]
js = json.dumps(G, separators=(',', ':'), ensure_ascii=False).encode('utf-8'); js += b' ' * ((4 - len(js) % 4) % 4)
out = struct.pack('<II', len(js), 0x4E4F534A) + js
for t, c in chunks:
    if t == 0x4E4F534A: continue
    c = c + b'\x00' * ((4 - len(c) % 4) % 4)
    out += struct.pack('<II', len(c), t) + c
out = b'glTF' + struct.pack('<II', 2, 12 + len(out)) + out
open(DST, 'wb').write(out)
print("PM 直した材質 %d 個  書き出し %s" % (n, DST))
