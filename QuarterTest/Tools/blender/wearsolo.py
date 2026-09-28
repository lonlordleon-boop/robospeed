# -*- coding: utf-8 -*-
"""単体で作った部品（服・靴・カツラ）を素体に着せる。

   wearpart.py との違いは「切らない」こと。
   wearpart.py は灰色マネキンに着せた三面図から作った部品を受け取るので、灰色の面を探して消し、
   消したあとに残る小さな穴を塞ぎ、縁のギザギザをならし、素体に埋まった面を消す、という後始末が要る。
   その後始末が、掌と肘のゴミ・股の穴・靴の内壁欠けを作っていた。

   こちらは部品だけを描いた三面図から作った部品を受け取る。面はひとつも消さない。
   やることは三つだけ。大きさと位置を合わせる、素体から重みを写す、素体と同じファイルに入れる。

   大きさの合わせ方は「素体が服の中に収まる最小の倍率」。
   上端（＝肩の線）を素体の肩の高さに置いたうえで、高さ1cmごとの帯で素体と部品の横幅・奥行きを比べ、
   どの帯でも部品のほうが広くなる倍率を探す。これを数回くり返して落ち着かせる。
   袖の先から先までを素体の肩幅に合わせると、袖は肩より外へ出ているぶん小さくなりすぎて、
   服が体の中に潜ってしまった。だから幅一点ではなく、全部の帯で比べる。
   すき間（既定4%）を持たせるので、素体の面と服の面が同じ深さに並ぶことがなくなり、
   描画がちらついて透けて見える現象も起きない。
   細かい調整は dressup.html のスライダーで行い、その値を「手動の大きさ」「ずらし」で焼き込む。

   種類は cloth（服）・hair（髪）・shoes（靴）の三つ。dressup.html がこの名前で部品を拾う。合わせ方がそれぞれ違う。
   服は肩に吊るし、髪は頭にかぶせ、靴は足を包む。

   靴は「片足ぶんだけ」を受け取る。左足に合わせてから x を反転して右足ぶんを作り、
   ひとつのメッシュにまとめる。左右を別々に生成すると形が微妙に食い違うので、
   反転して作るほうが揃うし、生成も一回で済む。
   合わせる高さには足首の骨（既定 LeftFoot）を渡す。そこから下が「足」。

   実行: blender -b --factory-startup -P wearsolo.py --
         素体.glb 部品.glb 出力.glb 種類 名前
         [合わせる高さ（骨の名前か world z の数値）既定 LeftShoulder、靴は LeftFoot]
         [すき間の割合 既定1.04] [手動の大きさ 既定1.0] [ずらし x,y,z（m）既定0,0,0]
         [左右別のずらし Lx,Ly,Lz;Rx,Ry,Rz] [裾の高さ world z 既定なし] [袖を腕へ回す幅 m 既定0.04、0で回さない]

   「裾の高さ」を書くと、上端を合わせる高さに置いたまま、下端がそこに来るように縦だけ縮める。
   三面図の服が素体より縦長のときに使う。書かなければ縦横おなじ倍率のまま。
   例:   ... -- es3.glb cloth.glb out.glb cloth 元気少女 LeftShoulder 1.04 1.0 0,0,0
         ... -- es3.glb shoe.glb out.glb shoes 元気少女 LeftFoot 1.06
"""
import bpy, sys, os, math
import numpy as np
from mathutils import Vector, kdtree

a = sys.argv[sys.argv.index("--")+1:]
BASE, PART, OUT, KIND, NAME = a[0], a[1], a[2], a[3], a[4]
# 合わせる高さ。骨の名前か、world z の数値。服と髪は肩、靴は足首を既定にする
ANCHOR = a[5] if len(a) > 5 else ('LeftFoot' if a[3] == 'shoes' else 'LeftShoulder')
EXTRA  = float(a[6]) if len(a) > 6 else 1.04      # 素体との間に持たせるすき間の割合
MANUAL = float(a[7]) if len(a) > 7 else 1.0       # スライダー「大きさ」
DXYZ   = [float(v) for v in a[8].split(',')] if len(a) > 8 else [0.0, 0.0, 0.0]
# 左右で別々にずらす（靴を片足ずつ合わせるとき）。x>0 が左足、x<0 が右足
SIDE   = [[float(v) for v in g.split(',')] for g in a[9].split(';')] if len(a) > 9 and a[9] else None
HEM    = float(a[10]) if len(a) > 10 and a[10] else None    # 裾を持ってきたい高さ（world z）。縦だけ縮める。"" なら使わない
# 袖を腕の向きへ回すときの、効き始めてから全開になるまでの幅（m）。0 を渡すと回さない
SLEEVE = float(a[11]) if len(a) > 11 else 0.04
# 股を素体よりどれだけ下に置くか（m）。素体の下着の裾のギザギザを隠すために少し下げる
CROFF = float(a[12]) if len(a) > 12 else 0.015

