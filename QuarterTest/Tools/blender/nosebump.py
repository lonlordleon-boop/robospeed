# -*- coding: utf-8 -*-
"""のっぺらぼうの顔に、鼻の「形」（小さな盛り上がり）を作る。

   鼻の点を mouthpaste.py で貼っただけだと、色が付いただけで横から見ても光を当てても鼻が無い。
   新お嬢様は生成の時点で鼻が盛り上がっていた（顔の面から約1cm、半径約1cm）。
   芸術少女・わんぱく少女は生成で鼻の形が出ず、鼻のまわりの頂点も粗かった（5mm以内に頂点0個）。
   粗いまま持ち上げると角ばったピラミッドになるので、鼻のまわりの三角形だけを細かく割ってから持ち上げる。

   ・割るのは鼻の中心から「割る半径」以内の、顔の前を向いた三角形だけ。1回で1枚を4枚に割る。
     隣の三角形は、割られた辺に合わせて2〜4枚に割る（継ぎ目にすき間ができないように）。
     UV の継ぎ目で分かれている頂点は、位置が同じなら同じ辺として扱う。
   ・新しい頂点の UV・重み・法線は、辺の両端の平均。骨の重みは多い順に4本まで残す。
   ・盛り上げる向きは、鼻のまわりの顔の向き（法線の平均）。高さは中心で「高さ」、「半径」で 0。形は (1-t²)²。
   ・元の頂点や三角形のデータは消さずに残し、新しい並びを glb の後ろに足す。骨・動き・絵は触らない。
     Blender を通さないので timezero.py は要らない。

   座標は glTF（X 左右・Y 上・Z 前）。鼻の中心は、貼った鼻の点の中心より 3mm ほど下（新お嬢様がそうだった）。
   実行: python nosebump.py 入力.glb 出力.glb 中心x,y [高さ 0.010] [半径 0.012] [割る半径 0.022] [割る回数 2]
         （blender -b --factory-startup --python-expr から呼んでもよい）

   【手本の鼻を写す】4番目に glb を書くと、その glb の鼻の盛り上がりを形ごと写す。
   ・約1cmの丸い盛り上がりでは「イボ程度」だった。元気少女（v55）の鼻は高さ約2.8cm・裾の半径約3cmで、先がはっきり前へ出ている。
   ・手本の顔に3次の曲面を当て（鼻のまわり 3.5cm は除く）、そこから出ている量を鼻の形とする。
     手本の三角形の上で補間して、こちらの頂点へ「縮尺」倍して足す。縁（2.5〜3.5cm × 縮尺）で 0 へ弱める（口のくぼみまで写さないため）。
   ・元気少女の鼻の点は鼻のてっぺんにある（x0.0002, y0.7507）。こちらの中心も貼った鼻の点の中心にする。
   ・縮尺は顔の輪郭の幅の比（facewidth の値。芸術 0.382 ÷ 元気 0.355 ≒ 1.075）。
   ・【採用】手本は元気少女ではなくギャル少女（鼻先 0.004,0.8148、顔の幅 0.406 → 芸術・わんぱくは比 0.94）。
     中心は「鼻先」を渡す。鼻の色（鼻の下の影）の中心の約 8mm × 比 だけ上。
     例: ... -- gei_n.glb 出力.glb 0.0,0.879 gyaru.glb 0.004,0.8148 0.94 0.045 3 4 0.8
   実行: python nosebump.py 入力.glb 出力.glb 中心x,y 手本.glb 手本の中心x,y [縮尺 1.0] [割る半径 0.045] [割る回数 3] [ならす回数 4]"""
import json, struct, sys
import numpy as np

