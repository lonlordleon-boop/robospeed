import bpy, sys
a = sys.argv[sys.argv.index("--")+1:]
bpy.ops.wm.open_mainfile(filepath=a[0])
print("OBJ_COUNT", len(bpy.data.objects))
for o in sorted(bpy.data.objects, key=lambda x: x.name):
    d = o.dimensions
    print("OBJ %-22s type=%-8s loc=(%.2f,%.2f,%.2f) dim=(%.2f,%.2f,%.2f) scale=(%.3f,%.3f,%.3f) parent=%s hide=%s"
          % (o.name, o.type, o.location[0], o.location[1], o.location[2],
             d[0], d[1], d[2], o.scale[0], o.scale[1], o.scale[2],
             o.parent.name if o.parent else "-", o.hide_viewport))
cam = bpy.data.objects.get("cam")
if cam: print("CAM loc=(%.2f,%.2f,%.2f) ortho=%.2f" % (cam.location[0],cam.location[1],cam.location[2], cam.data.ortho_scale))