bpy.ops.wm.read_factory_settings(use_empty=True)

# ---- 素体 ----
bpy.ops.import_scene.gltf(filepath=BASE)
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
# 2回目以降の着せ替えでは素体のほかに部品のメッシュもあるので、名前が body のものを優先する
body = next((o for o in bpy.data.objects if o.type == 'MESH' and o.name == 'body'), None) \
       or next(o for o in bpy.data.objects if o.type == 'MESH')
body.name = "body"
if arm.animation_data: arm.animation_data.action = None
bpy.context.view_layer.update()

BP = np.array([tuple(body.matrix_world @ v.co) for v in body.data.vertices])
print("BS 素体 頂点 %d  高さ %.3f 〜 %.3f" % (len(BP), BP[:,2].min(), BP[:,2].max()))

# 合わせる高さを決める
try:
    ZFIT = float(ANCHOR)
except ValueError:
    b = arm.data.bones.get(ANCHOR)
    if b is None:
        print("BS 骨 %s が無い。骨の一覧: %s" % (ANCHOR, [x.name for x in arm.data.bones]))
        sys.exit(1)
    ZFIT = (arm.matrix_world @ b.head_local).z
print("BS 合わせる高さ z %.4f（%s）" % (ZFIT, ANCHOR))

def split_z(P, zlo, zhi):
    """脚が二つに分かれている所と、一つにつながっている所の境目（股）の高さを返す。
       下から高さ5mmずつ見ていき、その断面の x を並べて一番大きいすき間を探す。
       すき間が幅の15%より大きく、しかも真ん中をまたいでいれば「脚が二本」。
       すき間が消えた高さが股。見つからなければ None。"""
    z = zlo; last = None
    while z < zhi:
        q = P[(P[:,2] >= z) & (P[:,2] < z+0.005)]
        if len(q) >= 20:
            xs = np.sort(q[:,0]); w = xs[-1] - xs[0]
            d = np.diff(xs)
            i = int(np.argmax(d)) if len(d) else -1
            two = (i >= 0 and w > 1e-6 and d[i] > 0.15*w
                   and xs[i] < (xs[0]+xs[-1])/2 < xs[i+1])
            if two: last = z
            elif last is not None: return z
        z += 0.005
    return None

def band_width(P, zlo, zhi):
    """その高さの帯にある点の、横幅と中心を返す"""
    q = P[(P[:,2] >= zlo) & (P[:,2] < zhi)]
    if len(q) < 10: return None, None
    c = np.array([(q[:,0].max()+q[:,0].min())/2, (q[:,1].max()+q[:,1].min())/2, (zlo+zhi)/2])
    return q[:,0].max() - q[:,0].min(), c

def band_depth(P, zlo, zhi):
    """その高さの帯にある点の、前後の厚み（y）を返す。
       ズボンは腰の高さに合わせるが、A字の姿勢では手が腰のすぐ横にあり、
       横幅で測ると手まで入って腰が2倍近くに見える。厚みなら手が入っても変わらない"""
    q = P[(P[:,2] >= zlo) & (P[:,2] < zhi)]
    if len(q) < 10: return None
    return q[:,1].max() - q[:,1].min()

wb, cb = band_width(BP, ZFIT - 0.015, ZFIT + 0.015)
if wb is None:
    print("BS 合わせる高さに素体の頂点が無い"); sys.exit(1)
print("BS 素体 その高さの幅 %.4f  中心 (%.3f, %.3f, %.3f)" % (wb, *cb))
# 素体の股の高さ。下半分だけを見る（腕や手は真ん中をまたがないので邪魔しない）
BCROTCH = split_z(BP, BP[:,2].min(), BP[:,2].min() + 0.5*(BP[:,2].max()-BP[:,2].min()))
print("BS 素体の股の高さ %s" % ("%.4f" % BCROTCH if BCROTCH is not None else "見つからない"))

