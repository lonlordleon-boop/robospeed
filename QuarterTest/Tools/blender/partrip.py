# -*- coding: utf-8 -*-
"""くっついて生成された「腕（手）」と「体側の物（鞄・ベスト）」を、メッシュの上で切り離す。

   わんぱく少女は、下ろした右手の指と肩掛け鞄の横が、同じ三角形でつながって生成されていた（2026年9月23日）。
   bagrig.py で鞄を胴の骨だけに付け直すと、鞄は崩れなくなったが、手とつながった三角形だけが
   腕を振ると大きく引き伸ばされ、鞄の下にギザギザの布が出た（伸びた辺 Wave 45 → 154 本）。
   重みの付け替えだけでは直らない。つながっている限り、手が動けばその三角形は伸びる。

   箱の中で、同じ位置の頂点ごとに「腕」（腕の骨の重み 0.5 以上）か「体」かを決め、
   ・体の頂点からは腕の重みを全部外して胴の骨へ、腕の頂点からは腕以外の重みを外して腕の骨へ移す
   ・腕と体の両方の頂点を持つ三角形は、多い方の側に付ける。少ない側の頂点は同じ位置・同じ UV・同じ法線の
     複製を作り、その三角形だけ複製を使う。複製の重みは、付ける側の頂点の重み（その三角形の中の平均）
   こうすると三角形はどちらか一方の骨だけで動くので、引き伸ばされない。
   切ったところは面のふちになる（手と鞄が触れていた所なので、ふだんは見えない）。
   元の頂点・三角形は残し、新しい並びを glb の後ろに足す。形・絵・動きは変えない。

   座標は glTF（X 左右・Y 上・Z 前）。キャラの右は −X。
   実行: python partrip.py 入力.glb 出力.glb 側(Right/Left) "x0,x1,y0,y1,z0,z1" [any]
         （blender -b --factory-startup --python-expr から呼んでもよい）
   例（わんぱく少女の右手と鞄）: ... Right "-0.33,-0.05,0.36,0.55,-0.14,0.32" """
import json, struct, sys
import numpy as np

a = [x for x in sys.argv[1:]]
if '--' in a: a = a[a.index('--') + 1:]
SRC, DST, SIDE = a[0], a[1], a[2]
X0, X1, Y0, Y1, Z0, Z1 = [float(v) for v in a[3].split(',')]

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
def add(arr, like, target=None, ctype=None):
    global bd
    ac0 = dict(G['accessors'][like])
    if ctype: ac0['componentType'] = ctype
    arr = np.ascontiguousarray(arr.astype(DT[ac0['componentType']]))
    while len(bd) % 4: bd.append(0)
    bv = {'buffer': 0, 'byteOffset': len(bd), 'byteLength': arr.nbytes}
    if target: bv['target'] = target
    bd += arr.tobytes(); G['bufferViews'].append(bv)
    ac = {'bufferView': len(G['bufferViews']) - 1, 'componentType': ac0['componentType'], 'count': int(arr.shape[0]), 'type': ac0['type']}
    if ac0.get('normalized'): ac['normalized'] = True
    if 'min' in ac0 and arr.ndim > 1:
        ac['min'] = arr.min(0).tolist(); ac['max'] = arr.max(0).tolist()
    G['accessors'].append(ac); return len(G['accessors']) - 1

sk = G['skins'][0]; names = [G['nodes'][j].get('name') for j in sk['joints']]
ARMS = [k for k, n in enumerate(names) if n in (SIDE + 'Shoulder', SIDE + 'Arm', SIDE + 'ForeArm', SIDE + 'Hand')]
TRUNK = [names.index(n) for n in ('Hips', 'Spine02', 'Spine01', 'Spine') if n in names]
IBM = rd(sk['inverseBindMatrices']).astype(float).reshape(-1, 4, 4).transpose(0, 2, 1)
ty = np.array([np.linalg.inv(IBM[k])[1, 3] for k in TRUNK])

cands = [(G['accessors'][m['primitives'][0]['attributes']['POSITION']]['count'], i)
         for i, m in enumerate(G['meshes']) if 'JOINTS_0' in m['primitives'][0]['attributes']]
pr = G['meshes'][max(cands)[1]]['primitives'][0]
att = {k: rd(v) for k, v in pr['attributes'].items()}
if pr.get('targets'): raise SystemExit("PR モーフのあるメッシュには未対応")
P = att['POSITION'].astype(float)
tri = rd(pr['indices']).astype(np.int64).reshape(-1, 3)
J = att['JOINTS_0'].astype(np.int64)
wac = G['accessors'][pr['attributes']['WEIGHTS_0']]
WMAX = 1.0 if wac['componentType'] == 5126 else float(np.iinfo(DT[wac['componentType']]).max)
W = att['WEIGHTS_0'].astype(float) / WMAX
nv0 = len(P)

key = np.round(P / 1e-5).astype(np.int64)
_, gid = np.unique(key, axis=0, return_inverse=True); gid = gid.ravel(); ng = gid.max() + 1
armw = np.zeros(len(P))
for k in ARMS: armw += np.where(J == k, W, 0).sum(1)
garm = np.zeros(ng); np.maximum.at(garm, gid, armw)
gpos = np.zeros((ng, 3)); gpos[gid] = P
inbox = (gpos[:, 0] >= X0) & (gpos[:, 0] <= X1) & (gpos[:, 1] >= Y0) & (gpos[:, 1] <= Y1) & (gpos[:, 2] >= Z0) & (gpos[:, 2] <= Z1)
isarm = garm >= 0.5