a = [x for x in sys.argv[1:]]
if '--' in a: a = a[a.index('--') + 1:]
SRC, DST = a[0], a[1]
CX, CY = [float(v) for v in a[2].split(',')]
COPY = len(a) > 3 and a[3].lower().endswith('.glb')
if COPY:
    TSRC = a[3]; TX, TY = [float(v) for v in a[4].split(',')]
    SCL = float(a[5]) if len(a) > 5 else 1.0
    RSUB = float(a[6]) if len(a) > 6 else 0.045
    LEV = int(a[7]) if len(a) > 7 else 3
    SMO = int(a[8]) if len(a) > 8 else 4       # 盛り上げ量をならす回数
    SOFT = float(a[9]) if len(a) > 9 else 0.6  # 法線を盛り上げる前の顔の向きへ寄せる割合（0＝本当の形どおり）
    # 法線の方式。base＝計算し直した顔の法線へ寄せる（芸術・わんぱく）
    # orig＝元の glb の法線を土台にして、形が変わった分の向きの変化だけを (1-SOFT) 倍して足す（新お嬢様）
    NMODE = a[10] if len(a) > 10 else 'base'

else:
    HGT = float(a[3]) if len(a) > 3 else 0.010
    RAD = float(a[4]) if len(a) > 4 else 0.012
    RSUB = float(a[5]) if len(a) > 5 else 0.022
    LEV = int(a[6]) if len(a) > 6 else 2

raw = open(SRC, 'rb').read(); off = 12; ck = []
while off < len(raw):
    ln, ty = struct.unpack_from('<II', raw, off); off += 8; ck.append((ty, off, ln)); off += ln
Jm = {t: (o, l) for t, o, l in ck}
G = json.loads(raw[Jm[0x4E4F534A][0]:Jm[0x4E4F534A][0] + Jm[0x4E4F534A][1]].decode('utf-8'))
BO, BL = Jm[0x004E4942]; bd = bytearray(raw[BO:BO + BL])
DT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NUM = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}

def rd(i):
    ac = G['accessors'][i]; bv = G['bufferViews'][ac['bufferView']]
    n = NUM[ac['type']]; dt = np.dtype(DT[ac['componentType']])
    b = bv.get('byteOffset', 0) + ac.get('byteOffset', 0); st = bv.get('byteStride') or n * dt.itemsize
    out = np.empty((ac['count'], n), dt)
    for k in range(n):
        out[:, k] = np.ndarray((ac['count'],), dt, bd, b + k * dt.itemsize, (st,))
    return out

def add(arr, like, target=None, ctype=None):
    """配列を glb の後ろに足して、新しいアクセサ番号を返す（型は元のアクセサに合わせる）"""
    global bd
    ac0 = dict(G['accessors'][like])
    if ctype: ac0['componentType'] = ctype
    arr = np.ascontiguousarray(arr.astype(DT[ac0['componentType']]))
    while len(bd) % 4: bd.append(0)
    bv = {'buffer': 0, 'byteOffset': len(bd), 'byteLength': arr.nbytes}
    if target: bv['target'] = target
    bd += arr.tobytes()
    G['bufferViews'].append(bv)
    ac = {'bufferView': len(G['bufferViews']) - 1, 'componentType': ac0['componentType'],
          'count': int(arr.shape[0]), 'type': ac0['type']}
    if ac0.get('normalized'): ac['normalized'] = True
    if 'min' in ac0:
        ac['min'] = arr.min(0).tolist() if arr.ndim > 1 else [int(arr.min())]
        ac['max'] = arr.max(0).tolist() if arr.ndim > 1 else [int(arr.max())]
    G['accessors'].append(ac)
    return len(G['accessors']) - 1

cands = [(G['accessors'][m['primitives'][0]['attributes']['POSITION']]['count'], i)
         for i, m in enumerate(G['meshes']) if 'JOINTS_0' in m['primitives'][0]['attributes']]
pr = G['meshes'][max(cands)[1]]['primitives'][0]
att = {k: rd(v) for k, v in pr['attributes'].items()}
tgts = [{k: rd(v) for k, v in t.items()} for t in pr.get('targets', [])]
tri = rd(pr['indices']).astype(np.int64).reshape(-1, 3)
P0 = att['POSITION'].astype(float)
nv0, nt0 = len(P0), len(tri)