# ---- 部品 ----
before = set(o.name for o in bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=PART)
new = [o for o in bpy.data.objects if o.name not in before]
for o in list(new):
    if o.type == 'MESH' and o.name.startswith("Icosphere"):
        bpy.data.objects.remove(o, do_unlink=True); new.remove(o)
part = next(o for o in new if o.type == 'MESH')
part.name = KIND + "_" + NAME
# 親の変換を焼き込んで、単独のオブジェクトにする
for o in bpy.data.objects: o.select_set(False)
part.select_set(True); bpy.context.view_layer.objects.active = part
part.parent = None
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
mesh = part.data

PP = np.array([tuple(part.matrix_world @ v.co) for v in mesh.vertices])
pz0, pz1 = PP[:,2].min(), PP[:,2].max()
# 部品の一番上の帯（上から15%）。服ならここが肩の線
wp, cp = band_width(PP, pz1 - 0.15*(pz1-pz0), pz1)
if wp is None or wp <= 0:
    print("BS 部品の上の帯が測れない"); sys.exit(1)
print("BS 部品 頂点 %d  高さ %.3f 〜 %.3f  上の帯の幅 %.4f  中心 (%.3f, %.3f, %.3f)"
      % (len(PP), pz0, pz1, wp, *cp))

# 髪（カツラ）は合わせ方が違う。服は肩に吊るすが、髪は頭にかぶせる。
# 上端を素体の頭のてっぺんに合わせ、左右前後は頭の一番広い帯の中心に合わせる。
# 大きさは「頭が髪の中に収まる最小の倍率」。比べるのは頭の高さの帯だけ。
HAIR = (KIND == 'hair')
HTOP = BP[:,2].max()

# 靴も合わせ方が違う。足を包むので、上端でも一番広い帯でもなく、足そのものの大きさで決める。
# 受け取るのは片足ぶん。左足に合わせてから反転して右足ぶんを作る。
SHOE = (KIND == 'shoes')
FOOT = None

def rot_z(P, deg):
    """z のまわりに回す。部品の外接箱の中心を軸にする"""
    t = math.radians(deg); c, s = math.cos(t), math.sin(t)
    R = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])
    o = (P.min(0) + P.max(0)) / 2
    return (P - o) @ R.T + o

if SHOE:
    # 生成された靴の向きをそろえる。
    # 生成器は靴をどちらへ向けて出すか決まっていない。この靴は長い向きが x に出てきた。
    # 足は前後（y）に長いので、まず長い向きを y に合わせる。
    # 次につま先の向き。靴下の立ち上がり（上から25%の塊）はかかと側に寄っているので、
    # その塊が前（-y）にあれば前後がさかさま。180度回してかかとを後ろへ向ける。
    # 高さで見分けようとしたが、つま先側とかかと側の上端が 0.734 と 0.738 でほぼ同じで使えなかった。
    sz = PP.max(0) - PP.min(0)
    if sz[0] > sz[1]:
        PP = rot_z(PP, 90)
        print("BS 靴の長い向きが x だったので、90度回して y へそろえた")
    zt_, zb_ = PP[:,2].max(), PP[:,2].min()
    top = PP[PP[:,2] > zt_ - 0.25*(zt_-zb_)]
    ymid = (PP[:,1].min() + PP[:,1].max()) / 2
    if len(top) and top[:,1].mean() < ymid:
        PP = rot_z(PP, 180)
        print("BS 靴下の立ち上がりが前にあったので、180度回してかかとを後ろへ向けた")
    else:
        print("BS つま先は前を向いている")

    # 足＝合わせる高さ（足首）より下にある素体の点。x>0 が左足
    fl = BP[(BP[:,2] <= ZFIT) & (BP[:,0] > 0)]
    if len(fl) < 20:
        print("BS 足首より下に素体の点が %d 個しか無い。合わせる高さを見直すこと" % len(fl))
        sys.exit(1)
    FOOT = (fl.min(0), fl.max(0))
    print("BS 左足 点 %d  x %.3f〜%.3f  y %.3f〜%.3f  z %.3f〜%.3f"
          % (len(fl), FOOT[0][0], FOOT[1][0], FOOT[0][1], FOOT[1][1], FOOT[0][2], FOOT[1][2]))

def widest(P, zlo, zhi):
    """その高さの範囲で、横幅が一番広い帯の幅と中心を返す。
       カツラは「こめかみの線」がいちばん確かな手がかりになる。
       外接箱で合わせると、リボンやポニーテールの張り出しに引きずられて大きくなりすぎた。"""
    best = (0.0, None)
    z = zlo
    while z < zhi:
        w, c = band_width(P, z, z + 0.02)
        if w is not None and w > best[0]: best = (w, c)
        z += 0.01
    return best

