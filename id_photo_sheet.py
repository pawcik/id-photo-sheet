"""
One-shot tool: turn one or more portrait photos into a printable 10x15cm
sheet of 35x45mm ID/document photos (6 slots, 2 columns x 3 rows, with
corner cut-mark guides), sized for kiosk printing (e.g. Rossmann in Poland,
whose standard print format is 10x15cm / 3:2).

Two ways to feed it a photo:

1. PRECISE (recommended for a real document photo) -- give the pixel
   coordinates of the hairline, chin, and face center (read them off the
   photo in any image viewer: macOS Preview, hover the cursor, etc.):

     --photo SOURCE HAIR_TOP CHIN FACE_CENTER_X

   The crop is framed so the head occupies --zoom of the 45mm frame height
   (most official rules, including Polish ones, want ~70-80%). Repeat
   --photo for more than one person; the 6 slots split evenly across them.

2. QUICK (casual reprints, no measuring) -- just pass bare image paths.
   Each gets a center-crop to the 35:45 aspect ratio instead of being
   stretched (a warning is printed). This is NOT face-aware, so head size
   and position aren't guaranteed to meet any document-photo rule.

--variants generates 3 sheets at once instead of one, so you can compare
zoom/framing levels before printing.

Examples:
    # one person, precise landmarks, default zoom (0.68)
    python3 id_photo_sheet.py out.jpg --photo me.heic 83 1858 1134

    # two people, 3 copies of each, custom zoom
    python3 id_photo_sheet.py out.jpg \\
        --photo kasia.heif 289 1991 1110 \\
        --photo pawel.heif 83 1858 1134 \\
        --zoom 0.6

    # compare 3 zoom levels (0.75 / 0.68 / 0.63) at once
    python3 id_photo_sheet.py out.jpg --photo me.heic 83 1858 1134 --variants

    # quick mode: no landmarks, raw photos straight in
    python3 id_photo_sheet.py out.jpg kasia.heif pawel.heif
    python3 id_photo_sheet.py out.jpg photo.heic --crop-bias 0.2
    python3 id_photo_sheet.py out.jpg photo.heic --variants
"""
import argparse
from PIL import Image, ImageDraw

try:
    import pillow_heif
    pillow_heif.register_heif_opener()  # lets Image.open() read .heic/.heif directly
except ImportError:
    pass

DPI = 600
MM_W, MM_H = 35, 45
SHEET_MM_W, SHEET_MM_H = 100, 150
COLS, ROWS = 2, 3
TOTAL_SLOTS = COLS * ROWS  # 6
TARGET_RATIO = MM_W / MM_H  # 35:45 = 0.778

# 2 * 35mm = 70mm <= 100mm and 3 * 45mm = 135mm <= 150mm, so 6 copies of a
# 35x45mm photo do fit on one 10x15cm sheet (tighter than the common 4-up
# layout, confirmed against Rossmann's own 10x15cm = 3:2 standard format).


def mm_to_px(mm):
    return int(round(mm / 25.4 * DPI))


PX_W, PX_H = mm_to_px(MM_W), mm_to_px(MM_H)


def crop_precise(source, hair_top, chin, face_center_x, zoom=0.68, crop_top=None):
    """zoom: fraction of the 45mm frame height the head (hair-top to chin)
    should occupy. Higher = zoomed in/tighter, lower = zoomed out."""
    im = Image.open(source).convert("RGB")
    head_h = chin - hair_top
    if head_h <= 0:
        raise ValueError("chin must be below hair_top")

    crop_h = int(round(head_h / zoom))
    crop_w = int(round(crop_h * MM_W / MM_H))

    if crop_top is None:
        crop_top = max(0, hair_top - int(round(0.03 * crop_h)))

    crop_left = int(round(face_center_x - crop_w / 2))
    crop_left = max(0, min(crop_left, im.width - crop_w))
    crop_bottom = crop_top + crop_h
    crop_right = crop_left + crop_w

    if crop_right > im.width or crop_bottom > im.height or crop_top < 0:
        raise ValueError(
            f"{source}: crop ({crop_left},{crop_top},{crop_right},{crop_bottom}) "
            f"exceeds image bounds ({im.width}x{im.height}) -- try a higher "
            f"--zoom (less zoomed out) or a lower --crop-top"
        )

    face = im.crop((crop_left, crop_top, crop_right, crop_bottom))
    return face.resize((PX_W, PX_H), Image.LANCZOS)


def crop_fallback(source, crop_bias=0.5):
    """Center-crop (positioned by crop_bias) a raw/uncropped photo to the
    35:45 aspect ratio instead of stretching. Not face-aware."""
    img = Image.open(source).convert("RGB")
    w, h = img.size
    ratio = w / h
    if abs(ratio - TARGET_RATIO) > 0.01:
        print(f"warning: {source} is {w}x{h} (ratio {ratio:.3f}), not 35:45 "
              f"({TARGET_RATIO:.3f}) -- cropping with crop_bias={crop_bias}; "
              f"head framing is not guaranteed to meet ID-photo rules")
        if ratio > TARGET_RATIO:
            new_w = int(round(h * TARGET_RATIO))
            left = int(round((w - new_w) * crop_bias))
            img = img.crop((left, 0, left + new_w, h))
        else:
            new_h = int(round(w / TARGET_RATIO))
            top = int(round((h - new_h) * crop_bias))
            img = img.crop((0, top, w, top + new_h))
    if img.size != (PX_W, PX_H):
        img = img.resize((PX_W, PX_H), Image.LANCZOS)
    return img


