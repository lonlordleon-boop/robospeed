# -*- coding: utf-8 -*-
"""背負い物（ランドセルなど）を、1本の骨だけで動くように付け直す。
   自動リグは、背中のランドセルや肩ベルトに腕・肩・腰の重みを混ぜる。スキップや走りで腕を振ると、
   ランドセルが腕に引っ張られて伸び縮みした。背負い物は胸と一緒に丸ごと動くのが正しい。

   選び方（メッシュは体と1つながりなので、色とつながりで選ぶ）:
   1. 種の箱に入る頂点から始める（ランドセルの真ん中の、確実に背負い物である所）。
   2. 辺でつながった隣へ、「絵の色が背負い物の色」の頂点だけをたどって広げる。
   3. 広げてよい範囲を位置で制限する（例: 高さ z0 より下は、背中側 y >= y0 だけ）。スカートの赤へ漏れないように。
   4. 最後に1周だけ外へ広げ、ボタンや縁の色の違う頂点も拾う。
   色の判定: 色相が 赤±0.06、鮮やかさ >= 0.45、明るさ >= 0.12。
   座標は glTF（Y が上、前が +Z）。Blender の (x, y, z) は glTF の (x, -z, y)。背中側は glTF の -Z。

   実行: blender -b --factory-startup --python bindpart.py --
         入力.glb 出力.glb 骨の名前 "種の箱 x0,x1,y0,y1,z0,z1" "広げてよい範囲 高さ下限,この高さより下で許す背中側のz上限" [段々にする周の数]
   高さ下限を 9 にすると、背中側（z 上限より後ろ）だけを選ぶ（肩ベルトは元の重みのまま）。
   例（秀才少女のランドセル）: ... Spine "-0.12,0.12,0.35,0.55,-0.32,-0.20" "9,-0.12" 3
"""
import json, struct, sys, os, tempfile, colorsys
import numpy as np
import bpy

a = sys.argv[sys.argv.index("--")+1:]
SRC, DST, BONE = a[0], a[1], a[2]
SEED = [float(v) for v in a[3].split(',')]
ZLOW, BACKZ = [float(v) for v in a[4].split(',')]
BLENDR = int(a[5]) if len(a) > 5 else 0      # 境目を段々にする周の数

raw = open(SRC, 'rb').read(); off = 12; ck = []
while off < len(raw):
    ln, ty = struct.unpack_from('<II', raw, off); off += 8; ck.append((ty, off, ln)); off += ln
