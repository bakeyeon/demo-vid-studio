"""
Demo Vid Studio: Blender scene builder (runs inside Blender, no API key needed).

Renders a style-matched 3D stage for the demo video:
  background  one 1920x1080 PNG of a soft 3D set, shapes kept to the edges so the
              device and the feature card can sit on top of it
  intro/outro a short PNG sequence with the project title in extruded 3D text

Usage (studio_cli.py calls this for you):
  blender -b --factory-startup -P blender_scene.py -- --kind background --style clay3d --out bg.png
  blender -b --factory-startup -P blender_scene.py -- --kind intro --style cyberpunk \
      --title "AlphaEvolve" --subtitle "Evolve code" --seconds 3 --out frames/intro_####.png
"""

import argparse
import math
import random
import sys

import bpy

STYLES = {
    # bg/world, floor, shape palette, roughness, metallic, emission strength (0 = none), outline
    "ambient": dict(world=(0.93, 0.90, 0.98), floor=(0.95, 0.93, 0.99),
                    palette=[(0.78, 0.70, 0.98), (1.00, 0.78, 0.70), (0.66, 0.92, 0.86), (0.98, 0.86, 0.95)],
                    text=(0.36, 0.30, 0.62), rough=0.35, metal=0.0, emit=0.0, outline=False, count=16),
    "minimal": dict(world=(0.06, 0.07, 0.09), floor=(0.09, 0.10, 0.12),
                    palette=[(0.55, 0.57, 0.62), (0.32, 0.34, 0.38), (0.80, 0.81, 0.84)],
                    text=(0.92, 0.93, 0.95), rough=0.25, metal=0.6, emit=0.0, outline=False, count=8),
    "cartoon": dict(world=(1.00, 0.93, 0.55), floor=(1.00, 0.96, 0.75),
                    palette=[(0.98, 0.30, 0.30), (0.20, 0.55, 0.98), (0.20, 0.80, 0.45), (1.00, 0.62, 0.10)],
                    text=(0.98, 0.30, 0.30), rough=0.6, metal=0.0, emit=0.0, outline=True, count=14),
    "storybook": dict(world=(0.96, 0.91, 0.80), floor=(0.94, 0.88, 0.76),
                      palette=[(0.80, 0.55, 0.42), (0.55, 0.66, 0.50), (0.90, 0.75, 0.52), (0.62, 0.55, 0.72)],
                      text=(0.45, 0.28, 0.20), rough=0.85, metal=0.0, emit=0.0, outline=False, count=14),
    "clay3d": dict(world=(0.95, 0.88, 0.80), floor=(0.96, 0.90, 0.83),
                   palette=[(1.00, 0.45, 0.38), (0.35, 0.62, 1.00), (0.40, 0.82, 0.50), (1.00, 0.75, 0.25), (0.70, 0.52, 1.00)],
                   text=(0.42, 0.25, 0.85), rough=0.9, metal=0.0, emit=0.0, outline=False, count=18),
    "cyberpunk": dict(world=(0.01, 0.01, 0.03), floor=(0.02, 0.02, 0.05),
                      palette=[(0.00, 0.95, 1.00), (1.00, 0.10, 0.85), (0.55, 0.20, 1.00)],
                      text=(0.00, 0.95, 1.00), rough=0.3, metal=0.4, emit=1.2, outline=False, count=12),
}


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=["background", "intro", "outro"], default="background")
    ap.add_argument("--style", choices=sorted(STYLES), default="clay3d")
    ap.add_argument("--out", required=True, help="PNG path (background) or frame pattern with #### (intro/outro)")
    ap.add_argument("--title", default="")
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--seconds", type=float, default=3.0)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--samples", type=int, default=32)
    return ap.parse_args(argv)


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return bpy.context.scene


def pick_engine(scene):
    engines = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    for name in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "CYCLES"):
        if name in engines:
            scene.render.engine = name
            return name
    return scene.render.engine


def material(name, color, rough, metal, emit=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if emit > 0:
        key = "Emission Color" if "Emission Color" in bsdf.inputs else "Emission"
        bsdf.inputs[key].default_value = (*color, 1)
        bsdf.inputs["Emission Strength"].default_value = emit
    return m


def outline(obj, thickness=0.035):
    """Inverted-hull black outline for the cartoon style."""
    mat = bpy.data.materials.new("outline")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0, 0, 0, 1)
    bsdf.inputs["Roughness"].default_value = 1
    if hasattr(mat, "use_backface_culling"):
        mat.use_backface_culling = True
    obj.data.materials.append(mat)
    mod = obj.modifiers.new("outline", "SOLIDIFY")
    mod.thickness = thickness
    mod.offset = 1
    mod.use_flip_normals = True
    mod.material_offset = len(obj.data.materials) - 1


