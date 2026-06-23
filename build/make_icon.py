"""
Beat or Delete icon — concept 3:
Judge's gavel striking a vinyl record. Dark bg, bold colors.
"""
from PIL import Image, ImageDraw
import math
import os

def draw_icon(size=1024):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size

    # --- Background rounded rect ---
    bg_r = int(s * 0.22)
    bg_color = (18, 18, 24, 255)
    d.rounded_rectangle([0, 0, s, s], radius=bg_r, fill=bg_color)

    cx, cy = s * 0.46, s * 0.54  # record center, shifted left+down

    # --- Vinyl record ---
    r = s * 0.32
    # Outer record (dark vinyl)
    d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=(22, 22, 22, 255), outline=(60, 60, 60, 255), width=int(s*0.008))

    # Groove rings
    for ratio in [0.9, 0.78, 0.66, 0.54]:
        gr = r * ratio
        d.ellipse([cx-gr, cy-gr, cx+gr, cy+gr], outline=(45, 45, 45, 255), width=max(1, int(s*0.004)))

    # Label circle (center of record) — red label
    lr = r * 0.32
    label_color = (180, 30, 30, 255)
    d.ellipse([cx-lr, cy-lr, cx+lr, cy+lr], fill=label_color)

    # Center hole
    hr = r * 0.055
    d.ellipse([cx-hr, cy-hr, cx+hr, cy+hr], fill=(18, 18, 24, 255))

    # --- Gavel ---
    # Gavel drawn at angle (~-40 degrees), top-right area
    # Handle
    handle_color = (180, 130, 60, 255)
    head_color = (200, 150, 70, 255)
    shadow_color = (120, 85, 30, 255)

    angle = math.radians(-42)
    cos_a, sin_a = math.cos(angle), math.sin(angle)

    def rot(px, py, ox, oy):
        dx, dy = px - ox, py - oy
        return ox + dx*cos_a - dy*sin_a, oy + dx*sin_a + dy*cos_a

    # Handle pivot point
    hx, hy = s * 0.72, s * 0.26

    # Handle: long rectangle
    hw, hl = s * 0.045, s * 0.38
    handle_pts = [
        rot(hx - hw/2, hy, hx, hy),
        rot(hx + hw/2, hy, hx, hy),
        rot(hx + hw/2, hy + hl, hx, hy),
        rot(hx - hw/2, hy + hl, hx, hy),
    ]
    d.polygon(handle_pts, fill=handle_color)

    # Gavel head: thick rectangle perpendicular to handle
    ghw, ghh = s * 0.22, s * 0.09
    ghx, ghy = hx, hy - s * 0.01  # head sits at top of handle
    head_pts = [
        rot(ghx - ghw/2, ghy - ghh/2, hx, hy),
        rot(ghx + ghw/2, ghy - ghh/2, hx, hy),
        rot(ghx + ghw/2, ghy + ghh/2, hx, hy),
        rot(ghx - ghw/2, ghy + ghh/2, hx, hy),
    ]
    d.polygon(head_pts, fill=head_color, outline=shadow_color, width=int(s*0.006))

    # Head banding lines (detail)
    for offset in [-ghw*0.3, ghw*0.3]:
        p1 = rot(ghx + offset, ghy - ghh/2, hx, hy)
        p2 = rot(ghx + offset, ghy + ghh/2, hx, hy)
        d.line([p1, p2], fill=shadow_color, width=max(1, int(s*0.006)))

    # --- Impact sparks where gavel meets record ---
    impact_x = cx + r * 0.5
    impact_y = cy - r * 0.55
    spark_color = (255, 200, 50, 220)
    for i in range(6):
        a = math.radians(i * 60 + 15)
        spark_len = s * 0.035
        x1, y1 = impact_x, impact_y
        x2 = impact_x + math.cos(a) * spark_len
        y2 = impact_y + math.sin(a) * spark_len
        d.line([(x1,y1),(x2,y2)], fill=spark_color, width=max(2, int(s*0.008)))

    # Small impact circle
    ir = s * 0.022
    d.ellipse([impact_x-ir, impact_y-ir, impact_x+ir, impact_y+ir], fill=(255, 220, 80, 200))

    return img


def make_icns(output_path):
    iconset_dir = output_path.replace(".icns", ".iconset")
    os.makedirs(iconset_dir, exist_ok=True)

    sizes = [16, 32, 64, 128, 256, 512, 1024]
    for sz in sizes:
        img = draw_icon(sz)
        img.save(f"{iconset_dir}/icon_{sz}x{sz}.png")
        # @2x versions
        if sz <= 512:
            img2 = draw_icon(sz * 2)
            img2 = img2.resize((sz * 2, sz * 2), Image.LANCZOS)
            img2.save(f"{iconset_dir}/icon_{sz}x{sz}@2x.png")

    os.system(f"iconutil -c icns '{iconset_dir}' -o '{output_path}'")
    print(f"Created: {output_path}")
    # Preview
    draw_icon(512).save(output_path.replace(".icns", "_preview.png"))
    print(f"Preview: {output_path.replace('.icns', '_preview.png')}")


make_icns("/Users/alonzigerman/personal/analyzer/build/AppIcon.icns")
