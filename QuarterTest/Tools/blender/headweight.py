# -*- coding: utf-8 -*-
"""頭（顔・髪）を、頭の骨だけで動くように重みを付け直す。

   芸術少女は、待機の動きで頭が縮んだり膨らんだりして見えた（2026年9月23日）。
   Meshy の自動の骨入れで、後頭部の髪の重みが 頭 0.5・胸（Spine）0.3・肩 などに分かれていた
   （顔の前側は頭だけ）。首や胸が動くと後ろ半分だけが遅れてついてくるので、
   頭の奥行きが 待機の中で ±7% 伸び縮みしていた（わんぱく少女は ±1%）。

   高さ Y0 から Y1 にかけて、頭の重みの下限をなめらかに 0 → 1 に上げる（Y1 より上は頭だけ）。
   頭の重みが下限より小さい頂点は、ほかの骨の重みを同じ割合で減らし、減らした分を頭の骨に移す。
   もとから下限より大きい頂点は変えない。形・絵・動きは変えない。
   頭の重み = Head・head_end・headfront の合計。移す先は Head。

   座標は glTF（Y 上）。
   実行: python headweight.py 入力.glb 出力.glb Y0 Y1
         （blender -b --factory-startup --python-expr から呼んでもよい）
   例（芸術少女）: ... 0.69 0.735   （首の付け根 0.69・あごの下 0.72）"""
import json, struct, sys
import numpy as np

a = [x for x in sys.argv[1:]]
if '--' in a: a = a[a.index('--') + 1:]
SRC, DST, Y0, Y1 = a[0], a[1], float(a[2]), float(a[3])

raw = open(SRC, 'rb').read(); off = 12; ck = []
while off < len(raw):
    ln, ty = struct.unpack_from('<II', raw, off); off += 8; ck.append((ty, off, ln)); off += ln
Jm = {t: (o, l) for t, o, l in ck}
G = json.loads(raw[Jm[0x4E4F534A][0]:Jm[0x4E4F534A][0] + Jm[0x4E4F534A][1]].decode('utf-8'))
BO, BL = Jm[0x004E4942]; bd = bytearray(raw[BO:BO + BL])
DT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NUM = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}
def rd(i):
    ac = G['accessors'][i]; bv = G['bufferViews'][ac['bufferView']]
    n = NUM[ac['type']]; dt = np.dtype(DT[ac['componentType']])
    b = bv.get('byteOffset', 0) + ac.get('byteOffset', 0); st = bv.get('byteStride') or n * dt.itemsize
    out = np.empty((ac['count'], n), dt)
    for k in range(n): out[:, k] = np.ndarray((ac['count'],), dt, bd, b + k * dt.itemsize, (st,))
    return out
def add(arr, like, target=None):
    global bd
    ac0 = dict(G['accessors'][like])
    arr = np.ascontiguousarray(arr.astype(DT[ac0['componentType']]))
    while len(bd) % 4: bd.append(0)
    bv = {'buffer': 0, 'byteOffset': len(bd), 'byteLength': arr.nbytes}
    if target: bv['target'] = target
    bd += arr.tobytes(); G['bufferViews'].append(bv)
    ac = {'bufferView': len(G['bufferViews']) - 1, 'componentType': ac0['componentType'], 'count': int(arr.shape[0]), 'type': ac0['type']}
    if ac0.get('normalized'): ac['normalized'] = True
    G['accessors'].append(ac); return len(G['accessors']) - 1

sk = G['skins'][0]; names = [G['nodes'][j].get('name') for j in sk['joints']]
HEADS = [k for k, n in enumerate(names) if n in ('Head', 'head_end', 'headfront')]
HEAD = names.index('Head')

done = set()
for mi, mesh in enumerate(G['meshes']):
    for pr in mesh['primitives']:
        at = pr['attributes']
        if 'JOINTS_0' not in at or (at['JOINTS_0'], at['WEIGHTS_0']) in done: continue
        done.add((at['JOINTS_0'], at['WEIGHTS_0']))
        P = rd(at['POSITION']).astype(float)
        J = rd(at['JOINTS_0']).astype(np.int64)
        wac = G['accessors'][at['WEIGHTS_0']]
        WMAX = 1.0 if wac['componentType'] == 5126 else float(np.iinfo(DT[wac['componentType']]).max)
        W = rd(at['WEIGHTS_0']).astype(float) / WMAX
        s = W.sum(1, keepdims=True); W = W / np.where(s > 0, s, 1)
        ishead = np.isin(J, HEADS)
        h = np.where(ishead, W, 0).sum(1)
        t = np.clip((P[:, 1] - Y0) / (Y1 - Y0), 0, 1); t = t * t * (3 - 2 * t)      # なめらかに
        tgt = np.maximum(h, t)
        ch = np.nonzero(tgt > h + 1e-6)[0]
        nk = J.shape[1]
        for vi in ch:
            acc = {}
            for k in range(nk):
                if W[vi, k] > 0: acc[int(J[vi, k])] = acc.get(int(J[vi, k]), 0.0) + W[vi, k]
            rest = 1 - h[vi]; f = (1 - tgt[vi]) / rest if rest > 1e-9 else 0.0
            new = {}
            for j, w in acc.items():
                new[j] = w if j in HEADS else w * f
            new[HEAD] = new.get(HEAD, 0.0) + (tgt[vi] - h[vi])
            top = sorted(new.items(), key=lambda x: -x[1])[:nk]; ss = sum(w for _, w in top) or 1.0
            J[vi] = 0; W[vi] = 0
            for k, (j, w) in enumerate(top): J[vi, k] = j; W[vi, k] = w / ss
        h2 = np.where(np.isin(J, HEADS), W, 0).sum(1)
        print("HW メッシュ%d: 付け直した頂点 %d / %d。Y1 より上で頭の重みが 0.99 未満: 前 %d → 後 %d"
              % (mi, len(ch), len(P), int(((P[:, 1] >= Y1) & (h < 0.99)).sum()), int(((P[:, 1] >= Y1) & (h2 < 0.99)).sum())))
        at['JOINTS_0'] = add(J, at['JOINTS_0'], 34962)
        if WMAX == 1.0: Wout = W.astype(np.float32)
        else:
            Wout = np.round(W * WMAX).astype(np.int64); Wout[:, 0] += int(WMAX) - Wout.sum(1)
        at['WEIGHTS_0'] = add(Wout, at['WEIGHTS_0'], 34962)

G['buffers'][0]['byteLength'] = len(bd)
js = json.dumps(G, separators=(',', ':')).encode('utf-8'); js += b' ' * ((4 - len(js) % 4) % 4)
bn = bytes(bd); bn += b'\x00' * ((4 - len(bn) % 4) % 4)
out = b'glTF' + struct.pack('<II', 2, 12 + 8 + len(js) + 8 + len(bn)) + struct.pack('<II', len(js), 0x4E4F534A) + js + struct.pack('<II', len(bn), 0x004E4942) + bn
open(DST, 'wb').write(out)
print("HW 書き出し", DST)