if HAIR:
    wh, ch = widest(BP, ZFIT, HTOP)
    if ch is None: wh, ch = wb, cb
    print("BS 素体の頭 てっぺん z %.4f  一番広い帯の幅 %.4f  中心 (%.3f, %.3f, %.3f)" % (HTOP, wh, *ch))

def place_uniform(k):
    """倍率 k で拡大縮小し、素体に合わせる位置へ持っていった座標を返す。
       実際のメッシュはまだ動かさない（何度も試すため）"""
    Q = PP * k
    zt = Q[:,2].max(); zb = Q[:,2].min()
    if HAIR:
        # 髪の一番広い帯（こめかみの線）を、素体の頭の一番広い帯へ重ねる
        _, c = widest(Q, zb, zt)
        return Q if c is None else Q + (ch - c)
    _, c = band_width(Q, zt - 0.15*(zt-zb), zt)
    return Q + (cb - c)

def place(k):
    """place_uniform のあと、裾の高さが指定されていれば縦を作り直す。
       倍率を決める繰り返しでは使わない。縦を変えると太さの比べ方まで動いて、
       倍率が必要以上に大きくなった（服がぶかぶかになった）"""
    Q = place_uniform(k)
    if HEM is not None:
        zt = Q[:,2].max(); zb = Q[:,2].min()
        Q = Q.copy()
        gc = split_z(Q, zb, zb + 0.7*(zt-zb))
        if gc is not None and BCROTCH is not None and zb < gc < zt and HEM < BCROTCH < zt:
            # 上端（肩）・股・裾の三点で合わせる。あいだは比例。
            # 一律に縮めると股の縫い目が上がって、股が開いたまま残る
            # 股は素体より 1.5cm 下に置く。ちょうどに合わせると、内股の縫い目の際に
            # 素体の下着が数枚だけ顔を出した
            Q[:,2] = np.interp(Q[:,2], [zb, gc, zt], [HEM, BCROTCH - CROFF, zt])
        else:
            Q[:,2] = zt - (zt - Q[:,2]) * ((zt - HEM) / (zt - zb))
    return Q

def need(Q):
    """素体の胴に対して部品がどれだけ足りないかを返す。高さ1cmの帯ごとに前後の厚み（y）を比べ、
       その比の中央値を取る。

       横幅（x）は使わない。A字の姿勢では手が体の一番外側まで張り出していて、
       短パンの高さでも素体の幅が体の全幅になる。それに合わせると服が3倍以上になった。
       前後の厚みなら、腕があってもほとんど変わらないので胴の太さをそのまま表す。

       見るのは合わせる高さ（服なら肩）より下の全部。頭は襟から出るものなので比べない。
       まとめ方は上から9割の値。中央値だと、胴に合わせたぶん腰で足りなくなり、
       素体の下着が短パンを突き抜けた。一番大きい値だと端の一点に引きずられる。"""
    if HAIR:
        # 髪は頭の高さの帯だけを見る。横幅と前後の厚みの両方で、頭が中に収まるかを測る。
        # 前髪や毛先は頭より下へ垂れるが、そこは比べない（首や肩と比べても意味がない）
        z0, z1 = ZFIT + 0.10*(HTOP-ZFIT), min(Q[:,2].max(), HTOP)
    else:
        z1 = min(Q[:,2].max(), ZFIT)
        z0 = Q[:,2].min()
    rs = []
    for z in np.arange(z0, z1, 0.01):
        q = Q[(Q[:,2] >= z) & (Q[:,2] < z+0.01)]
        b = BP[(BP[:,2] >= z) & (BP[:,2] < z+0.01)]
        if len(q) < 20 or len(b) < 20: continue
        if HAIR:
            for ax in (0, 1):
                gw = q[:,ax].max() - q[:,ax].min(); bw = b[:,ax].max() - b[:,ax].min()
                if gw > 1e-6: rs.append(bw / gw)
            continue
        gd = q[:,1].max() - q[:,1].min(); bd = b[:,1].max() - b[:,1].min()
        if gd > 1e-6: rs.append(bd / gd)
    if not rs: return 1.0
    r = float(np.percentile(rs, 90))
    print("BS   比べた帯 %d 本、厚みの比 上から9割 %.3f（中央値 %.3f 最大 %.3f）"
          % (len(rs), r, float(np.median(rs)), max(rs)))
    return r