def smooth(obj):
    for p in obj.data.polygons:
        p.use_smooth = True


def add_shape(kind, loc, size, mat, rot):
    if kind == "sphere":
        bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=size, location=loc)
    elif kind == "torus":
        bpy.ops.mesh.primitive_torus_add(major_radius=size, minor_radius=size * 0.38, location=loc, rotation=rot)
    elif kind == "cylinder":
        bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=size * 0.8, depth=size * 1.2, location=loc, rotation=rot)
    elif kind == "cone":
        bpy.ops.mesh.primitive_cone_add(vertices=48, radius1=size, depth=size * 1.6, location=loc, rotation=rot)
    else:
        bpy.ops.mesh.primitive_cube_add(size=size * 1.5, location=loc, rotation=rot)
    obj = bpy.context.active_object
    if kind in ("cube", "cylinder", "cone"):
        bev = obj.modifiers.new("soft", "BEVEL")
        bev.width = size * 0.22
        bev.segments = 6
    smooth(obj)
    obj.data.materials.append(mat)
    return obj


def build_set(scene, st, rng, keep_center=True, title_zone=False):
    world = bpy.data.worlds.new("world")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (*st["world"], 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.5 if st["emit"] == 0 else 0.6

    # Cyclorama: a floor that curves up into a back wall, so there is no horizon line.
    import bmesh
    mesh = bpy.data.meshes.new("cyclorama")
    cyc = bpy.data.objects.new("cyclorama", mesh)
    scene.collection.objects.link(cyc)
    bm = bmesh.new()
    verts = []
    W = 60
    for i in range(41):  # profile from front floor (y=-12) curving up to the back wall (z=20)
        t = i / 40
        if t < 0.55:
            y, z = -12 + (t / 0.55) * 18, 0.0
        else:
            a = (t - 0.55) / 0.45 * (math.pi / 2)
            y, z = 6 + math.sin(a) * 6, (1 - math.cos(a)) * 6 + (t - 0.55) / 0.45 * 14
        verts.append((bm.verts.new((-W / 2, y, z)), bm.verts.new((W / 2, y, z))))
    for a, b in zip(verts, verts[1:]):
        bm.faces.new((a[0], a[1], b[1], b[0]))
    bm.to_mesh(mesh)
    bm.free()
    smooth(cyc)
    if st["emit"] > 0:  # cyberpunk: dark floor with a glowing grid
        cyc.data.materials.append(material("floor", st["floor"], 0.4, 0.2))
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=48, y_subdivisions=48, size=60, location=(0, -3, 0.02))
        grid = bpy.context.active_object
        wf = grid.modifiers.new("wire", "WIREFRAME")
        wf.thickness = 0.04
        grid.data.materials.append(material("grid", st["palette"][1], 0.5, 0.0, emit=2.0))
    else:
        cyc.data.materials.append(material("floor", st["floor"], 0.95, 0.0))

    mats = [material(f"c{i}", c, st["rough"], st["metal"], st["emit"]) for i, c in enumerate(st["palette"])]
    kinds = ["sphere", "cube", "torus", "cylinder", "cone", "sphere"]
    shapes, placed = [], []
    for i in range(st["count"]):
        size = rng.uniform(0.9, 1.9)
        floating = i % 3 == 2
        loc = None
        for _ in range(200):
            x = rng.uniform(-17, 17)
            y = rng.uniform(-6, 5)
            z = rng.uniform(4.5, 9.5) if floating else size * 0.9
            # keep the middle of the frame clear for the device and the card
            if keep_center and abs(x) < 10.5:
                continue
            # intro/outro: nothing floats behind or in front of the title
            if title_zone and floating and abs(x) < 9:
                continue
            if title_zone and not floating and y > -1 and abs(x) < 7:
                continue
            if any((x - a) ** 2 + (y - b) ** 2 + (z - c) ** 2 < (size + r + 0.4) ** 2 for a, b, c, r in placed):
                continue
            loc = (x, y, z)
            break
        if loc is None:
            continue
        placed.append((*loc, size))
        rot = (rng.uniform(0, math.pi), rng.uniform(0, math.pi), rng.uniform(0, math.pi))
        obj = add_shape(rng.choice(kinds), loc, size, mats[i % len(mats)], rot)
        if st["outline"]:
            outline(obj)
        shapes.append(obj)
    return shapes


def lights_and_camera(scene, st, width, height):
    bpy.ops.object.light_add(type="AREA", location=(-6, -8, 12))
    key = bpy.context.active_object
    key.data.energy = 1400 if st["emit"] == 0 else 300
    key.data.size = 12
    key.rotation_euler = (math.radians(40), 0, math.radians(-30))
    bpy.ops.object.light_add(type="AREA", location=(8, -6, 8))
    fill = bpy.context.active_object
    fill.data.energy = 350 if st["emit"] == 0 else 120
    fill.data.size = 10
    fill.rotation_euler = (math.radians(55), 0, math.radians(45))

    bpy.ops.object.camera_add(location=(0, -30, 7.5), rotation=(math.radians(82), 0, 0))
    cam = bpy.context.active_object
    cam.data.lens = 40 if width >= height else 26
    scene.camera = cam
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    return cam