# 重みを実数で扱う（正規化された整数なら 0〜1 に直す）
def wfloat(w, acc):
    ac = G['accessors'][acc]
    if ac['componentType'] == 5126: return w.astype(float)
    return w.astype(float) / float(np.iinfo(DT[ac['componentType']]).max)
def wback(w, acc):
    ac = G['accessors'][acc]
    if ac['componentType'] == 5126: return w
    mx = np.iinfo(DT[ac['componentType']]).max
    q = np.round(w * mx).astype(np.int64)
    q[:, 0] += mx - q.sum(1)          # 丸めで合計がずれた分は一番重い骨へ
    return q
WK = sorted(k for k in att if k.startswith('WEIGHTS_'))
JK = sorted(k for k in att if k.startswith('JOINTS_'))
W = np.concatenate([wfloat(att[k], pr['attributes'][k]) for k in WK], 1)
J = np.concatenate([att[k].astype(np.int64) for k in JK], 1)
other = [k for k in att if not k.startswith('WEIGHTS_') and not k.startswith('JOINTS_')]
A = {k: att[k].astype(float) for k in other}
T = [{k: t[k].astype(float) for k in t} for t in tgts]

def pkey(p): return tuple(np.round(p / 1e-5).astype(np.int64))

# 鼻のまわりの前を向いた頂点
d0 = np.hypot(P0[:, 0] - CX, P0[:, 1] - CY)
near = d0 < min(RSUB, 0.02)      # 広く取ると前髪を拾うので、中心の近くだけで前の面を決める
zc = P0[near, 2].max()
print("NB 鼻の中心 %.4f,%.4f  前の面 z %.4f" % (CX, CY, zc))

for lev in range(LEV):
    P = A['POSITION']
    cen = P[tri].mean(1)
    fn = np.cross(P[tri[:, 1]] - P[tri[:, 0]], P[tri[:, 2]] - P[tri[:, 0]])
    fn /= np.maximum(np.linalg.norm(fn, axis=1), 1e-12)[:, None]
    # 向きの条件（前を向いた三角形だけ）は付けない。生成の網目は鼻の位置で細長い三角形が集まっていて、
    # それが横や裏を向いているため割られずに残り、持ち上げると放射状のしわになった（芸術少女）
    sel = (np.hypot(cen[:, 0] - CX, cen[:, 1] - CY) < RSUB) & (cen[:, 2] > zc - 0.04)
    # 割る辺（位置で決める）
    split = set()
    for t in np.where(sel)[0]:
        for i in range(3):
            ka, kb = pkey(P[tri[t, i]]), pkey(P[tri[t, (i + 1) % 3]])
            split.add((min(ka, kb), max(ka, kb)))
    mid = {}          # 頂点番号の組 → 新しい頂点番号
    newv = []         # (a, b)
    def midv(i, j):
        k = (min(i, j), max(i, j))
        if k not in mid:
            mid[k] = len(A['POSITION']) + len(newv); newv.append(k)
        return mid[k]
    out = []
    for t in range(len(tri)):
        v = tri[t]
        e = []
        for i in range(3):
            ka, kb = pkey(P[v[i]]), pkey(P[v[(i + 1) % 3]])
            e.append((min(ka, kb), max(ka, kb)) in split)
        n = sum(e)
        if n == 0: out.append(v); continue
        m = [midv(v[i], v[(i + 1) % 3]) if e[i] else -1 for i in range(3)]
        if n == 3:
            out += [[v[0], m[0], m[2]], [m[0], v[1], m[1]], [m[2], m[1], v[2]], [m[0], m[1], m[2]]]
        elif n == 1:
            i = e.index(True); a0, b0, c0 = v[i], v[(i + 1) % 3], v[(i + 2) % 3]
            out += [[a0, m[i], c0], [m[i], b0, c0]]
        else:
            i = e.index(False)   # 割らない辺 v[i]→v[i+1]
            a0, b0, c0 = v[i], v[(i + 1) % 3], v[(i + 2) % 3]
            mb, mc = m[(i + 1) % 3], m[(i + 2) % 3]   # b0-c0 の中点, c0-a0 の中点
            out += [[a0, b0, mb], [a0, mb, mc], [mc, mb, c0]]
    tri = np.array(out, np.int64)
    if newv:
        ia = np.array([k[0] for k in newv]); ib = np.array([k[1] for k in newv])
        for k in A:
            nvv = (A[k][ia] + A[k][ib]) / 2
            if k == 'NORMAL': nvv /= np.maximum(np.linalg.norm(nvv, axis=1), 1e-12)[:, None]
            A[k] = np.concatenate([A[k], nvv])
        for t_ in T:
            for k in t_: t_[k] = np.concatenate([t_[k], (t_[k][ia] + t_[k][ib]) / 2])
        # 骨の重み：両端を半分ずつ足して、多い順に残す
        nj, nw = [], []
        for x, y in zip(ia, ib):
            acc = {}
            for jj, ww in zip(J[x], W[x]): acc[jj] = acc.get(jj, 0) + ww / 2
            for jj, ww in zip(J[y], W[y]): acc[jj] = acc.get(jj, 0) + ww / 2
            top = sorted(acc.items(), key=lambda q: -q[1])[:J.shape[1]]
            top += [(0, 0.0)] * (J.shape[1] - len(top))
            s = sum(q[1] for q in top) or 1.0
            nj.append([q[0] for q in top]); nw.append([q[1] / s for q in top])
        J = np.concatenate([J, np.array(nj, np.int64)]); W = np.concatenate([W, np.array(nw)])
    print("NB 割り %d 回目: 選んだ三角形 %d、足した頂点 %d → 三角形 %d" % (lev + 1, int(sel.sum()), len(newv), len(tri)))