def place_shoe():
    """足が靴の中に収まる最小の倍率で拡大縮小し、左足の位置へ置いた座標を返す。

       決め手は「足の長さ」だけにする。靴という物は、長さが決まれば幅も高さも決まる形をしている。
       三方向の比のうち一番大きいものを採る、という服と同じやり方を最初に試したが、
       部品の縦横比が足と少しでも違うと、一番きつい向きに引きずられて別の向きが破綻した。
       仮の靴で試したとき、19.5cm の足に対して 37.5cm の靴が出来た。

       長さで合わせたあと足が横や上へはみ出すぶんは、sinkbody.py の引っ込めモーフで沈める。
       部品を削るのではなく素体を引っ込める、という服の股と同じ考え方。
       ただし、はみ出しが 25% を超えるほど形が食い違っている場合だけは、
       沈めきれないので、その向きに合わせて靴ごと大きくする。

       靴底は床（素体の最下点）に合わせ、前後左右は足の中心に合わせる。"""
    flo, fhi = FOOT
    fsz = fhi - flo
    psz = PP.max(0) - PP.min(0)
    print("BS 足 %.3f x %.3f x %.3f ／ 靴 %.3f x %.3f x %.3f" % (*fsz, *psz))
    kk = float(fsz[1] / psz[1])                      # 長さ（前後）で合わせる
    over = max(fsz[0] / psz[0], fsz[2] / psz[2]) / kk  # そのとき横と高さがどれだけ足りないか
    if over > 1.25:
        print("BS 靴の縦横比が足と %.0f%% 食い違う。長さではなく、きつい向きに合わせる" % ((over-1)*100))
        kk *= over
    else:
        print("BS 長さで合わせる。横と高さのはみ出しは %.0f%%、モーフで沈める" % (max(over-1, 0)*100))
    kk *= EXTRA
    print("BS 倍率 %.4f（すき間 %.2f 込み）" % (kk, EXTRA))
    QQ = PP * kk
    c = (QQ.min(0) + QQ.max(0)) / 2
    fc = (flo + fhi) / 2
    QQ[:, 0] += fc[0] - c[0]
    QQ[:, 1] += fc[1] - c[1]
    QQ[:, 2] += BP[:, 2].min() - QQ[:, 2].min()   # 靴底を床へ
    return QQ

def widen_sock(Q):
    """靴下が脚に入るように、高さごとに横へ広げる。

       生成された靴下はまっすぐな細い筒だが、この子のふくらはぎは太い。
       測ったら、床から7.7cm の高さで脚が113mm、靴下が91mm しかなかった。
       そのまま着せると sinkbody が脚を筒の中へ引っぱり、足首が裂けてトゲだらけになった。

       最初は入らない高さで切り落としたが、それだと靴下が丸ごと無くなってしまう。
       だから切らずに広げる。実物の靴下も脚に合わせて伸びるので、そのほうが素直。

       広げる量は上へ行くほど増える一方にする（上へ行くほど脚が太いため）。
       急に広がると段が付くので、前後の帯で均す。広げる中心は、その高さの筒の中心。"""
    zb_, zt_ = Q[:,2].min(), Q[:,2].max()
    edges = np.arange(zb_, zt_ + 0.01, 0.01)
    fs, cxs, cys = [], [], []
    for z in edges:
        b = BP[(BP[:,2] >= z) & (BP[:,2] < z+0.01) & (BP[:,0] > 0)]
        s = Q[(Q[:,2] >= z) & (Q[:,2] < z+0.01)]
        f = 1.0
        if len(s) >= 5:
            cxs.append((s[:,0].min()+s[:,0].max())/2); cys.append((s[:,1].min()+s[:,1].max())/2)
            if len(b) >= 5 and z > ZFIT:
                sx = s[:,0].max()-s[:,0].min(); sy = s[:,1].max()-s[:,1].min()
                bx = b[:,0].max()-b[:,0].min(); by = b[:,1].max()-b[:,1].min()
                if sx > 1e-6: f = max(f, bx*EXTRA/sx)
                if sy > 1e-6: f = max(f, by*EXTRA/sy)
        else:
            cxs.append(np.nan); cys.append(np.nan)
        fs.append(f)
    fs = np.maximum.accumulate(np.array(fs))          # 上へ行くほど広く
    pad = np.pad(fs, (1, 1), mode='edge')
    fs = np.convolve(pad, np.ones(3)/3.0, mode='valid')
    if fs.max() > 1.8:
        print("BS 靴下を %.2f 倍も広げないと入らない。広げすぎるので 1.8 倍で頭打ちにする" % fs.max())
        fs = np.minimum(fs, 1.8)
    if fs.max() <= 1.001:
        print("BS 靴下は脚に入っている。広げない")
        return Q
    print("BS 靴下を広げる: 一番広げる所で %.2f 倍（高さ z %.3f）"
          % (fs.max(), edges[int(np.argmax(fs))]))
    cxs, cys = np.array(cxs), np.array(cys)
    ok = ~np.isnan(cxs)
    cxs = np.interp(edges, edges[ok], cxs[ok]); cys = np.interp(edges, edges[ok], cys[ok])
    fz  = np.interp(Q[:,2], edges, fs)
    cxz = np.interp(Q[:,2], edges, cxs); cyz = np.interp(Q[:,2], edges, cys)
    R = Q.copy()
    R[:,0] = cxz + (Q[:,0] - cxz) * fz
    R[:,1] = cyz + (Q[:,1] - cyz) * fz
    return R