def add_text(body, size, loc, color, st, extrude=0.25):
    bpy.ops.object.text_add(location=loc, rotation=(math.radians(90), 0, 0))
    t = bpy.context.active_object
    t.data.body = body
    t.data.size = size
    t.data.extrude = extrude
    t.data.bevel_depth = extrude * 0.35
    t.data.bevel_resolution = 4
    t.data.align_x = "CENTER"
    t.data.align_y = "CENTER"
    t.data.materials.append(material("text", color, max(0.3, st["rough"] - 0.2), st["metal"], st["emit"] * 0.8))
    return t


def animate_intro(scene, st, args, shapes):
    fps = args.fps
    end = max(2, int(round(args.seconds * fps)))
    scene.render.fps = fps
    scene.frame_start, scene.frame_end = 1, end
    title = add_text(args.title or "Demo", 2.9, (0, 0, 6.2), st["text"], st, extrude=0.45)
    sub = add_text(args.subtitle, 1.0, (0, 0, 3.9), st["palette"][0], st, extrude=0.12) if args.subtitle else None

    # Title swings in and settles; subtitle rises after it.
    fly = int(end * 0.45)
    if args.kind == "outro":
        title.keyframe_insert("rotation_euler", frame=1)
        title.keyframe_insert("scale", frame=1)
        title.rotation_euler[2] = math.radians(-25)
        title.scale = (0.85, 0.85, 0.85)
        title.keyframe_insert("rotation_euler", frame=end)
        title.keyframe_insert("scale", frame=end)
    else:
        title.rotation_euler[2] = math.radians(-70)
        title.scale = (0.2, 0.2, 0.2)
        title.keyframe_insert("rotation_euler", frame=1)
        title.keyframe_insert("scale", frame=1)
        title.rotation_euler[2] = 0
        title.scale = (1, 1, 1)
        title.keyframe_insert("rotation_euler", frame=fly)
        title.keyframe_insert("scale", frame=fly)
    if sub:
        z = sub.location[2]
        sub.location[2] = z - 1.5
        sub.scale = (0.01, 0.01, 0.01)
        sub.keyframe_insert("location", frame=max(1, fly - 6))
        sub.keyframe_insert("scale", frame=max(1, fly - 6))
        sub.location[2] = z
        sub.scale = (1, 1, 1)
        sub.keyframe_insert("location", frame=min(end, fly + 10))
        sub.keyframe_insert("scale", frame=min(end, fly + 10))

    # Gentle bob on the props.
    for k, obj in enumerate(shapes):
        z0 = obj.location[2]
        for f in range(1, end + 1, max(1, fps // 3)):
            obj.location[2] = z0 + 0.25 * math.sin((f / fps) * 2.4 + k)
            obj.rotation_euler[2] += 0.04
            obj.keyframe_insert("location", frame=f)
            obj.keyframe_insert("rotation_euler", frame=f)


def main():
    args = parse_args()
    st = STYLES[args.style]
    scene = reset_scene()
    engine = pick_engine(scene)
    if engine == "CYCLES":
        scene.cycles.samples = args.samples
    elif hasattr(scene, "eevee") and hasattr(scene.eevee, "taa_render_samples"):
        scene.eevee.taa_render_samples = args.samples
    rng = random.Random(args.seed)
    shapes = build_set(scene, st, rng, keep_center=(args.kind == "background"), title_zone=(args.kind != "background"))
    lights_and_camera(scene, st, args.width, args.height)
    transforms = [i.identifier for i in scene.view_settings.bl_rna.properties["view_transform"].enum_items]
    if args.style == "cartoon":
        scene.view_settings.view_transform = "Standard"
    else:
        # Standard keeps pastel clay colours clean; AgX tames the neon glow
        scene.view_settings.view_transform = ("AgX" if "AgX" in transforms else "Filmic") if st["emit"] > 0 else "Standard"
        looks = [i.identifier for i in scene.view_settings.bl_rna.properties["look"].enum_items]
        punchy = next((l for l in looks if "Punchy" in l), None)
        if punchy:
            scene.view_settings.look = punchy
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.filepath = args.out

    if args.kind == "background":
        bpy.ops.render.render(write_still=True)
    else:
        animate_intro(scene, st, args, shapes)
        bpy.ops.render.render(animation=True)
    print(f"[blender_scene] engine={engine} kind={args.kind} style={args.style} out={args.out}")


if __name__ == "__main__":
    main()