def build_sheet(cropped_images, out_path, copies=None):
    """cropped_images: list of already-35x45mm-sized PIL Images."""
    n = len(cropped_images)
    if n < 1:
        raise ValueError("need at least one photo")
    if n > TOTAL_SLOTS:
        raise ValueError(f"at most {TOTAL_SLOTS} photos supported per sheet")

    if copies is None:
        base = TOTAL_SLOTS // n
        remainder = TOTAL_SLOTS % n
        copies = [base + (1 if i < remainder else 0) for i in range(n)]
    elif sum(copies) != TOTAL_SLOTS:
        raise ValueError(f"copies must sum to {TOTAL_SLOTS}, got {sum(copies)}")

    sheet_w, sheet_h = mm_to_px(SHEET_MM_W), mm_to_px(SHEET_MM_H)
    gap = mm_to_px(4)
    mark_len = mm_to_px(3)
    mark_col = (150, 150, 150)

    sheet = Image.new("RGB", (sheet_w, sheet_h), "white")
    draw = ImageDraw.Draw(sheet)

    grid_w = COLS * PX_W + (COLS + 1) * gap
    grid_h = ROWS * PX_H + (ROWS + 1) * gap
    off_x = (sheet_w - grid_w) // 2
    off_y = (sheet_h - grid_h) // 2

    # photo-major order: all copies of photo A first, then all of photo B, etc.
    slot_images = []
    for img, n_copies in zip(cropped_images, copies):
        slot_images.extend([img] * n_copies)

    idx = 0
    for r in range(ROWS):
        for c in range(COLS):
            x = off_x + gap + c * (PX_W + gap)
            y = off_y + gap + r * (PX_H + gap)
            sheet.paste(slot_images[idx], (x, y))
            corners = [(x, y), (x + PX_W, y), (x, y + PX_H), (x + PX_W, y + PX_H)]
            for (cx, cy) in corners:
                dx = -1 if cx == x else 1
                dy = -1 if cy == y else 1
                draw.line([(cx, cy), (cx + dx * mark_len, cy)], fill=mark_col, width=2)
                draw.line([(cx, cy), (cx, cy + dy * mark_len)], fill=mark_col, width=2)
            idx += 1

    sheet.save(out_path, dpi=(DPI, DPI), quality=95)
    print(f"copies per photo: {copies} -> {out_path} ({sheet.size[0]}x{sheet.size[1]}px @ {DPI}dpi)")


def make_sheet(precise_photos, quick_photos, out_path, zoom=0.68, crop_bias=0.5):
    if precise_photos:
        images = [crop_precise(path, hair_top, chin, face_x, zoom=zoom)
                  for (path, hair_top, chin, face_x) in precise_photos]
    else:
        images = [crop_fallback(path, crop_bias=crop_bias) for path in quick_photos]
    build_sheet(images, out_path)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("out_path")
    parser.add_argument("photos", nargs="*", help="quick mode: bare image paths (no landmarks)")
    parser.add_argument("--photo", dest="precise_photos", action="append", nargs=4,
                         metavar=("PATH", "HAIR_TOP", "CHIN", "FACE_CENTER_X"),
                         help="precise mode: source path + pixel landmarks (repeatable)")
    parser.add_argument("--zoom", "--ratio", dest="zoom", type=float, default=0.68,
                         help="precise mode only: head-height fraction of frame "
                              "(default 0.68). Higher = zoomed in, lower = zoomed out")
    parser.add_argument("--crop-bias", type=float, default=0.5,
                         help="quick mode only: 0=top/left, 0.5=centered (default), 1=bottom/right")
    parser.add_argument("--variants", action="store_true",
                         help="generate 3 sheets instead of one, to compare zoom/framing")
    args = parser.parse_args()

    if args.precise_photos:
        precise_photos = [(path, int(hair_top), int(chin), int(face_x))
                           for path, hair_top, chin, face_x in args.precise_photos]
        quick_photos = []
    else:
        precise_photos = []
        quick_photos = args.photos
        if not quick_photos:
            parser.error("give either bare image paths or one or more --photo PATH HAIR_TOP CHIN FACE_CENTER_X")

    stem, dot, ext = args.out_path.rpartition(".")
    if not dot:
        stem, ext = args.out_path, "jpg"

    if args.variants:
        if precise_photos:
            for label, zoom in (("tight", 0.75), ("medium", 0.68), ("zoomedout", 0.63)):
                make_sheet(precise_photos, quick_photos, f"{stem}_{label}.{ext}", zoom=zoom)
        else:
            for label, bias in (("top", 0.15), ("center", 0.5), ("bottom", 0.85)):
                make_sheet(precise_photos, quick_photos, f"{stem}_{label}.{ext}", crop_bias=bias)
    else:
        make_sheet(precise_photos, quick_photos, args.out_path, zoom=args.zoom, crop_bias=args.crop_bias)


if __name__ == "__main__":
    main()