if SHOE:
    Q = widen_sock(place_shoe())
else:
    if HAIR:
        wpm, _ = widest(PP, PP[:,2].min(), PP[:,2].max())
        k = float(wh / wpm) if wpm > 1e-6 else 1.0
        print("BS 部品の一番広い帯の幅 %.4f → 倍率の出発点 %.4f" % (wpm, k))
    elif KIND == 'pants':
        # ズボンは腰の帯の厚みで出発点を決める（横幅だと手が混ざる。band_depth の説明）
        db = band_depth(BP, ZFIT - 0.015, ZFIT + 0.015)
        dp = band_depth(PP, pz1 - 0.15*(pz1-pz0), pz1)
        k = float(db / dp) if (db and dp and dp > 1e-6) else float(wb / wp)
        print("BS ズボン: 腰の厚み 素体 %.4f ／ 部品 %.4f → 倍率の出発点 %.4f" % (db or 0, dp or 0, k))
    else:
        k = float(wb / wp)
    for it in range(6):
        Q = place_uniform(k)
        r = need(Q)
        print("BS 合わせ %d回目: 倍率 %.4f  はみ出し %.3f" % (it+1, k, r))
        if r <= 1.001: break
        k *= r
    k *= EXTRA
    print("BS 自動の倍率 %.4f（すき間 %.2f 込み）" % (k, EXTRA))

    # 決まった倍率で実際に動かす（place と同じ計算をメッシュに焼く）
    Q = place(k)
PMI = part.matrix_world.inverted()
for i, v in enumerate(mesh.vertices): v.co = PMI @ Vector(tuple(Q[i]))
print("BS 置いた: 高さ %.3f 〜 %.3f  幅 %.3f  厚み %.3f"
      % (Q[:,2].min(), Q[:,2].max(), Q[:,0].max()-Q[:,0].min(), Q[:,1].max()-Q[:,1].min()))

