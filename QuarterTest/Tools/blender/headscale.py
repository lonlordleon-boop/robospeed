# -*- coding: utf-8 -*-
"""頭だけを大きく（小さく）する。首から下と骨・動きには触らない。
   頭の骨（Head と、その子の head_end・headfront）に付いた重みのぶんだけ、Head の根元を支点に頂点を拡大する。
   重みが半分の頂点（首とのつなぎ目）は半分だけ広がるので、首との境目に段はできない。
   Head の根元はほぼ「あご」の高さなので、あごはその場に残り、顔が上と横に広がる。

   使いどころ：生成したキャラの頭が、ほかの子より小さく出たとき（芸術少女・わんぱく少女で起きた）。
   preview も公園も「首の関節の高さ」で大きさをそろえて表示するので、全身を拡大しても見た目は変わらない。
   顔の大きさをそろえるには、頭と体の比そのものを変えるしかない。

   首の関節より下は広げない（首の関節から Head の根元にかけて徐々に効かせる）。
   Meshy の自動の骨入れは頭の重みを襟・肩まで伸ばしているので、重みだけで広げると肩が膨らむ。
   髪が首より下まで垂れているキャラには使わない（髪の先が広がらずに折れる）。

   倍率の決め方：顔の輪郭の幅（髪は入れない）を測って、ほかの子の平均との比を取る。
   測り方は scratchpad の facewidth.py（正面・平らな光で描き、髪と肌をキャラごとの色で分けて、肌の幅だけを取る）。

   glb の中身（頂点の座標）を直接書き換える。Blender で書き出し直さないので、骨・動き・絵はそのまま残る。
   実行: blender -b --factory-startup -P headscale.py -- 入力.glb 出力.glb 倍率 [起こす角度（度）]
   例:   ... -- wan_s2.glb wan_h.glb 1.64"""
import json, struct, sys
import numpy as np

a = sys.argv[sys.argv.index("--")+1:]
SRC, DST, F = a[0], a[1], float(a[2])
TILT = float(a[3]) if len(a) > 3 else 0.0     # 頭を起こす角度（度）。＋で顔が上を向く
# 【あご支点の方式】5番目に chin を渡すと、支点を「あごの一番下」に置き、あごより上を全部同じ倍率で広げる。
# 首の関節からあごの一番下までの間（首）でなじませる。頭か体かは、頭と首の重みの合計で決める（襟・肩は外れる）。
# 元の方式（Head の根元を支点、頭の重み 0.3 以上）では、あごの下の頂点が首と重みを分け合っていて広がらず、
# わんぱく少女の顎の下が横一直線に平らになり「削れて」見えた。
# 6番目は縦だけの倍率（頭が縦に長いとき 1 より小さく）。
MODE = a[4] if len(a) > 4 else ''
VY = float(a[5]) if len(a) > 5 else 1.0
HEADS = {'Head', 'head_end', 'headfront'}

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
    arr = np.array([struct.unpack_from('<'+f*n, bd, b+k*st) for k in range(ac['count'])], float)
    if ac.get('normalized'):
        arr = arr / {'B':255.0,'H':65535.0,'b':127.0,'h':32767.0}[f]
    return arr
def wr(i, arr):
    ac, n, f, b, st = lay(i)
    for k in range(ac['count']): struct.pack_into('<'+f*n, bd, b+k*st, *arr[k])

# 体のメッシュ＝頂点のいちばん多い、骨の付いたメッシュ
cands = []
for mi, m in enumerate(G['meshes']):
    pr = m['primitives'][0]
    if 'JOINTS_0' in pr['attributes']:
        cands.append((G['accessors'][pr['attributes']['POSITION']]['count'], mi))
mi = max(cands)[1]; pr = G['meshes'][mi]['primitives'][0]
skin = G['skins'][0]; joints = skin['joints']
names = [G['nodes'][j].get('name', '') for j in joints]
IBM = rd(skin['inverseBindMatrices'])
def bindpos(k):
    M = np.array(IBM[k]).reshape(4, 4).T       # 列優先
    return np.linalg.inv(M)[:3, 3]
kh = names.index('Head')
pivot = bindpos(kh)
hs = [k for k, n in enumerate(names) if n in HEADS]
P = rd(pr['attributes']['POSITION'])
J = rd(pr['attributes']['JOINTS_0']).astype(int)
W = rd(pr['attributes']['WEIGHTS_0'])
w = np.zeros(len(P))
for c in range(4):
    w += np.where(np.isin(J[:, c], hs), W[:, c], 0.0)