P = A['POSITION']
# 盛り上げる向き：鼻のまわりの顔の法線の平均
d = np.hypot(P[:, 0] - CX, P[:, 1] - CY)
fr = (d < 0.015) & (P[:, 2] > zc - 0.04)
nrm = A['NORMAL'][fr].mean(0); nrm /= np.linalg.norm(nrm)
if not COPY:
    t = np.clip(d / RAD, 0, 1)
    h = np.where(fr | ((d < RAD) & (P[:, 2] > zc - 0.04)), HGT * (1 - t * t) ** 2, 0.0)
else:
    # 手本の glb を読む（同じ読み方）
    traw = open(TSRC, 'rb').read(); o_ = 12; tck = []
    while o_ < len(traw):
        l_, y_ = struct.unpack_from('<II', traw, o_); o_ += 8; tck.append((y_, o_, l_)); o_ += l_
    tJ = {t_: (o2, l2) for t_, o2, l2 in tck}
    TG = json.loads(traw[tJ[0x4E4F534A][0]:tJ[0x4E4F534A][0] + tJ[0x4E4F534A][1]].decode('utf-8'))
    tbd = traw[tJ[0x004E4942][0]:tJ[0x004E4942][0] + tJ[0x004E4942][1]]
    def trd(i):
        ac = TG['accessors'][i]; bv = TG['bufferViews'][ac['bufferView']]
        n = NUM[ac['type']]; dt = np.dtype(DT[ac['componentType']])
        b = bv.get('byteOffset', 0) + ac.get('byteOffset', 0); st = bv.get('byteStride') or n * dt.itemsize
        out = np.empty((ac['count'], n), dt)
        for k in range(n): out[:, k] = np.ndarray((ac['count'],), dt, tbd, b + k * dt.itemsize, (st,))
        return out
    tc = [(TG['accessors'][m['primitives'][0]['attributes']['POSITION']]['count'], i)
          for i, m in enumerate(TG['meshes']) if 'JOINTS_0' in m['primitives'][0]['attributes']]
    tpr = TG['meshes'][max(tc)[1]]['primitives'][0]
    TP = trd(tpr['attributes']['POSITION']).astype(float); TN = trd(tpr['attributes']['NORMAL']).astype(float)
    TT = trd(tpr['indices']).astype(np.int64).reshape(-1, 3)
    td = np.hypot(TP[:, 0] - TX, TP[:, 1] - TY)
    tzc = TP[td < 0.02, 2].max()
    tfront = (TN[:, 2] > 0.3) & (TP[:, 2] > tzc - 0.08)
    ring = tfront & (td > 0.035) & (td < 0.10)
    def Bs(x, y): return np.stack([x ** i * y ** j for i in range(4) for j in range(4 - i)], 1)
    X_, Y_, Z_ = TP[ring, 0] - TX, TP[ring, 1] - TY, TP[ring, 2]
    keep = np.ones(len(X_), bool)
    for it in range(4):       # 目や口の彫りは外れ値として除いて当て直す
        cf, *_ = np.linalg.lstsq(Bs(X_[keep], Y_[keep]), Z_[keep], rcond=None)
        r_ = Z_ - Bs(X_, Y_) @ cf; sd = np.std(r_[keep]); keep = np.abs(r_) < 2.0 * sd
    TR = TP[:, 2] - Bs(TP[:, 0] - TX, TP[:, 1] - TY) @ cf      # 手本の頂点ごとの「面から出ている量」
    # 手本の前を向いた三角形（鼻のまわり）
    tsel = tfront[TT].all(1) & (td[TT].min(1) < 0.045)
    TT2 = TT[tsel]
    ax, ay = TP[TT2[:, 0], 0] - TX, TP[TT2[:, 0], 1] - TY
    bx, by = TP[TT2[:, 1], 0] - TX, TP[TT2[:, 1], 1] - TY
    cx_, cy_ = TP[TT2[:, 2], 0] - TX, TP[TT2[:, 2], 1] - TY
    den = (by - cy_) * (ax - cx_) + (cx_ - bx) * (ay - cy_)
    den = np.where(np.abs(den) < 1e-14, 1e-14, den)
    def sample(qx, qy):
        """手本の鼻のまわりで (qx, qy)（鼻の中心から）の出ている量。前にある三角形のうち一番手前を使う"""
        l1 = ((by - cy_) * (qx - cx_) + (cx_ - bx) * (qy - cy_)) / den
        l2 = ((cy_ - ay) * (qx - cx_) + (ax - cx_) * (qy - cy_)) / den
        l3 = 1 - l1 - l2
        ins = (l1 >= -1e-6) & (l2 >= -1e-6) & (l3 >= -1e-6)
        if not ins.any(): return 0.0
        k = np.where(ins)[0]
        z = l1[k] * TP[TT2[k, 0], 2] + l2[k] * TP[TT2[k, 1], 2] + l3[k] * TP[TT2[k, 2], 2]
        j = k[np.argmax(z)]; w1, w2, w3 = l1[j], l2[j], l3[j]
        return w1 * TR[TT2[j, 0]] + w2 * TR[TT2[j, 1]] + w3 * TR[TT2[j, 2]]
    print("NB 手本 %s の鼻: 中心 %.4f,%.4f  高さ %.4f（曲面のばらつき %.4f）" % (TSRC.split('/')[-1], TX, TY, sample(0.0, 0.0), sd))
    # 手本の三角形の上で直線補間すると、手本の網目が粗い（ギャル少女は鼻が大きな三角形数枚）ため、
    # 辺の折れ目がそのまま写り、正面から光を当てると鼻から放射状のしわが出た。
    # 手本の頂点の「出ている量」を、なめらかな曲面（薄板スプライン）でつないで写す。
    # 使う頂点は前を向いたものだけ（鼻の裏側の頂点は正面から見ると重なるので外す）
    tk = np.round(TP / 1e-5).astype(np.int64)
    _, tfirst = np.unique(tk, axis=0, return_index=True)
    use = np.zeros(len(TP), bool); use[tfirst] = True
    use &= tfront & (td < 0.045) & (TN[:, 2] > 0.2)
    SX, SY, SR = TP[use, 0] - TX, TP[use, 1] - TY, TR[use]
    def U(r2): return np.where(r2 > 0, 0.5 * r2 * np.log(np.maximum(r2, 1e-30)), 0.0)
    nS = len(SX)
    K = U((SX[:, None] - SX[None, :]) ** 2 + (SY[:, None] - SY[None, :]) ** 2) + 1e-9 * np.eye(nS)
    Pm = np.stack([np.ones(nS), SX, SY], 1)
    M = np.zeros((nS + 3, nS + 3)); M[:nS, :nS] = K; M[:nS, nS:] = Pm; M[nS:, :nS] = Pm.T
    sol = np.linalg.lstsq(M, np.concatenate([SR, np.zeros(3)]), rcond=None)[0]
    wS, aS = sol[:nS], sol[nS:]
    def tps(qx, qy):
        r2 = (qx[:, None] - SX[None, :]) ** 2 + (qy[:, None] - SY[None, :]) ** 2
        return U(r2) @ wS + aS[0] + aS[1] * qx + aS[2] * qy
    print("NB 手本の頂点 %d 個をなめらかにつないだ。中心の高さ %.4f" % (nS, float(tps(np.zeros(1), np.zeros(1))[0])))
    # 元の顔は 1cm 以上の大きな平らな三角形で、法線だけでなめらかに見せていた。
    # 細かく割ると新しい頂点は平らな面の上に乗るので、面と面の折れ目が光でしわになって見えた。
    # 割った範囲の頂点を、まわりの元の頂点に当てた3次曲面の上へ乗せ直してから盛り上げる
    Pb = A['POSITION']
    Porig = Pb.copy()          # 乗せ直す前・盛り上げる前の形（orig 方式で使う）
    # 前の面の高さ zc は元の鼻の先で決まることがあるので、奥行きの幅は広めに取り、前を向いた頂点だけ使う（髪・耳を外す）
    N0 = att['NORMAL'].astype(float)
    fitp = (d0 < 0.09) & (P0[:, 2] > zc - 0.10) & (N0[:, 2] > 0.3)
    # もとから鼻の盛り上がりがある顔（新お嬢様）では、それに引っぱられて曲面が浮き、まわりに段差が出た。
    # 曲面から大きく外れた点（元の鼻など）を除いて当て直す
    fx, fy, fz = P0[fitp, 0] - CX, P0[fitp, 1] - CY, P0[fitp, 2]
    kf = np.ones(len(fx), bool)
    for it in range(5):
        cz, *_ = np.linalg.lstsq(Bs(fx[kf], fy[kf]), fz[kf], rcond=None)
        rf = fz - Bs(fx, fy) @ cz; sf = np.std(rf[kf]); kf = np.abs(rf) < 2.0 * sf
    print("NB 顔の曲面: 使った点 %d / %d、ばらつき %.4f" % (int(kf.sum()), len(fx), sf))
    zfit = Bs(Pb[:, 0] - CX, Pb[:, 1] - CY) @ cz
    wb = np.clip((RSUB * 1.1 - d) / (RSUB * 0.3), 0, 1); wb = wb * wb * (3 - 2 * wb)
    wb = np.where(Pb[:, 2] > zc - 0.05, wb, 0.0)
    print("NB 顔の面を曲面へ乗せ直した: 頂点 %d、動いた量 最大 %.4f" % (int((wb > 0).sum()), float(np.abs(wb * (zfit - Pb[:, 2])).max())))
    Pb[:, 2] = Pb[:, 2] + wb * (zfit - Pb[:, 2])
    # 盛り上げる向きは真正面（Z）。手本の「出ている量」も曲面から Z の向きに測っているので、それに合わせる。
    # 元の頂点の法線の平均だと、もとから小さな鼻がある顔（新お嬢様）では、その斜面につられて上を向いた（上向き 0.16）。
    # 曲面の傾きを使うと、鼻の高さでは顔の丸みでもっと上を向いた（0.42）
    nrm = np.array([0.0, 0.0, 1.0])
    P = Pb
    h = np.zeros(len(P))
    tgt = np.where((d < 0.035 * SCL) & (P[:, 2] > zc - 0.05))[0]
    ds = d[tgt] / SCL
    fall = np.clip((0.035 - ds) / 0.010, 0, 1); fall = fall * fall * (3 - 2 * fall)
    h[tgt] = tps((P[tgt, 0] - CX) / SCL, (P[tgt, 1] - CY) / SCL) * SCL * fall
    # 写したままだと、手本の網目の粗さと三角形の選び方で、正面から光を当てると鼻のまわりにしわが出た。
    # 盛り上げ量を、となりの頂点との平均で数回ならす（位置が同じ頂点はまとめる）。高さは元の最大に戻す
    hmax = h.max()
    keyh = np.round(P / 1e-5).astype(np.int64)
    _, gh = np.unique(keyh, axis=0, return_inverse=True); gh = gh.ravel()
    ng = gh.max() + 1
    hg = np.zeros(ng); np.maximum.at(hg, gh, h); hg2 = np.zeros(ng); np.minimum.at(hg2, gh, h)
    hg = np.where(np.abs(hg2) > np.abs(hg), hg2, hg)
    live = np.zeros(ng, bool); live[gh[tgt]] = True
    ea = np.concatenate([gh[tri[:, 0]], gh[tri[:, 1]], gh[tri[:, 2]]])
    eb = np.concatenate([gh[tri[:, 1]], gh[tri[:, 2]], gh[tri[:, 0]]])
    for it in range(SMO):
        sm = np.zeros(ng); cn = np.zeros(ng)
        np.add.at(sm, ea, hg[eb]); np.add.at(cn, ea, 1)
        np.add.at(sm, eb, hg[ea]); np.add.at(cn, eb, 1)
        avg = np.where(cn > 0, sm / np.maximum(cn, 1), hg)
        hg = np.where(live, 0.5 * hg + 0.5 * avg, hg)
    if hg.max() > 1e-9: hg *= hmax / hg.max()
    h = hg[gh] * (P[:, 2] > zc - 0.05)
    print("NB 盛り上げ量を %d 回ならした" % SMO)