# 靴は、ここまでで左足ぶんが出来ている。x を反転した写しを作って右足ぶんにし、ひとつにまとめる。
# 素体の足は x=0 について左右対称なので、反転するだけで反対の足にぴったり乗る。
# x を反転すると面の表裏がひっくり返るので、法線を戻しておく。忘れると靴が内側から見える
if SHOE:
    other = part.copy()
    other.data = mesh.copy()
    bpy.context.collection.objects.link(other)
    for v in other.data.vertices: v.co.x = -v.co.x
    other.data.flip_normals()
    for o in bpy.data.objects: o.select_set(False)
    part.select_set(True); other.select_set(True)
    bpy.context.view_layer.objects.active = part
    bpy.ops.object.join()
    mesh = part.data
    XS = [v.co.x for v in mesh.vertices]
    print("BS 反転して両足ぶんにした: 頂点 %d  x %.3f 〜 %.3f" % (len(mesh.vertices), min(XS), max(XS)))

    # 靴下の丈を、脚が入るところまで詰める。
    # 生成された靴下はまっすぐな筒だが、この子のふくらはぎは上へ行くほど太い。
    # 測ったら、床から5.7cm より上では脚のほうが8〜23mm 太かった。
    # そのまま着せると sinkbody が脚を筒の中へ引っぱり、足首が裂けてトゲだらけになった。
    # だから高さ1cmごとに脚と筒の幅を比べ、脚が入らなくなる手前で切り落とす。
    # 元の絵の靴下ももともと短いので、design も崩れない。
    # 蓋だけ外して筒を開ける手も試したが、原因は蓋ではなく太さだったので効かなかった。
    PW = np.array([tuple(v.co) for v in mesh.vertices])
    zb_, zt_ = PW[:,2].min(), PW[:,2].max()
    lastgood, bad, cut = zt_, 0, None
    z = zb_
    while z < zt_:
        b = BP[(BP[:,2] >= z) & (BP[:,2] < z+0.01) & (BP[:,0] > 0)]
        s = PW[(PW[:,2] >= z) & (PW[:,2] < z+0.01) & (PW[:,0] > 0)]
        if len(b) >= 5 and len(s) >= 5 and z > ZFIT:
            ox = (b[:,0].max()-b[:,0].min()) - (s[:,0].max()-s[:,0].min())
            oy = (b[:,1].max()-b[:,1].min()) - (s[:,1].max()-s[:,1].min())
            if max(ox, oy) > 0.003:      # 3mm を超えてはみ出したら「入らない」
                bad += 1
                if bad >= 2:             # 2段つづいたら、そこで確定
                    cut = lastgood + 0.01
                    break
            else:
                bad = 0; lastgood = z
        z += 0.01
    if cut is not None and cut < zt_:
        import bmesh
        bm = bmesh.new(); bm.from_mesh(mesh)
        kill = [f for f in bm.faces if sum(v.co.z for v in f.verts) / len(f.verts) > cut]
        bmesh.ops.delete(bm, geom=kill, context='FACES')
        bm.to_mesh(mesh); bm.free()
        print("BS 靴下が脚に入らなくなる高さ z %.3f で切った（%d 面を落とし、丈は %.1f cm）"
              % (cut, len(kill), (cut - zb_) * 100))
    else:
        print("BS 靴下は脚に入っている。切らない")

# スライダーで決めた手動の大きさとずらし。dressup.html と同じく、部品の外接箱の中心を基準に
# 拡大縮小してから、ずらす
if SIDE:
    # 左右別。x>0 を左足、x<0 を右足として、その側だけの外接箱の中心を基準にする
    for nm, sgn, d in (("左足", 1, SIDE[0]), ("右足", -1, SIDE[1] if len(SIDE) > 1 else SIDE[0])):
        idx = [v.index for v in mesh.vertices if (v.co.x > 0) == (sgn > 0)]
        if not idx: continue
        KP = np.array([tuple(mesh.vertices[vi].co) for vi in idx])
        c0 = (KP.min(0) + KP.max(0)) / 2
        for vi in idx:
            p = np.array(mesh.vertices[vi].co)
            mesh.vertices[vi].co = tuple(c0 + MANUAL * (p - c0) + np.array(d))
        print("BS 手動 %s: 大きさ %.2f（中心 %.3f, %.3f, %.3f）  ずらし (%.3f, %.3f, %.3f)" % (nm, MANUAL, *c0, *d))
elif MANUAL != 1.0 or any(DXYZ):
    KP = np.array([tuple(v.co) for v in mesh.vertices])
    c0 = (KP.min(0) + KP.max(0)) / 2
    for v in mesh.vertices:
        p = np.array(v.co); v.co = tuple(c0 + MANUAL * (p - c0) + np.array(DXYZ))
    print("BS 手動: 大きさ %.2f（中心 %.3f, %.3f, %.3f）  ずらし (%.3f, %.3f, %.3f)" % (MANUAL, *c0, *DXYZ))

