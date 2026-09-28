# -*- coding: utf-8 -*-
"""頭はそのままで、首から下の体を広げる（横幅・奥行き・高さ）、腕を長くする。骨と動きもいっしょに直す。

   芸術少女・わんぱく少女は、顔の輪郭を元気少女・ギャル少女に合わせたら、体が小さかった（2026年9月23日）。
   preview と同じ縮尺で骨の関節を比べると、ギャル少女に対して
     芸術: 肩幅 −27%、腕の長さ −15%、腰幅 −30%、肩の高さ −3.4cm
     わんぱく: 肩幅 −13%、腕の長さ −24%、腰幅 −7%
   ・体（頭と腕以外の骨）: 足元の真ん中を基準に、左右 SX・高さ SY・前後 SZ 倍
   ・首: 首の関節では体と同じ動き、Head の関節では動かない。その間は高さでなだらかにつなぐ
   ・頭（Head・head_end・headfront）: 動かさない（顔の輪郭は合わせ済み）
   ・腕: 肩の関節を体といっしょに動かし、そこから骨の向きに FA 倍に伸ばす。太さは 1+(FA−1)×0.3 倍、手の大きさも同じ
   頂点は、骨の重みで各骨の動かし方を混ぜる。法線も同じように直す。
   骨の関節の位置・骨の逆行列（inverseBindMatrices）・動きの位置のキーを新しい位置に合わせる
   （Blender の書き出しで、動きには全部の骨の位置のキーが入っている。腰（Hips）以外は差を足し、腰は上下の動きを SY 倍する）。

   preview は首の関節の高さで大きさをそろえるので、SY を変えたら scaleAdj も SY 倍にすること（顔の大きさを保つため）。
   座標は glTF（X 左右・Y 上・Z 前）。glb を直接書き換える。元の並びは残して、新しい並びを後ろに足す。
   実行: python bodyscale.py 入力.glb 出力.glb SX SY SZ FA"""
import json, struct, sys
import numpy as np

a = [x for x in sys.argv[1:]]
if '--' in a: a = a[a.index('--') + 1:]
SRC, DST = a[0], a[1]
SX, SY, SZ, FA = [float(v) for v in a[2:6]]
FP = 1 + (FA - 1) * 0.3      # 腕の太さと手の大きさ

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
    ac0 = G['accessors'][like]
    arr = np.ascontiguousarray(arr.astype(DT[ac0['componentType']]))
    while len(bd) % 4: bd.append(0)
    bv = {'buffer': 0, 'byteOffset': len(bd), 'byteLength': arr.nbytes}
    if target: bv['target'] = target
    bd += arr.tobytes(); G['bufferViews'].append(bv)
    ac = {'bufferView': len(G['bufferViews']) - 1, 'componentType': ac0['componentType'], 'count': int(arr.shape[0]), 'type': ac0['type']}
    if ac0.get('normalized'): ac['normalized'] = True
    if 'min' in ac0:
        ac['min'] = arr.min(0).tolist(); ac['max'] = arr.max(0).tolist()
    G['accessors'].append(ac); return len(G['accessors']) - 1

