# -*- coding: utf-8 -*-
"""
Meshy の 3d_rigging が返した GLB（別リグ＋クリップ1本）から、クリップだけを
うちのモデルの GLB へ移し替えて追加する。

  実行: blender -b --factory-startup --python retarget.py -- うちの.glb 元.glb 追加する名前 出力.glb

移し替えの式（前回と同じ）:
  回転:  newQ = restQ_target * inv(restQ_source) * animQ_source   （骨ごとのローカル）
  移動:  Hips だけ。 t_new = t_target_rest + (t_source - t_source_rest) * (脚の長さの比)
骨は名前で対応させる。対応の取れない骨は捨てて報告する。
"""
import json, struct, sys, os
import numpy as np

a = sys.argv[sys.argv.index("--")+1:]
TGT, SRC, NAME, OUT = a[0], a[1], a[2], a[3]

COMP={5120:('b',1),5121:('B',1),5122:('h',2),5123:('H',2),5125:('I',4),5126:('f',4)}
NUM={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}

def load(path):
    raw=open(path,'rb').read(); off=12; ck=[]
    while off<len(raw):
        ln,ty=struct.unpack_from('<II',raw,off); off+=8; ck.append((ty,off,ln)); off+=ln
    Jm={t:(o,l) for t,o,l in ck}
    G=json.loads(raw[Jm[0x4E4F534A][0]:Jm[0x4E4F534A][0]+Jm[0x4E4F534A][1]].decode('utf-8'))
    BO,BL=Jm[0x004E4942]; bd=bytearray(raw[BO:BO+BL])
    return G, bd

def reader(G, bd):
    def rd(i):
        ac=G['accessors'][i]; n=NUM[ac['type']]; f,s=COMP[ac['componentType']]
        bv=G['bufferViews'][ac['bufferView']]
        b=bv.get('byteOffset',0)+ac.get('byteOffset',0); st=bv.get('byteStride') or n*s
        o=np.zeros((ac['count'],n))
        for k in range(ac['count']): o[k]=struct.unpack_from('<'+f*n,bd,b+k*st)
        return o
    return rd

def q2m(q):
    x,y,z,w=q
    return np.array([1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w),2*(x*y+z*w),1-2*(x*x+z*z),
                     2*(y*z-x*w),2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]).reshape(3,3)
def qmul(a,b):
    ax,ay,az,aw=a; bx,by,bz,bw=b
    return np.array([aw*bx+ax*bw+ay*bz-az*by, aw*by-ax*bz+ay*bw+az*bx,
                     aw*bz+ax*by-ay*bx+az*bw, aw*bw-ax*bx-ay*by-az*bz])
def qconj(q): return np.array([-q[0],-q[1],-q[2],q[3]])

def rig(G):
    nodes=G['nodes']; parent={}
    for i,nd in enumerate(nodes):
        for c in nd.get('children',[]): parent[c]=i
    n2i={nd.get('name',''):i for i,nd in enumerate(nodes)}
    def wd(i):
        ch=[]; j=i
        while j is not None: ch.append(j); j=parent.get(j)
        M=np.eye(4)
        for j in reversed(ch):
            nd=nodes[j]; L=np.eye(4)
            L[:3,:3]=q2m(np.array(nd.get('rotation',[0,0,0,1]),float))@np.diag(np.array(nd.get('scale',[1,1,1]),float))
            L[:3,3]=np.array(nd.get('translation',[0,0,0]),float); M=M@L
        return M
    return nodes, parent, n2i, wd

GT, BT = load(TGT); GS, BS = load(SRC)
rdT = reader(GT, BT); rdS = reader(GS, BS)
nT, pT, iT, wdT = rig(GT); nS, pS, iS, wdS = rig(GS)
print("SRC_ANIMS", [x.get('name') for x in GS.get('animations',[])])
if not GS.get('animations'):
    print("NO_ANIMATION"); sys.exit(0)
