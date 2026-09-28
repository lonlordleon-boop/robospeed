# -*- coding: utf-8 -*-
"""指定した頂点番号の重みを表示する（どの工程で変わったかを追うため）。"""
import bpy, sys
a=sys.argv[sys.argv.index("--")+1:]; SRC=a[0]; IDX=[int(x) for x in a[1].split(',')]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
for o in list(bpy.data.objects):
    if o.type=='MESH' and o.name.startswith("Icosphere"): bpy.data.objects.remove(o, do_unlink=True)
mesh=next(o for o in bpy.data.objects if o.type=='MESH')
vg={g.index:g.name for g in mesh.vertex_groups}
import os
for i in IDX:
    v=mesh.data.vertices[i]
    w={vg[g.group]:round(g.weight,3) for g in v.groups if g.weight>0.01}
    print("VW %-22s v%d 位置(%.3f,%.3f,%.3f) %s"%(os.path.basename(SRC),i,*(mesh.matrix_world@v.co),w))