# 節の今の姿勢（素の姿勢）
def trs(n):
    if 'matrix' in n: return np.array(n['matrix'], float).reshape(4, 4).T
    t = np.array(n.get('translation', [0, 0, 0]), float); q = n.get('rotation', [0, 0, 0, 1]); s = np.array(n.get('scale', [1, 1, 1]), float)
    x, y, z, w = q
    R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                  [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                  [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    M = np.eye(4); M[:3, :3] = R * s; M[:3, 3] = t; return M
parent = {}
for i, n in enumerate(G['nodes']):
    for c in n.get('children', []): parent[c] = i
glob = {}
def gl(i):
    if i not in glob: glob[i] = (gl(parent[i]) if i in parent else np.eye(4)) @ trs(G['nodes'][i])
    return glob[i]
sk = G['skins'][0]; joints = sk['joints']; names = [G['nodes'][j].get('name') for j in joints]
IBM = rd(sk['inverseBindMatrices']).reshape(-1, 4, 4).transpose(0, 2, 1).astype(float)
Gj = [gl(j) for j in joints]
err = max(np.abs(np.linalg.inv(IBM[k]) - Gj[k]).max() for k in range(len(joints)))
print("BS 素の姿勢と骨の逆行列のずれ %.2e" % err)
J = {names[k]: Gj[k][:3, 3].copy() for k in range(len(joints))}

cands = [(G['accessors'][m['primitives'][0]['attributes']['POSITION']]['count'], i)
         for i, m in enumerate(G['meshes']) if 'JOINTS_0' in m['primitives'][0]['attributes']]
pr = G['meshes'][max(cands)[1]]['primitives'][0]
P = rd(pr['attributes']['POSITION']).astype(float); N = rd(pr['attributes']['NORMAL']).astype(float)
JI = rd(pr['attributes']['JOINTS_0']).astype(int)
WA = G['accessors'][pr['attributes']['WEIGHTS_0']]
WW = rd(pr['attributes']['WEIGHTS_0']).astype(float)
if WA['componentType'] != 5126: WW /= np.iinfo(DT[WA['componentType']]).max
WW /= np.maximum(WW.sum(1, keepdims=True), 1e-9)
Y0 = P[:, 1].min(); CZ = J['Hips'][2]
S3 = np.array([SX, SY, SZ])
def B(p): return np.array([0, Y0, CZ]) + (p - np.array([0, Y0, CZ])) * S3
BN = 1.0 / S3                          # 体の変形での法線の直し方（逆転置）
print("BS 足元 %.4f  体 左右 %.3f 高さ %.3f 前後 %.3f  腕の長さ %.3f（太さ %.3f）" % (Y0, SX, SY, SZ, FA, FP))

HEAD = {'Head', 'head_end', 'headfront'}
hy, ny = J['Head'][1], J['neck'][1]
# 腕：肩の関節は体といっしょに動かし、骨の向きに FA、横に FP
def armR(u): u = u / np.linalg.norm(u); return FP * np.eye(3) + (FA - FP) * np.outer(u, u)
NEWJ = {}
for nm in names:
    if nm in HEAD: NEWJ[nm] = J[nm].copy()
    else: NEWJ[nm] = B(J[nm])
maps = {}                              # 骨の名前 → (位置を写す関数, 法線を写す関数)
for side in ('Left', 'Right'):
    ja, jf, jh = J[side + 'Arm'], J[side + 'ForeArm'], J[side + 'Hand']
    Ra, Rf = armR(jf - ja), armR(jh - jf)
    na = B(ja); nf = na + Ra @ (jf - ja); nh = nf + Rf @ (jh - jf)
    NEWJ[side + 'Arm'], NEWJ[side + 'ForeArm'], NEWJ[side + 'Hand'] = na, nf, nh
    maps[side + 'Arm'] = (lambda p, na=na, ja=ja, R=Ra: na + (p - ja) @ R.T, lambda n, R=Ra: n @ np.linalg.inv(R))
    maps[side + 'ForeArm'] = (lambda p, nf=nf, jf=jf, R=Rf: nf + (p - jf) @ R.T, lambda n, R=Rf: n @ np.linalg.inv(R))
    maps[side + 'Hand'] = (lambda p, nh=nh, jh=jh: nh + (p - jh) * FP, lambda n: n)
    print("BS %s 肩 %s→%s  手首 %s→%s  腕の長さ %.3f→%.3f" % (side, np.round(ja, 3), np.round(na, 3), np.round(jh, 3), np.round(nh, 3),
          np.linalg.norm(jf - ja) + np.linalg.norm(jh - jf), np.linalg.norm(nf - na) + np.linalg.norm(nh - nf)))

def body_map(p): return np.array([0, Y0, CZ]) + (p - np.array([0, Y0, CZ])) * S3
def body_nrm(n): return n * BN
def neck_map(p):
    t = np.clip((p[:, 1] - ny) / max(hy - ny, 1e-6), 0, 1)[:, None]
    return p + (1 - t) * (body_map(p) - p)
def neck_nrm(n): return n            # 首は混ぜた形なので、法線はあとで元の向きと体の向きの間を取る

# 頂点を写す
P2 = np.zeros_like(P); N2 = np.zeros_like(N)
for k, nm in enumerate(names):
    for slot in range(JI.shape[1]):
        m = (JI[:, slot] == k) & (WW[:, slot] > 0)
        if not m.any(): continue
        w = WW[m, slot][:, None]; p = P[m]; n = N[m]
        if nm in HEAD: q, nn = p, n
        elif nm == 'neck':
            t = np.clip((p[:, 1] - ny) / max(hy - ny, 1e-6), 0, 1)[:, None]
            q = neck_map(p); nn = n * (t + (1 - t) * BN)
        elif nm in maps: q, nn = maps[nm][0](p), maps[nm][1](n)
        else: q, nn = body_map(p), body_nrm(n)
        P2[m] += w * q; N2[m] += w * nn / np.maximum(np.linalg.norm(nn, axis=1, keepdims=True), 1e-12)
N2 /= np.maximum(np.linalg.norm(N2, axis=1, keepdims=True), 1e-12)
d = np.linalg.norm(P2 - P, axis=1)
print("BS 頂点の動き 平均 %.4f 最大 %.4f" % (d.mean(), d.max()))

# 骨：新しい素の姿勢（回転はそのまま、位置だけ変える）
Gn = {}
for k, j in enumerate(joints):
    M = Gj[k].copy(); M[:3, 3] = NEWJ[names[k]]; Gn[j] = M
old_t = {}; new_t = {}
for k, j in enumerate(joints):
    p = parent.get(j)
    Gp = Gn[p] if p in Gn else (gl(p) if p is not None else np.eye(4))
    L = np.linalg.inv(Gp) @ Gn[j]
    n = G['nodes'][j]
    old_t[j] = np.array(n.get('translation', [0, 0, 0]), float)
    new_t[j] = L[:3, 3]
    n['translation'] = [float(v) for v in L[:3, 3]]
IBMn = np.stack([np.linalg.inv(Gn[j]).T for j in joints]).reshape(-1, 16)
sk['inverseBindMatrices'] = add(IBMn, sk['inverseBindMatrices'])

# 動きの位置のキー
hips = joints[names.index('Hips')]
nch = 0
for an in G.get('animations', []):
    for ch in an['channels']:
        j = ch['target']['node']
        if ch['target']['path'] != 'translation' or j not in new_t: continue
        smp = an['samplers'][ch['sampler']]
        v = rd(smp['output']).astype(float)
        if j == hips: v2 = new_t[j] + (v - old_t[j]) * SY
        else: v2 = v + (new_t[j] - old_t[j])
        smp['output'] = add(v2, smp['output']); nch += 1
print("BS 動きの位置のキーを直した %d 本" % nch)

pr['attributes']['POSITION'] = add(P2, pr['attributes']['POSITION'], 34962)
pr['attributes']['NORMAL'] = add(N2, pr['attributes']['NORMAL'], 34962)
G['buffers'][0]['byteLength'] = len(bd)
js = json.dumps(G, separators=(',', ':')).encode('utf-8'); js += b' ' * ((4 - len(js) % 4) % 4)
bn = bytes(bd); bn += b'\x00' * ((4 - len(bn) % 4) % 4)
out = b'glTF' + struct.pack('<II', 2, 12 + 8 + len(js) + 8 + len(bn)) + struct.pack('<II', len(js), 0x4E4F534A) + js + struct.pack('<II', len(bn), 0x004E4942) + bn
open(DST, 'wb').write(out)
print("BS 書き出し", DST)