an = GS['animations'][0]

# 脚の長さの比（腰→足首）
def leglen(wd, n2i):
    if 'Hips' in n2i and 'LeftFoot' in n2i:
        return np.linalg.norm(wd(n2i['Hips'])[:3,3]-wd(n2i['LeftFoot'])[:3,3])
    return 1.0
ratio = leglen(wdT, iT) / max(1e-6, leglen(wdS, iS))
print("LEG_RATIO %.4f" % ratio)

# 追加するデータをターゲットの BIN の末尾に足す
def add_accessor(arr, ctype='VEC3', comp=5126, is_time=False):
    global BT
    while len(BT)%4: BT.append(0)
    off=len(BT)
    n=NUM[ctype]
    for row in arr:
        BT += struct.pack('<'+'f'*n, *([row] if n==1 else list(row)))
    bv={'buffer':0,'byteOffset':off,'byteLength':len(BT)-off}
    GT['bufferViews'].append(bv)
    acc={'bufferView':len(GT['bufferViews'])-1,'componentType':comp,'count':len(arr),'type':ctype}
    if is_time:
        acc['min']=[float(min(arr))]; acc['max']=[float(max(arr))]
    GT['accessors'].append(acc)
    return len(GT['accessors'])-1

samplers=[]; channels=[]; matched=[]; skipped=[]
for chn in an['channels']:
    tg=chn['target']; ni=tg.get('node')
    if ni is None: continue
    name=nS[ni].get('name','')
    if name not in iT: skipped.append(name+':'+tg['path']); continue
    smp=an['samplers'][chn['sampler']]
    times=rdS(smp['input'])[:,0]; vals=rdS(smp['output'])
    interp=smp.get('interpolation','LINEAR')
    if interp=='CUBICSPLINE': vals=vals[1::3]; interp='LINEAR'
    ti=iT[name]
    if tg['path']=='rotation':
        rT=np.array(nT[ti].get('rotation',[0,0,0,1]),float)
        rS=np.array(nS[ni].get('rotation',[0,0,0,1]),float)
        fix=qmul(rT, qconj(rS))
        out=np.array([qmul(fix,v)/np.linalg.norm(qmul(fix,v)) for v in vals])
        ctype='VEC4'
    elif tg['path']=='translation':
        if name!='Hips': skipped.append(name+':translation(骨の長さが違うので捨てる)'); continue
        tT=np.array(nT[ti].get('translation',[0,0,0]),float)
        tS=np.array(nS[ni].get('translation',[0,0,0]),float)
        out=np.array([tT+(v-tS)*ratio for v in vals]); ctype='VEC3'
    elif tg['path']=='scale':
        skipped.append(name+':scale'); continue
    else:
        continue
    ai=add_accessor(list(times),'SCALAR',is_time=True); ao=add_accessor(out,ctype)
    samplers.append({'input':ai,'output':ao,'interpolation':interp})
    channels.append({'sampler':len(samplers)-1,'target':{'node':ti,'path':tg['path']}})
    matched.append(name)

GT.setdefault('animations',[]).append({'name':NAME,'samplers':samplers,'channels':channels})
GT['buffers'][0]['byteLength']=len(BT)

js=json.dumps(GT,separators=(',',':')).encode('utf-8'); js+=b' '*((4-len(js)%4)%4)
bn=bytes(BT); bn+=b'\x00'*((4-len(bn)%4)%4)
out=b'glTF'+struct.pack('<II',2,12+8+len(js)+8+len(bn))
out+=struct.pack('<II',len(js),0x4E4F534A)+js+struct.pack('<II',len(bn),0x004E4942)+bn
open(OUT,'wb').write(out)
print("MATCHED", len(set(matched)), "骨 /", "SKIPPED", skipped[:8], ("...+%d"%(len(skipped)-8) if len(skipped)>8 else ""))
print("ADDED", NAME, "→", OUT, os.path.getsize(OUT))