P2 = P + h[:, None] * nrm[None, :]
print("NB 盛り上げ: 向き %s  動かした頂点 %d  最大 %.4f" % (np.round(nrm, 3).tolist(), int((h > 1e-6).sum()), h.max()))

# 法線を計算し直す（盛り上げたまわりだけ。同じ位置の頂点は同じ向き）
key = np.round(P2 / 1e-5).astype(np.int64)
_, grp = np.unique(key, axis=0, return_inverse=True); grp = grp.ravel()
fn = np.cross(P2[tri[:, 1]] - P2[tri[:, 0]], P2[tri[:, 2]] - P2[tri[:, 0]])
acc = np.zeros((grp.max() + 1, 3))
for k in range(3): np.add.at(acc, grp[tri[:, k]], fn)
ln_ = np.linalg.norm(acc, axis=1); ln_[ln_ < 1e-12] = 1
NN = acc[grp] / ln_[grp][:, None]
if COPY and SOFT > 0:
    # 本当の形どおりの法線だと、正面から光を当てたとき鼻のまわりに強い陰としわが出た。
    # ギャル少女は網目が粗く法線がなめらかなので、同じ高さの鼻でも正面からは控えめに見える
    # （法線を計算し直すとギャル少女にも陰が出た）。盛り上げる前の顔の法線へ SOFT の割合だけ寄せる
    fb = np.cross(P[tri[:, 1]] - P[tri[:, 0]], P[tri[:, 2]] - P[tri[:, 0]])
    ab = np.zeros((grp.max() + 1, 3))
    for k in range(3): np.add.at(ab, grp[tri[:, k]], fb)
    ab /= np.maximum(np.linalg.norm(ab, axis=1), 1e-12)[:, None]
    if NMODE == 'orig':
        # 新お嬢様の顔には、生成が彫った凹凸が形として残っていて、元の法線をならして隠してあった。
        # 法線を計算し直すと、その凹凸が鼻のまわりで段差やしわとして出た。
        # 元の法線に「元の形 → 仕上がりの形」で変わった向きの分だけを足す
        fo = np.cross(Porig[tri[:, 1]] - Porig[tri[:, 0]], Porig[tri[:, 2]] - Porig[tri[:, 0]])
        ao_ = np.zeros((grp.max() + 1, 3))
        for k in range(3): np.add.at(ao_, grp[tri[:, k]], fo)
        ao_ /= np.maximum(np.linalg.norm(ao_, axis=1), 1e-12)[:, None]
        NN = A['NORMAL'] + (1 - SOFT) * (NN - ao_[grp])
        NN /= np.maximum(np.linalg.norm(NN, axis=1), 1e-12)[:, None]
        print("NB 元の法線に、形の変化の分を %.0f%% 足した" % ((1 - SOFT) * 100))
    else:
        NN = (1 - SOFT) * NN + SOFT * ab[grp]
        NN /= np.maximum(np.linalg.norm(NN, axis=1), 1e-12)[:, None]
        print("NB 法線を盛り上げる前の顔の向きへ %.0f%% 寄せた" % (SOFT * 100))
