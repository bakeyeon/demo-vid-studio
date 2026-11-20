"""
Demo Vid Studio: Blender 3D Isometric Maker Lab & Film Studio Scene Builder (runs inside Blender, no API key needed).

Renders a style-matched 3D Isometric Prototype Maker Lab & Film Studio stage for the demo video:
  background  one PNG (1920x1080 or 1080x1080) of a warm isometric studio backdrop with festive props
              and soft bokeh / framing so the device and feature card sit cleanly on top of it
  intro/outro a short PNG animation sequence of the full isometric studio diorama with a coding AI
              robot agent, a creator directing the cinema camera, clapperboard action, glowing holiday
              fairy lights & tree, and a floating 3D title marquee sign

Usage (studio_cli.py calls this for you):
  blender -b --factory-startup -P blender_scene.py -- --kind background --style clay3d --out bg.png
  blender -b --factory-startup -P blender_scene.py -- --kind intro --style clay3d \
      --title "Demo Vid Studio" --subtitle "Demo videos your agent directs" --seconds 3.2 --out frames/f_####
"""

import argparse
import math
import os
import random
import sys

import bpy

STYLES = {
    "clay3d": dict(
        bg=(1.00, 0.96, 0.85),       # Bright warm ivory / soft butter-cream backdrop!
        base=(0.76, 0.50, 0.30),
        floor1=(0.96, 0.90, 0.82),
        floor2=(0.89, 0.80, 0.70),
        wall_l=(0.97, 0.86, 0.76),
        wall_r=(0.78, 0.91, 0.84),
        accent=(0.92, 0.18, 0.24),
        emit=0.0,
        outline=False,
    ),
    "ambient": dict(
        bg=(0.96, 0.95, 0.99),
        base=(0.68, 0.62, 0.82),
        floor1=(0.96, 0.94, 0.99),
        floor2=(0.88, 0.85, 0.95),
        wall_l=(0.90, 0.86, 0.98),
        wall_r=(0.82, 0.93, 0.95),
        accent=(0.38, 0.32, 0.88),
        emit=0.0,
        outline=False,
    ),
    "minimal": dict(
        bg=(0.08, 0.09, 0.12),
        base=(0.18, 0.20, 0.25),
        floor1=(0.14, 0.16, 0.20),
        floor2=(0.11, 0.13, 0.17),
        wall_l=(0.16, 0.18, 0.23),
        wall_r=(0.13, 0.15, 0.20),
        accent=(0.35, 0.65, 0.98),
        emit=0.4,
        outline=False,
    ),
    "cartoon": dict(
        bg=(1.00, 0.94, 0.62),
        base=(0.95, 0.45, 0.20),
        floor1=(1.00, 0.97, 0.82),
        floor2=(0.98, 0.88, 0.55),
        wall_l=(1.00, 0.82, 0.35),
        wall_r=(0.45, 0.85, 0.98),
        accent=(0.96, 0.22, 0.28),
        emit=0.0,
        outline=True,
    ),
    "storybook": dict(
        bg=(0.97, 0.93, 0.84),
        base=(0.65, 0.44, 0.28),
        floor1=(0.95, 0.89, 0.78),
        floor2=(0.87, 0.78, 0.66),
        wall_l=(0.94, 0.84, 0.72),
        wall_r=(0.80, 0.88, 0.76),
        accent=(0.82, 0.32, 0.24),
        emit=0.0,
        outline=False,
    ),
    "cyberpunk": dict(
        bg=(0.02, 0.02, 0.05),
        base=(0.08, 0.09, 0.18),
        floor1=(0.06, 0.07, 0.14),
        floor2=(0.04, 0.05, 0.10),
        wall_l=(0.07, 0.08, 0.16),
        wall_r=(0.05, 0.06, 0.13),
        accent=(0.95, 0.12, 0.75),
        emit=1.5,
        outline=False,
    ),
}


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=["background", "intro", "outro"], default="background")
    ap.add_argument("--style", choices=sorted(STYLES), default="clay3d")
    ap.add_argument("--out", required=True, help="PNG path (background) or frame pattern with #### (intro/outro)")
    ap.add_argument("--title", default="Demo Vid Studio")
    ap.add_argument("--subtitle", default="Demo videos your agent directs")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--seconds", type=float, default=2.4)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--samples", type=int, default=16)
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