# 袖を腕の向きへ回す。
# 三面図の服は袖を横に広げた形で描かれていることが多い。素体は A字の姿勢で腕が斜め下を向いているので、
# そのまま着せると腕が袖の横腹を突き破って出る。後ろから見ると肩の位置がずれて見えるのはこれ。
# 肩の関節を中心に、袖だけを腕の向きまで回す。肩から離れるほど強く回し、胴は動かさない。
if SLEEVE and KIND == 'cloth':      # 袖があるのは服だけ。髪や靴に掛けると形が壊れる
    from mathutils import Matrix
    for bname, sgn, nm in (('LeftArm', 1, '左袖'), ('RightArm', -1, '右袖')):
        b = arm.data.bones.get(bname)
        if b is None: continue
        S = arm.matrix_world @ b.head_local
        adir = (arm.matrix_world @ b.tail_local - S).normalized()
        # 袖の先＝その側で一番外の3%の点の重心
        side = [v for v in mesh.vertices if (v.co.x > 0) == (sgn > 0)]
        if not side: continue
        xs = [abs((part.matrix_world @ v.co).x) for v in side]
        xm = max(xs); xn = min(xs)
        tip = [part.matrix_world @ v.co for v in side if abs((part.matrix_world @ v.co).x) >= xm - 0.03*(xm-xn)]
        if len(tip) < 10: continue
        T = sum(tip, Vector()) / len(tip)
        sdir = (T - S).normalized()
        ang = sdir.angle(adir)
        axis = sdir.cross(adir)
        if axis.length < 1e-6 or ang < 1e-3:
            print("BS %s: 回す必要なし" % nm); continue
        axis.normalize()
        print("BS %s: 袖 (%.2f, %.2f, %.2f) を腕 (%.2f, %.2f, %.2f) へ %.1f度 回す"
              % (nm, *sdir, *adir, ang*180/3.14159265))
        for v in side:
            p = part.matrix_world @ v.co
            # 肩より内側は動かさない。そこから SLEEVE m のあいだでなめらかに効かせる
            # 袖の高さにあるものだけ。x だけで選ぶと、腰まわり（短パン）まで回ってしまう
            if p.z < S.z - 0.10: continue
            t = (abs(p.x) - abs(S.x)) / SLEEVE
            t = 0.0 if t <= 0 else (1.0 if t >= 1 else t*t*(3-2*t))
            if t <= 0: continue
            q = Matrix.Rotation(ang*t, 4, axis) @ (p - S) + S
            v.co = part.matrix_world.inverted() @ q

# 材質の名前を「種類:名前」にする（dressup.html がこれで拾う）
for m in mesh.materials:
    if m: m.name = "%s:%s" % (KIND, NAME)

# 髪は頭の骨ひとつに全部くくる。
# 素体から重みを写すと、生え際の近くが肩や背骨に引っぱられて、歩くたびに髪が揺れて崩れる。
# 髪は頭と一緒に動けばよいので、これでよい。
if HAIR:
    vg = part.vertex_groups.new(name='Head')
    vg.add([v.index for v in mesh.vertices], 1.0, 'REPLACE')
    print("BS 髪は Head の骨ひとつに結んだ: 頂点 %d" % len(mesh.vertices))
    for o in bpy.data.objects: o.select_set(False)
    part.select_set(True); arm.select_set(True); bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type='ARMATURE_NAME')
    bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB',
                              export_animations=True, export_skins=True, export_yup=True,
                              export_morph=True)
    print("BS 書き出し", OUT, os.path.getsize(OUT))
    sys.exit(0)

# 素体の近い頂点（4点）の重みを距離で加重平均して写す。服は体と同じ骨で曲がる
bpos = [body.matrix_world @ v.co for v in body.data.vertices]
kd = kdtree.KDTree(len(bpos))
for i, p in enumerate(bpos): kd.insert(p, i)
kd.balance()
names = [g.name for g in body.vertex_groups]
vgs = {n: part.vertex_groups.new(name=n) for n in names}
far = 0
for v in mesh.vertices:
    hits = kd.find_n(v.co, 8)
    if hits and hits[0][2] > 0.05: far += 1
    # 一番近い点から 1cm より遠いものは捨てる。
    # A字の姿勢では手が腰のすぐ横にあるので、腰の服に手の重みが混じり、
    # 走りで腕を振ると腰の布がそこだけ引っぱられて、辺が15倍に伸びた。
    if hits:
        lim = hits[0][2] + 0.01
        hits = [h for h in hits if h[2] <= lim][:4]
    acc = {}; tot = 0.0
    for co, i, d in hits:
        w = 1.0 / (d + 1e-4); tot += w
        for g in body.data.vertices[i].groups:
            acc[g.group] = acc.get(g.group, 0.0) + w * g.weight
    for gi_, val in acc.items():
        if val / tot > 1e-3: vgs[names[gi_]].add([v.index], val / tot, 'REPLACE')
print("BS 重みを素体から写した: 頂点 %d、骨 %d（素体から5cm以上離れていた頂点 %d）"
      % (len(mesh.vertices), len(names), far))

for o in bpy.data.objects: o.select_set(False)
part.select_set(True); arm.select_set(True); bpy.context.view_layer.objects.active = arm
bpy.ops.object.parent_set(type='ARMATURE_NAME')

bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB',
                          export_animations=True, export_skins=True, export_yup=True)
print("BS 書き出し", OUT, os.path.getsize(OUT))