redo = (d < RSUB * 1.3) & (P[:, 2] > zc - 0.05)
A['NORMAL'] = np.where(redo[:, None], NN, A['NORMAL'])
A['POSITION'] = P2
print("NB 法線を計算し直した頂点 %d" % int(redo.sum()))

# 新しい並びを書き足す
old = dict(pr['attributes'])
for k in other: pr['attributes'][k] = add(A[k], old[k], 34962)
col = 0
for k in JK:
    n = NUM[G['accessors'][old[k]]['type']]
    pr['attributes'][k] = add(J[:, col:col + n], old[k], 34962); col += n
col = 0
for k in WK:
    n = NUM[G['accessors'][old[k]]['type']]
    pr['attributes'][k] = add(wback(W[:, col:col + n], old[k]), old[k], 34962); col += n
if T:
    pr['targets'] = [{k: add(t_[k], tg[k], 34962) for k in t_} for t_, tg in zip(T, pr['targets'])]
idxacc = pr['indices']
pr['indices'] = add(tri.reshape(-1), idxacc, 34963, 5125 if len(A['POSITION']) > 65535 else None)
G['accessors'][pr['indices']].pop('min', None); G['accessors'][pr['indices']].pop('max', None)
G['buffers'][0]['byteLength'] = len(bd)
print("NB 頂点 %d → %d、三角形 %d → %d" % (nv0, len(A['POSITION']), nt0, len(tri)))

js = json.dumps(G, separators=(',', ':')).encode('utf-8'); js += b' ' * ((4 - len(js) % 4) % 4)
bn = bytes(bd); bn += b'\x00' * ((4 - len(bn) % 4) % 4)
out = b'glTF' + struct.pack('<II', 2, 12 + 8 + len(js) + 8 + len(bn)) + struct.pack('<II', len(js), 0x4E4F534A) + js + struct.pack('<II', len(bn), 0x004E4942) + bn
open(DST, 'wb').write(out)
print("NB 書き出し", DST)