# 重みを2つに分ける
def regroup(vi, keep_arm):
    acc = {}
    for k in range(J.shape[1]):
        if W[vi, k] > 0: acc[int(J[vi, k])] = acc.get(int(J[vi, k]), 0.0) + W[vi, k]
    armp = {j: w for j, w in acc.items() if j in ARMS}; rest = {j: w for j, w in acc.items() if j not in ARMS}
    if keep_arm:
        new = armp if armp else acc
    else:
        tr = {j: w for j, w in rest.items() if j in TRUNK}
        moved = sum(armp.values())
        new = dict(rest)
        if moved > 0:
            if tr:
                s = sum(tr.values())
                for j, w in tr.items(): new[j] += moved * w / s
            else:
                y = P[vi, 1]; o = np.argsort(np.abs(ty - y))[:2]
                dd = np.abs(ty[o] - y) + 1e-6; ww = (1 / dd) / (1 / dd).sum()
                for oi, w in zip(o, ww): new[TRUNK[oi]] = new.get(TRUNK[oi], 0.0) + moved * w
    top = sorted(new.items(), key=lambda x: -x[1])[:J.shape[1]]
    s = sum(w for _, w in top) or 1.0
    J[vi] = 0; W[vi] = 0
    for k, (j, w) in enumerate(top): J[vi, k] = j; W[vi, k] = w / s
vin = np.nonzero(inbox[gid])[0]
for vi in vin: regroup(vi, bool(isarm[gid[vi]]))
print("PR 箱の中の位置 %d：腕 %d・体 %d" % (int(inbox.sum()), int((inbox & isarm).sum()), int((inbox & ~isarm).sum())))

# 腕と体の両方の頂点を持つ三角形を、多い方へ付ける
tg = gid[tri]
# 5番目に any を渡すと、箱に1点でもかかる三角形を切る（箱の外は重みを変えないので、箱のふちでつながったまま伸びた）
tin = inbox[tg].any(1) if (len(a) > 4 and a[4] == 'any') else inbox[tg].all(1)
ta = isarm[tg]
mixed = tin & ta.any(1) & ~ta.all(1)
newsrc = []; newJ = []; newW = []; dupkey = {}
for t in np.nonzero(mixed)[0]:
    side_arm = ta[t].sum() >= 2
    own = [c for c in range(3) if ta[t, c] == side_arm]
    # 付ける側の重み（その三角形の中の平均）
    acc = {}
    for c in own:
        vi = tri[t, c]
        for k in range(J.shape[1]):
            if W[vi, k] > 0: acc[int(J[vi, k])] = acc.get(int(J[vi, k]), 0.0) + W[vi, k] / len(own)
    top = sorted(acc.items(), key=lambda x: -x[1])[:J.shape[1]]; s = sum(w for _, w in top) or 1.0
    jj = [j for j, _ in top] + [0] * (J.shape[1] - len(top)); ww = [w / s for _, w in top] + [0.0] * (J.shape[1] - len(top))
    for c in range(3):
        if ta[t, c] == side_arm: continue
        vi = tri[t, c]
        k2 = (int(vi), bool(side_arm), tuple(jj), tuple(np.round(ww, 4)))
        if k2 not in dupkey:
            dupkey[k2] = nv0 + len(newsrc); newsrc.append(vi); newJ.append(jj); newW.append(ww)
        tri[t, c] = dupkey[k2]
print("PR 切り離した三角形 %d（腕の側へ %d・体の側へ %d）、複製した頂点 %d" % (int(mixed.sum()), int((mixed & (ta.sum(1) >= 2)).sum()), int((mixed & (ta.sum(1) < 2)).sum()), len(newsrc)))

src = np.array(newsrc, np.int64)
Jall = np.concatenate([J, np.array(newJ, np.int64).reshape(-1, J.shape[1])])
Wall = np.concatenate([W, np.array(newW, float).reshape(-1, W.shape[1])])
old = dict(pr['attributes'])
for k in old:
    if k.startswith('JOINTS_') or k.startswith('WEIGHTS_'): continue
    arr = np.concatenate([att[k], att[k][src]]) if len(src) else att[k]
    pr['attributes'][k] = add(arr, old[k], 34962)
pr['attributes']['JOINTS_0'] = add(Jall, old['JOINTS_0'], 34962)
if WMAX == 1.0: Wout = Wall.astype(np.float32)
else:
    Wout = np.round(Wall * WMAX).astype(np.int64); Wout[:, 0] += int(WMAX) - Wout.sum(1)
pr['attributes']['WEIGHTS_0'] = add(Wout, old['WEIGHTS_0'], 34962)
pr['indices'] = add(tri.reshape(-1), pr['indices'], 34963, 5125 if len(Jall) > 65535 else None)
G['accessors'][pr['indices']].pop('min', None); G['accessors'][pr['indices']].pop('max', None)
G['buffers'][0]['byteLength'] = len(bd)
js = json.dumps(G, separators=(',', ':')).encode('utf-8'); js += b' ' * ((4 - len(js) % 4) % 4)
bn = bytes(bd); bn += b'\x00' * ((4 - len(bn) % 4) % 4)
out = b'glTF' + struct.pack('<II', 2, 12 + 8 + len(js) + 8 + len(bn)) + struct.pack('<II', len(js), 0x4E4F534A) + js + struct.pack('<II', len(bn), 0x004E4942) + bn
open(DST, 'wb').write(out)
print("PR 書き出し", DST)