w = np.clip(w, 0, 1)
# 生成モデルの自動の骨入れは、頭の重みを首より下（襟・肩）まで薄く伸ばしていることがある。
# そのまま広げると肩まで膨らむので、首の関節から Head の根元にかけて徐々に効かせる（首より下は 0）。
# 髪が首より下まで垂れているキャラ（ロングヘア）では、髪の先が広がらずに折れるので使わないこと。
# また、頭の頂点の多くは首と重みを分け合っている（0.5〜0.99）。重みのまま広げると場所ごとに倍率が変わり顔がゆがむ。
# 重みで倍率を変えると、あご周り（首と重みを分け合う）だけ小さく広がり、顔が下を向いた（わんぱく少女で起きた）。
# なので重みは「頭かどうか」の判定だけに使い（0.3 以上なら頭）、倍率のなじませは高さだけで行う：
# 首の関節の高さで 0、Head の根元の高さで 1。あごは Head の根元より上にあるので、顔は上から下まで同じ倍率になる。
kn = names.index('neck'); ny = bindpos(kn)[1]
def smooth(x): x = np.clip(x, 0, 1); return x * x * (3 - 2 * x)
if MODE != 'chin':
    w = smooth((w - 0.1) / 0.2) * smooth((P[:, 1] - ny) / max(pivot[1] - ny, 1e-6))
    SC = np.array([1.0, 1.0, 1.0])
else:
    # 頭と首の重みの合計（襟・肩・胸の頂点は 0 に近い）
    hn = [k for k, n in enumerate(names) if n in HEADS or n == 'neck']
    whn = np.zeros(len(P))
    for c in range(4): whn += np.where(np.isin(J[:, c], hn), W[:, c], 0.0)
    # あごの一番下：顔の真ん中の縦の線で、高さごとの一番前を並べ、首の前から顔の前へ半分以上出た一番低い高さ。
    # 「頭の重みが多い一番低い点」にしたら、頭の重みが付いた首の前の頂点を拾い、首の関節より下になった
    mid = np.abs(P[:, 0]) < 0.02
    ys = np.arange(ny - 0.05, pivot[1] + 0.20, 0.002)
    prof = np.array([P[mid & (P[:, 1] >= y) & (P[:, 1] < y + 0.002), 2].max() if (mid & (P[:, 1] >= y) & (P[:, 1] < y + 0.002)).any() else np.nan for y in ys])
    neck_front = np.nanmedian(prof[(ys > ny - 0.02) & (ys < ny + 0.01)])
    face_front = np.nanmax(prof)
    ok = np.where(prof > neck_front + 0.5 * (face_front - neck_front))[0]
    chin_y = ys[ok[0]]
    print("HS 首の前 %.4f  顔の前 %.4f" % (neck_front, face_front))
    pivot = np.array([0.0, chin_y, pivot[2]])
    w = smooth((whn - 0.05) / 0.25) * smooth((P[:, 1] - ny) / max(chin_y - ny, 1e-6))
    SC = np.array([1.0, VY, 1.0])
    print("HS あご支点の方式：あごの一番下 y %.4f（首の関節 %.4f）  縦の倍率 %.3f" % (chin_y, ny, VY))
# 生成した頭がうつむいていることがある（わんぱく少女）。左右の軸まわりに回して起こす。
# glTF は Y が上・Z が前。X 軸まわりに θ 回すと前（+Z）が上（+Y）へ行くのは θ が負のとき
D = (P - pivot) * (1.0 + (F * SC[None, :] - 1.0) * w[:, None])
th = -np.radians(TILT) * w
cy, sy = np.cos(th), np.sin(th)
y2 = D[:, 1] * cy - D[:, 2] * sy
z2 = D[:, 1] * sy + D[:, 2] * cy
D[:, 1], D[:, 2] = y2, z2
P2 = pivot + D
wr(pr['attributes']['POSITION'], P2)
if MODE == 'chin' and 'NORMAL' in pr['attributes']:
    # 法線も同じように回す（縦だけの倍率のぶんは逆に掛ける）。元の方式は法線を回していなかった
    Nn = rd(pr['attributes']['NORMAL'])
    Nn = Nn / (1.0 + (SC[None, :] - 1.0) * w[:, None])
    ny2 = Nn[:, 1] * cy - Nn[:, 2] * sy; nz2 = Nn[:, 1] * sy + Nn[:, 2] * cy
    Nn[:, 1], Nn[:, 2] = ny2, nz2
    Nn /= np.maximum(np.linalg.norm(Nn, axis=1, keepdims=True), 1e-12)
    wr(pr['attributes']['NORMAL'], Nn)
ac = G['accessors'][pr['attributes']['POSITION']]
ac['min'] = P2.min(0).tolist(); ac['max'] = P2.max(0).tolist()
print("HS 支点（Head の根元）%s  倍率 %.3f  起こす角度 %.1f 度" % (np.round(pivot, 4), F, TILT))
print("HS 頭の頂点 %d（重み1） ／ つなぎ目 %d（重み0〜1） ／ 触らない %d"
      % ((w > 0.999).sum(), ((w > 0.001) & (w <= 0.999)).sum(), (w <= 0.001).sum()))
print("HS 高さ（Y）%.3f → %.3f" % (P[:, 1].max() - P[:, 1].min(), P2[:, 1].max() - P2[:, 1].min()))

js = json.dumps(G, separators=(',',':')).encode('utf-8'); js += b' '*((4-len(js)%4)%4)
bn = bytes(bd); bn += b'\x00'*((4-len(bn)%4)%4)
out = b'glTF'+struct.pack('<II',2,12+8+len(js)+8+len(bn))+struct.pack('<II',len(js),0x4E4F534A)+js+struct.pack('<II',len(bn),0x004E4942)+bn
open(DST,'wb').write(out)
print("HS 書き出し", DST)