Jm = {t: (o, l) for t, o, l in ck}
G = json.loads(raw[Jm[0x4E4F534A][0]:Jm[0x4E4F534A][0]+Jm[0x4E4F534A][1]].decode('utf-8'))
BO, BL = Jm[0x004E4942]; bd = bytearray(raw[BO:BO+BL])
COMP = {5120:('b',1),5121:('B',1),5122:('h',2),5123:('H',2),5125:('I',4),5126:('f',4)}
NUM = {'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}
def lay(i):
    ac = G['accessors'][i]; n = NUM[ac['type']]; f, s = COMP[ac['componentType']]
    bv = G['bufferViews'][ac['bufferView']]
    return ac, n, f, bv.get('byteOffset',0)+ac.get('byteOffset',0), bv.get('byteStride') or n*s
def rd(i):
    ac, n, f, b, st = lay(i)
    return np.frombuffer(bytes(bd[b:b+st*ac['count']]), dtype=np.dtype('<'+f)).reshape(-1, st//COMP[ac['componentType']][1])[:, :n].astype(np.float64) if st == n*COMP[ac['componentType']][1] else np.array([struct.unpack_from('<'+f*n, bd, b+k*st) for k in range(ac['count'])], float)
def wr(i, arr):
    ac, n, f, b, st = lay(i)
    for k in range(ac['count']): struct.pack_into('<'+f*n, bd, b+k*st, *arr[k])

# 絵を取り出して画素を読む
img = G['images'][0]; bv = G['bufferViews'][img['bufferView']]
data = bytes(bd[bv.get('byteOffset',0):bv.get('byteOffset',0)+bv['byteLength']])
ext = '.png' if img.get('mimeType') == 'image/png' else '.jpg'
tmp = os.path.join(tempfile.gettempdir(), 'bindpart_tex' + ext); open(tmp, 'wb').write(data)
im = bpy.data.images.load(tmp); TW, TH = im.size
px = np.array(im.pixels[:], dtype=np.float32).reshape(TH, TW, 4)[:, :, :3]

joints = G['skins'][0]['joints']; jn = [G['nodes'][j].get('name') for j in joints]
BI = jn.index(BONE) if BONE != 'AUTO' else -1
tot = 0
for mesh in G['meshes']:
    for pr in mesh['primitives']:
        P = rd(pr['attributes']['POSITION']); UV = rd(pr['attributes']['TEXCOORD_0'])
        J = rd(pr['attributes']['JOINTS_0']).astype(int); W = rd(pr['attributes']['WEIGHTS_0'])
        I = rd(pr['indices']).astype(int).ravel().reshape(-1, 3)
        n = len(P)
        # glTF の UV は上が v=0。Blender の画素は下の行が先頭
        cols = px[np.clip(((1 - UV[:, 1]) * TH).astype(int), 0, TH-1), np.clip((UV[:, 0] * TW).astype(int), 0, TW-1)]
        hsv = np.array([colorsys.rgb_to_hsv(*c) for c in cols])
        isred = ((hsv[:, 0] < 0.06) | (hsv[:, 0] > 0.94)) & (hsv[:, 1] >= 0.45) & (hsv[:, 2] >= 0.12)
        # UV の継ぎ目で分かれた同じ位置の頂点をまとめる
        key = np.round(P / 1e-5).astype(np.int64); _, wid = np.unique(key, axis=0, return_inverse=True); wid = wid.ravel()
        nw = wid.max() + 1
        wred = np.zeros(nw, bool); np.logical_or.at(wred, wid, isred)
        wpos = np.zeros((nw, 3)); wpos[wid] = P
        nb = [set() for _ in range(nw)]
        for t in I:
            a0, b0, c0 = wid[t]
            nb[a0].update((b0, c0)); nb[b0].update((a0, c0)); nb[c0].update((a0, b0))
        allowed = (wpos[:, 1] >= ZLOW) | (wpos[:, 2] <= BACKZ)
        x0, x1, y0, y1, z0, z1 = SEED
        seed = (wpos[:, 0] >= x0) & (wpos[:, 0] <= x1) & (wpos[:, 1] >= y0) & (wpos[:, 1] <= y1) & (wpos[:, 2] >= z0) & (wpos[:, 2] <= z1) & wred
        sel = seed.copy(); front = list(np.nonzero(seed)[0])
        while front:
            nxt = []
            for v in front:
                for u in nb[v]:
                    if not sel[u] and wred[u] and allowed[u]:
                        sel[u] = True; nxt.append(u)
            front = nxt
        ring = sel.copy()
        for v in np.nonzero(sel)[0]:
            for u in nb[v]:
                if allowed[u]: ring[u] = True
        # 境目から外へ BLENDR 周ぶんは、骨の重みを段々に減らして元の重みへつなぐ。
        # いきなり切り替えると、ランドセルの縁と腕・ベストの間の面が引き伸ばされて裂けたように見えた
        dist = np.full(nw, -1); dist[ring] = 0; front = list(np.nonzero(ring)[0])
        for d in range(1, BLENDR + 1):
            nxt = []
            for v in front:
                for u in nb[v]:
                    if dist[u] < 0: dist[u] = d; nxt.append(u)
            front = nxt
        tw = np.where(dist < 0, 0.0, 1.0 - np.clip(dist, 0, None) / (BLENDR + 1))   # 位置ごとの骨の割合
        # 付け先。骨の名前が AUTO なら、選んだ所に元々付いていた胴の骨（腕・肩・手・頭・首・脚を除く）の重みの平均を、
        # 全部の頂点に同じだけ付ける。胸の骨1本に固定すると、腰や背骨が曲がったときにベストとの境目が伸びた
        if BONE == 'AUTO':
            skip = ('Arm', 'Hand', 'Shoulder', 'Head', 'head', 'neck', 'Leg', 'Foot', 'Toe')
            tot_w = {}
            for vi in np.nonzero(ring[wid])[0]:
                for k in range(4):
                    j = J[vi, k]
                    if W[vi, k] > 0 and not any(s in jn[j] for s in skip): tot_w[j] = tot_w.get(j, 0.0) + W[vi, k]
            top = sorted(tot_w.items(), key=lambda x: -x[1])[:4]; s = sum(w for _, w in top)
            TARGET = {j: w / s for j, w in top}
            print("BP 付け先（平均）: %s" % ", ".join("%s %.2f" % (jn[j], w) for j, w in TARGET.items()))
        else:
            TARGET = {BI: 1.0}
        for vi in np.nonzero(tw[wid] > 0)[0]:
            t = tw[wid[vi]]
            acc = {}
            for k in range(4):
                if W[vi, k] > 0: acc[J[vi, k]] = acc.get(J[vi, k], 0.0) + W[vi, k] * (1 - t)
            for j, w in TARGET.items(): acc[j] = acc.get(j, 0.0) + t * w
            top = sorted(acc.items(), key=lambda x: -x[1])[:4]
            s = sum(w for _, w in top)
            J[vi] = 0; W[vi] = 0.0
            for k, (j, w) in enumerate(top): J[vi, k] = j; W[vi, k] = w / s
        vs = ring[wid]
        wr(pr['attributes']['JOINTS_0'], J); wr(pr['attributes']['WEIGHTS_0'], W)
        q = wpos[ring]
        print("BP 種 %d → 選んだ位置 %d（頂点 %d）＋段々に %d 周（位置 %d）  範囲 x%.2f..%.2f 高さ%.2f..%.2f 前後z%.2f..%.2f → %s に付けた" % (
            seed.sum(), ring.sum(), vs.sum(), BLENDR, int(((dist > 0)).sum()), q[:, 0].min(), q[:, 0].max(), q[:, 1].min(), q[:, 1].max(), q[:, 2].min(), q[:, 2].max(), BONE))
        tot += vs.sum()

js = json.dumps(G, separators=(',',':')).encode('utf-8'); js += b' '*((4-len(js)%4)%4)
bn = bytes(bd); bn += b'\x00'*((4-len(bn)%4)%4)
out = (b'glTF' + struct.pack('<II',2,12+8+len(js)+8+len(bn)) + struct.pack('<II',len(js),0x4E4F534A) + js
       + struct.pack('<II',len(bn),0x004E4942) + bn)
open(DST, 'wb').write(out); print("BP 書き出し", DST)