def mat(name, color, rough=0.40, metal=0.0, sss=0.22, emit=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if "Subsurface Weight" in bsdf.inputs and sss > 0:
        bsdf.inputs["Subsurface Weight"].default_value = sss
    if "Coat Weight" in bsdf.inputs:
        bsdf.inputs["Coat Weight"].default_value = 0.22
    if emit > 0:
        key = "Emission Color" if "Emission Color" in bsdf.inputs else "Emission"
        bsdf.inputs[key].default_value = (*color, 1.0)
        bsdf.inputs["Emission Strength"].default_value = emit
    return m


def smooth(obj):
    for p in obj.data.polygons:
        p.use_smooth = True


def box(loc, scale, material, bevel=0.08, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel > 0:
        b = o.modifiers.new("b", "BEVEL")
        b.width = bevel
        b.segments = 5
    smooth(o)
    o.data.materials.append(material)
    return o


def cyl(loc, r, d, material, rot=(0, 0, 0), bevel=0.04):
    bpy.ops.mesh.primitive_cylinder_add(vertices=36, radius=r, depth=d, location=loc, rotation=rot)
    o = bpy.context.active_object
    if bevel > 0:
        b = o.modifiers.new("b", "BEVEL")
        b.width = bevel
        b.segments = 4
    smooth(o)
    o.data.materials.append(material)
    return o


def cone(loc, r1, r2, d, material, rot=(0, 0, 0), bevel=0.05):
    bpy.ops.mesh.primitive_cone_add(vertices=36, radius1=r1, radius2=r2, depth=d, location=loc, rotation=rot)
    o = bpy.context.active_object
    if bevel > 0:
        b = o.modifiers.new("b", "BEVEL")
        b.width = bevel
        b.segments = 4
    smooth(o)
    o.data.materials.append(material)
    return o


def sphere(loc, r, material):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=36, ring_count=20, radius=r, location=loc)
    o = bpy.context.active_object
    smooth(o)
    o.data.materials.append(material)
    return o


def load_bold_font():
    candidates = [
        r"C:\Windows\Fonts\LatoWeb-Bold.ttf",
        r"C:\Windows\Fonts\ariblk.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for fp in candidates:
        if os.path.exists(fp):
            try:
                return bpy.data.fonts.load(fp)
            except Exception:
                pass
    return None


def build_palette(st):
    return dict(
        base=mat("base", st["base"], rough=0.45),
        floor1=mat("floor1", st["floor1"], rough=0.50),
        floor2=mat("floor2", st["floor2"], rough=0.50),
        wall_l=mat("wall_l", st["wall_l"], rough=0.55),
        wall_r=mat("wall_r", st["wall_r"], rough=0.55),
        wood=mat("wood", (0.80, 0.52, 0.32), rough=0.42),
        dark=mat("dark", (0.14, 0.15, 0.24), rough=0.35, metal=0.15),
        white=mat("white", (0.99, 0.98, 0.99), rough=0.32),
        red=mat("red", st["accent"], rough=0.38, sss=0.25, emit=st["emit"] * 0.4),
        green=mat("green", (0.12, 0.62, 0.36), rough=0.42, sss=0.25),
        mint=mat("mint", (0.20, 0.80, 0.62), rough=0.38, sss=0.25),
        gold=mat("gold", (0.98, 0.72, 0.12), rough=0.32, metal=0.25),
        sky=mat("sky", (0.24, 0.62, 0.96), rough=0.38, sss=0.25),
        lilac=mat("lilac", (0.58, 0.42, 0.94), rough=0.38, sss=0.25),
        skin=mat("skin", (0.96, 0.78, 0.68), rough=0.40, sss=0.35),
        bulb_gold=mat("bgold", (1.00, 0.80, 0.20), rough=0.1, emit=2.8),
        bulb_red=mat("bred", (1.00, 0.20, 0.28), rough=0.1, emit=2.6),
        bulb_mint=mat("bmint", (0.20, 0.95, 0.65), rough=0.1, emit=2.6),
        bulb_blue=mat("bblue", (0.25, 0.78, 1.00), rough=0.1, emit=2.6),
        scr1=mat("scr1", (0.18, 0.85, 0.98), rough=0.2, emit=1.5),
        scr2=mat("scr2", (0.98, 0.38, 0.68), rough=0.2, emit=1.5),
    )


def build_character(x, y, z, rot_z, body_mat, P, is_robot=False):
    parts = []
    parts.append(box((x, y, z + 0.65), (0.74, 0.54, 0.80), body_mat, bevel=0.18, rot=(0, 0, rot_z)))
    dx = -0.36 * math.sin(rot_z)
    dy = -0.36 * math.cos(rot_z)
    px = 0.14 * math.cos(rot_z)
    py = -0.14 * math.sin(rot_z)

    if is_robot:
        parts.append(box((x, y, z + 1.44), (0.84, 0.70, 0.70), P["white"], bevel=0.18, rot=(0, 0, rot_z)))
        parts.append(box((x + dx, y + dy, z + 1.44), (0.64, 0.10, 0.38), P["dark"], bevel=0.05, rot=(0, 0, rot_z)))
        parts.append(sphere((x + dx * 1.12 - px, y + dy * 1.12 - py, z + 1.45), 0.08, P["bulb_blue"]))
        parts.append(sphere((x + dx * 1.12 + px, y + dy * 1.12 + py, z + 1.45), 0.08, P["bulb_blue"]))
        parts.append(cyl((x, y, z + 1.06), 0.38, 0.16, P["red"]))
        parts.append(cyl((x, y, z + 1.90), 0.05, 0.26, P["dark"]))
        bobble = sphere((x, y, z + 2.08), 0.14, P["bulb_gold"])
        parts.append(bobble)
    else:
        parts.append(sphere((x, y, z + 1.45), 0.45, P["skin"]))
        parts.append(sphere((x + dx * 1.12 - px, y + dy * 1.12 - py, z + 1.46), 0.065, P["dark"]))
        parts.append(sphere((x + dx * 1.12 + px, y + dy * 1.12 + py, z + 1.46), 0.065, P["dark"]))
        parts.append(sphere((x + dx * 1.08 - px * 1.5, y + dy * 1.08 - py * 1.5, z + 1.36), 0.06, P["red"]))
        parts.append(sphere((x + dx * 1.08 + px * 1.5, y + dy * 1.08 + py * 1.5, z + 1.36), 0.06, P["red"]))
        parts.append(cyl((x, y, z + 1.78), 0.46, 0.16, P["white"]))
        parts.append(cone((x - 0.05, y + 0.05, z + 2.12), 0.42, 0.04, 0.62, P["red"], rot=(math.radians(-12), math.radians(10), 0)))
        parts.append(sphere((x - 0.14, y + 0.14, z + 2.45), 0.14, P["white"]))

    ax = 0.48 * math.cos(rot_z)
    ay = -0.48 * math.sin(rot_z)
    arm_l = box((x - ax, y - ay, z + 0.70), (0.24, 0.46, 0.24), body_mat, bevel=0.08, rot=(math.radians(25), 0, rot_z))
    arm_r = box((x + ax, y + ay, z + 0.70), (0.24, 0.46, 0.24), body_mat, bevel=0.08, rot=(math.radians(25), 0, rot_z))
    parts.extend([arm_l, arm_r])
    return arm_l, arm_r


def build_christmas_tree(x, y, z, P):
    cyl((x, y, z + 0.32), 0.38, 0.55, P["red"])
    cyl((x, y, z + 0.72), 0.20, 0.45, P["wood"])
    cone((x, y, z + 1.45), 1.35, 0.25, 1.35, P["green"])
    cone((x, y, z + 2.25), 1.08, 0.20, 1.15, P["green"])
    cone((x, y, z + 2.95), 0.78, 0.05, 0.95, P["green"])
    star = sphere((x, y, z + 3.55), 0.26, P["bulb_gold"])
    baubles = [
        (0.85, -0.45, 1.15, P["bulb_red"]), (-0.75, -0.55, 1.25, P["bulb_gold"]), (0.15, -0.95, 1.10, P["bulb_blue"]),
        (-0.45, 0.75, 1.30, P["bulb_mint"]), (0.65, 0.55, 1.20, P["bulb_red"]),
        (0.58, -0.42, 2.05, P["bulb_gold"]), (-0.55, -0.35, 2.15, P["bulb_red"]), (0.0, -0.68, 1.95, P["bulb_mint"]),
        (0.35, -0.28, 2.78, P["bulb_blue"]), (-0.32, -0.25, 2.82, P["bulb_gold"]),
    ]
    for bx, by, bz, bmat in baubles:
        sphere((x + bx, y + by, z + bz), 0.13, bmat)

    box((x - 0.95, y - 0.55, z + 0.35), (0.62, 0.62, 0.58), P["red"], bevel=0.06, rot=(0, 0, math.radians(15)))
    box((x - 0.95, y - 0.55, z + 0.36), (0.66, 0.14, 0.60), P["gold"], bevel=0.02, rot=(0, 0, math.radians(15)))
    box((x - 0.95, y - 0.55, z + 0.36), (0.14, 0.66, 0.60), P["gold"], bevel=0.02, rot=(0, 0, math.radians(15)))
    box((x - 0.35, y - 1.05, z + 0.28), (0.50, 0.50, 0.46), P["sky"], bevel=0.06, rot=(0, 0, math.radians(-12)))
    box((x - 0.35, y - 1.05, z + 0.29), (0.54, 0.12, 0.48), P["white"], bevel=0.02, rot=(0, 0, math.radians(-12)))
    return star


def build_fairy_lights(offset_x, offset_y, offset_z, P):
    bulbs = [P["bulb_gold"], P["bulb_red"], P["bulb_mint"], P["bulb_blue"]]
    for i in range(11):
        t = i / 10
        x = offset_x - 3.2 + t * 6.4
        sag = 0.28 * math.sin(t * math.pi * 2)
        z = offset_z + 4.45 - abs(sag)
        sphere((x, offset_y + 3.35, z), 0.14, bulbs[i % 4])
    for i in range(11):
        t = i / 10
        y = offset_y - 3.2 + t * 6.4
        sag = 0.28 * math.sin(t * math.pi * 2)
        z = offset_z + 4.45 - abs(sag)
        sphere((offset_x + 3.35, y, z), 0.14, bulbs[(i + 1) % 4])


def build_isometric_studio(scene, st, P):
    world = bpy.data.worlds.new("world")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (*st["bg"], 1.0)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.42 if st["emit"] == 0 else 0.5

    # Warm ivory backdrop plane behind the isometric room (emit=1.35 counters exposure=-0.35 so backdrop stays bright warm ivory!)
    box((6.0, 6.0, -1.2), (75.0, 75.0, 0.2), mat("bg_floor", st["bg"], rough=0.9, sss=0.0, emit=1.38 if st["emit"] == 0 else 0.0), bevel=0.0)

    offset_x, offset_y, offset_z = 0.0, 0.0, 0.0
    box((offset_x, offset_y, offset_z - 0.25), (7.8, 7.8, 0.5), P["base"], bevel=0.12)
    for ix in range(-3, 4):
        for iy in range(-3, 4):
            tm = P["floor1"] if (ix + iy) % 2 == 0 else P["floor2"]
            box((offset_x + ix * 1.0, offset_y + iy * 1.0, offset_z + 0.04), (0.96, 0.96, 0.10), tm, bevel=0.03)

    cyl((offset_x + 0.1, offset_y - 0.4, offset_z + 0.10), 1.95, 0.05, P["red"], bevel=0.02)
    cyl((offset_x + 0.1, offset_y - 0.4, offset_z + 0.12), 1.55, 0.04, P["floor1"], bevel=0.02)

    box((offset_x, offset_y + 3.68, offset_z + 2.45), (7.8, 0.35, 5.3), P["wall_l"], bevel=0.08)
    box((offset_x + 3.68, offset_y, offset_z + 2.45), (0.35, 7.8, 5.3), P["wall_r"], bevel=0.08)

    build_fairy_lights(offset_x, offset_y, offset_z, P)

    for wx, col in [(-2.4, P["lilac"]), (-1.2, P["sky"])]:
        for wz in [2.3, 3.4]:
            box((offset_x + wx, offset_y + 3.45, offset_z + wz), (0.92, 0.12, 0.92), col, bevel=0.06)

    bpy.ops.mesh.primitive_torus_add(
        major_segments=36, minor_segments=20, major_radius=0.58, minor_radius=0.20,
        location=(offset_x + 0.5, offset_y + 3.42, offset_z + 3.15), rotation=(math.radians(90), 0, 0),
    )
    wr = bpy.context.active_object
    smooth(wr)
    wr.data.materials.append(P["green"])
    sphere((offset_x + 0.5, offset_y + 3.30, offset_z + 3.68), 0.18, P["red"])
    sphere((offset_x + 0.98, offset_y + 3.30, offset_z + 3.15), 0.10, P["bulb_gold"])
    sphere((offset_x + 0.02, offset_y + 3.30, offset_z + 3.15), 0.10, P["bulb_red"])

    box((offset_x + 3.45, offset_y + 0.95, offset_z + 2.75), (0.14, 3.2, 1.95), P["white"], bevel=0.06)
    for idx, col in enumerate([P["red"], P["gold"], P["mint"], P["sky"]]):
        box((offset_x + 3.35, offset_y + 2.05 - idx * 0.72, offset_z + 3.0), (0.08, 0.56, 0.62), col, bevel=0.03)
        box((offset_x + 3.35, offset_y + 2.05 - idx * 0.72, offset_z + 2.22), (0.08, 0.56, 0.52), P["lilac"], bevel=0.03)

    star = build_christmas_tree(offset_x + 2.35, offset_y - 2.15, offset_z + 0.08, P)

    dx, dy = offset_x - 1.35, offset_y + 1.75
    box((dx, dy, offset_z + 1.05), (3.4, 1.6, 0.16), P["wood"], bevel=0.05)
    for lx in [-1.45, 1.45]:
        for ly in [-0.6, 0.6]:
            box((dx + lx, dy + ly, offset_z + 0.5), (0.16, 0.16, 1.0), P["white"], bevel=0.03)

    box((dx - 0.75, dy + 0.35, offset_z + 1.85), (1.35, 0.14, 0.92), P["dark"], bevel=0.05)
    box((dx - 0.75, dy + 0.27, offset_z + 1.85), (1.22, 0.04, 0.78), P["dark"], bevel=0.02)
    for row_i, (w_bar, col_bar) in enumerate([(0.7, P["scr1"]), (0.95, P["bulb_gold"]), (0.55, P["bulb_mint"]), (0.85, P["scr2"])]):
        box((dx - 1.25 + w_bar / 2, dy + 0.24, offset_z + 2.08 - row_i * 0.14), (w_bar, 0.04, 0.07), col_bar, bevel=0.01)
    box((dx - 0.75, dy + 0.38, offset_z + 1.25), (0.22, 0.22, 0.35), P["dark"], bevel=0.03)

    box((dx + 0.75, dy + 0.35, offset_z + 1.85), (1.35, 0.14, 0.92), P["dark"], bevel=0.05)
    box((dx + 0.75, dy + 0.27, offset_z + 1.85), (1.18, 0.04, 0.74), P["scr1"], bevel=0.02)
    box((dx + 0.75, dy + 0.24, offset_z + 1.88), (0.42, 0.05, 0.42), P["red"], bevel=0.06)
    box((dx + 0.75, dy + 0.38, offset_z + 1.25), (0.22, 0.22, 0.35), P["dark"], bevel=0.03)

    cyl((dx - 1.45, dy + 0.4, offset_z + 1.18), 0.20, 0.08, P["gold"])
    cyl((dx - 1.45, dy + 0.4, offset_z + 1.55), 0.04, 0.70, P["gold"])
    cyl((dx - 1.30, dy + 0.25, offset_z + 1.92), 0.24, 0.28, P["red"], rot=(math.radians(35), math.radians(-20), 0))
    sphere((dx - 1.25, dy + 0.20, offset_z + 1.82), 0.14, P["bulb_gold"])

    box((dx - 0.1, dy - 0.35, offset_z + 1.16), (0.95, 0.38, 0.08), P["white"], bevel=0.03)
    cyl((dx + 1.15, dy - 0.35, offset_z + 1.25), 0.16, 0.32, P["red"])

    rob_arms = build_character(dx - 0.15, dy - 1.18, offset_z + 0.1, math.radians(-25), P["sky"], P, is_robot=True)
    dir_arms = build_character(offset_x + 0.85, offset_y - 0.15, offset_z + 0.1, math.radians(15), P["green"], P, is_robot=False)

    cx, cy = offset_x - 0.15, offset_y - 1.65
    box((cx, cy, offset_z + 1.35), (0.65, 0.85, 0.55), P["dark"], bevel=0.08, rot=(0, 0, math.radians(-25)))
    reel1 = cyl((cx - 0.08, cy + 0.15, offset_z + 1.78), 0.24, 0.14, P["gold"], rot=(0, math.radians(90), math.radians(-25)))
    reel2 = cyl((cx + 0.12, cy - 0.22, offset_z + 1.78), 0.24, 0.14, P["gold"], rot=(0, math.radians(90), math.radians(-25)))
    cyl((cx - 0.22, cy + 0.48, offset_z + 1.35), 0.22, 0.38, P["white"], rot=(math.radians(90), 0, math.radians(25)))
    sphere((cx + 0.22, cy + 0.22, offset_z + 1.55), 0.08, P["bulb_red"])
    for ang in [0, 120, 240]:
        rad = math.radians(ang)
        cyl((cx + 0.25 * math.cos(rad), cy + 0.25 * math.sin(rad), offset_z + 0.65), 0.05, 1.25, P["dark"], rot=(math.radians(18), math.radians(12), rad))

    sx, sy = offset_x - 2.25, offset_y - 1.75
    box((sx, sy, offset_z + 0.72), (1.15, 0.16, 0.85), P["dark"], bevel=0.05, rot=(0, 0, math.radians(28)))
    clap_bar = box((sx, sy, offset_z + 1.22), (1.15, 0.18, 0.22), P["gold"], bevel=0.04, rot=(0, math.radians(-16), math.radians(28)))

    return dict(rob_arms=rob_arms, dir_arms=dir_arms, clap_bar=clap_bar, reels=(reel1, reel2), star=star)


def setup_lights_and_camera(scene, st, width, height, kind):
    bpy.ops.object.light_add(type="AREA", location=(-11, -9, 15))
    key = bpy.context.active_object
    key.data.energy = 1650 if st["emit"] == 0 else 650
    key.data.size = 9
    key.data.color = (1.0, 0.96, 0.90)
    key.rotation_euler = (math.radians(46), 0, math.radians(-42))

    bpy.ops.object.light_add(type="AREA", location=(-12, 7, 10))
    fill = bpy.context.active_object
    fill.data.energy = 420 if st["emit"] == 0 else 250
    fill.data.size = 12
    fill.data.color = (0.88, 0.93, 1.0)
    fill.rotation_euler = (math.radians(55), 0, math.radians(-115))

    bpy.ops.object.light_add(type="AREA", location=(7, -12, 12))
    rim = bpy.context.active_object
    rim.data.energy = 520 if st["emit"] == 0 else 350
    rim.data.size = 10
    rim.data.color = (1.0, 0.90, 0.95)
    rim.rotation_euler = (math.radians(50), 0, math.radians(25))

    bpy.ops.object.light_add(type="POINT", location=(1.2, 0.5, 3.2))
    pt = bpy.context.active_object
    pt.data.energy = 110
    pt.data.color = (1.0, 0.82, 0.48)
    pt.data.shadow_soft_size = 1.2

    bpy.ops.object.camera_add(location=(-14.0, -14.0, 14.2), rotation=(math.radians(60), 0, math.radians(-45)))
    cam = bpy.context.active_object
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 14.2 if width <= height else 16.2
    scene.camera = cam
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    return cam


def add_marquee_title(args, P):
    font_data = load_bold_font()
    board = box((-0.4, -0.4, 7.15), (8.4, 0.48, 2.15), P["white"], bevel=0.22, rot=(0, 0, math.radians(-45)))
    pill = box((-0.55, -0.55, 6.40), (6.5, 0.38, 0.75), P["red"], bevel=0.16, rot=(0, 0, math.radians(-45)))
    s1 = sphere((-3.25, 2.45, 7.18), 0.24, P["bulb_gold"])
    s2 = sphere((2.45, -3.25, 7.18), 0.24, P["bulb_gold"])

    bpy.ops.object.text_add(location=(-0.58, -0.58, 7.22), rotation=(math.radians(90), 0, math.radians(-45)))
    t1 = bpy.context.active_object
    t1.data.body = args.title or "Demo Vid Studio"
    if font_data:
        t1.data.font = font_data
    t1.data.size = min(1.06, max(0.68, 17.5 / max(10, len(t1.data.body))))
    t1.data.extrude = 0.15
    t1.data.bevel_depth = 0.02
    t1.data.align_x = "CENTER"
    t1.data.align_y = "CENTER"
    t1.data.materials.append(P["dark"])

    t2 = None
    if args.subtitle:
        bpy.ops.object.text_add(location=(-0.72, -0.72, 6.38), rotation=(math.radians(90), 0, math.radians(-45)))
        t2 = bpy.context.active_object
        t2.data.body = args.subtitle.upper()
        if font_data:
            t2.data.font = font_data
        t2.data.size = min(0.42, max(0.28, 13.5 / max(15, len(t2.data.body))))
        t2.data.extrude = 0.05
        t2.data.bevel_depth = 0.008
        t2.data.align_x = "CENTER"
        t2.data.align_y = "CENTER"
        t2.data.materials.append(P["white"])

    return [board, pill, s1, s2, t1] + ([t2] if t2 else [])


def animate_studio(scene, args, rig, marquee_objs):
    fps = args.fps
    end = max(2, int(round(args.seconds * fps)))
    scene.render.fps = fps
    scene.frame_start, scene.frame_end = 1, end
    fly = int(end * 0.38)

    # Marquee smoothly drops/bounces in on intro (or settles on outro)
    for obj in marquee_objs:
        z_final = obj.location[2]
        if args.kind == "intro":
            obj.location[2] = z_final + 2.2
            obj.keyframe_insert("location", frame=1)
            obj.location[2] = z_final - 0.12
            obj.keyframe_insert("location", frame=fly)
            obj.location[2] = z_final
            obj.keyframe_insert("location", frame=min(end, fly + 8))
        else:
            obj.location[2] = z_final
            obj.keyframe_insert("location", frame=1)
            obj.location[2] = z_final + 0.15
            obj.keyframe_insert("location", frame=end)

    # Clapperboard snaps shut!
    cb = rig["clap_bar"]
    cb.rotation_euler[1] = math.radians(-24)
    cb.keyframe_insert("rotation_euler", frame=1)
    cb.rotation_euler[1] = 0.0
    cb.keyframe_insert("rotation_euler", frame=min(end, int(fps * 0.45)))

    # Robot typing at keyboard & creator directing at camera
    arm_l, arm_r = rig["rob_arms"]
    d_l, d_r = rig["dir_arms"]
    for f in range(1, end + 1, 4):
        phase = (f / fps) * 14.0
        arm_l.rotation_euler[0] = math.radians(25 + 14 * math.sin(phase))
        arm_r.rotation_euler[0] = math.radians(25 - 14 * math.sin(phase))
        arm_l.keyframe_insert("rotation_euler", frame=f)
        arm_r.keyframe_insert("rotation_euler", frame=f)

        d_l.rotation_euler[0] = math.radians(25 + 10 * math.cos(phase * 0.5))
        d_l.keyframe_insert("rotation_euler", frame=f)


def main():
    args = parse_args()
    st = STYLES[args.style]
    scene = reset_scene()
    engine = pick_engine(scene)
    if engine == "CYCLES":
        scene.cycles.samples = args.samples
    elif hasattr(scene, "eevee") and hasattr(scene.eevee, "taa_render_samples"):
        scene.eevee.taa_render_samples = args.samples

    P = build_palette(st)
    rig = build_isometric_studio(scene, st, P)
    cam = setup_lights_and_camera(scene, st, args.width, args.height, args.kind)

    scene.view_settings.view_transform = "Standard"
    looks = [i.identifier for i in scene.view_settings.bl_rna.properties["look"].enum_items]
    hc = next((l for l in looks if l == "High Contrast" or "Medium High Contrast" in l), None)
    if hc:
        scene.view_settings.look = hc
    scene.view_settings.exposure = -0.35 if st["emit"] == 0 else -0.1

    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.filepath = args.out

    if args.kind == "background":
        # For stage background, zoom slightly wider & add gentle tilt-shift DoF so foreground cards pop
        cam.data.ortho_scale = 15.6 if args.width <= args.height else 18.0
        bpy.ops.render.render(write_still=True)
    else:
        marquee = add_marquee_title(args, P)
        animate_studio(scene, args, rig, marquee)
        bpy.ops.render.render(animation=True)
    print(f"[blender_scene] engine={engine} kind={args.kind} style={args.style} out={args.out}")


if __name__ == "__main__":
    main()
