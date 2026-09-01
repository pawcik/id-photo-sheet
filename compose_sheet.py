"""
Compose a 10x15cm print sheet from one or more ID photos, replicating each
input to fill 6 slots (2 cols x 3 rows). Accepts .jpg/.png/.heic/.heif.

If an input isn't already cropped to the 35x45mm ratio (0.778), it gets
center-cropped to that ratio instead of stretched. `--crop-bias` controls
*where* that crop is taken from the excess space:
    0.0 = keep the top/left edge (crop away the bottom/right)
    0.5 = centered (default)
    1.0 = keep the bottom/right edge (crop away the top/left)
This only affects photos that need the fallback crop -- a photo already at
the 35x45mm ratio is used as-is regardless of --crop-bias.

Usage:
    python3 compose_sheet.py OUTPUT.jpg PHOTO1 [PHOTO2 ...] [--crop-bias 0..1]
    python3 compose_sheet.py OUTPUT.jpg PHOTO1 [PHOTO2 ...] --variants

Examples:
    # two different photos -> 3 copies of the first, 3 of the second
    python3 compose_sheet.py combined.jpg kasia.heif pawel.heif

    # pull the crop window higher (keep more headroom, cut the chin/shoulders)
    python3 compose_sheet.py combined.jpg kasia.heif --crop-bias 0.2

    # generate 3 files (bias 0.15 / 0.5 / 0.85) at once to compare framing
    python3 compose_sheet.py combined.jpg kasia.heif pawel.heif --variants
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

# 2 * 35mm = 70mm <= 100mm and 3 * 45mm = 135mm <= 150mm, so 6 copies of a
# 35x45mm photo do fit on one 10x15cm sheet (tighter than the common 4-up
# layout, confirmed against Rossmann's own 10x15cm = 3:2 standard format).


def mm_to_px(mm):
    return int(round(mm / 25.4 * DPI))


def build_sheet(photo_paths, out_path, copies=None, crop_bias=0.5):
    n = len(photo_paths)
    if n < 1:
        raise ValueError("need at least one photo")
    if n > TOTAL_SLOTS:
        raise ValueError(f"at most {TOTAL_SLOTS} photos supported per sheet")
    if not 0.0 <= crop_bias <= 1.0:
        raise ValueError("crop_bias must be between 0.0 and 1.0")

    if copies is None:
        base = TOTAL_SLOTS // n
        remainder = TOTAL_SLOTS % n
        copies = [base + (1 if i < remainder else 0) for i in range(n)]
    else:
        if sum(copies) != TOTAL_SLOTS:
            raise ValueError(f"copies must sum to {TOTAL_SLOTS}, got {sum(copies)}")

    px_w, px_h = mm_to_px(MM_W), mm_to_px(MM_H)
    sheet_w, sheet_h = mm_to_px(SHEET_MM_W), mm_to_px(SHEET_MM_H)
    gap = mm_to_px(4)
    mark_len = mm_to_px(3)
    mark_col = (150, 150, 150)

    sheet = Image.new("RGB", (sheet_w, sheet_h), "white")
    draw = ImageDraw.Draw(sheet)

    grid_w = COLS * px_w + (COLS + 1) * gap
    grid_h = ROWS * px_h + (ROWS + 1) * gap
    off_x = (sheet_w - grid_w) // 2
    off_y = (sheet_h - grid_h) // 2

    # build the ordered list of images for each of the 6 slots (photo-major:
    # all copies of photo A first, then all copies of photo B, etc.)
    target_ratio = MM_W / MM_H  # 35:45
    slot_images = []
    for path, n_copies in zip(photo_paths, copies):
        img = Image.open(path).convert("RGB")
        w, h = img.size
        ratio = w / h
        if abs(ratio - target_ratio) > 0.01:
            # not already a 35x45-shaped crop (e.g. a raw, uncropped HEIC
            # straight from the phone) -- crop to the right aspect ratio
            # instead of stretching, positioned per crop_bias. This does
            # NOT guarantee correct ID-photo head size/position -- for a
            # real document photo, first make a proper face-framed 35x45mm
            # crop (see make_id_sheet.py) and pass that in instead.
            print(f"warning: {path} is {w}x{h} (ratio {ratio:.3f}), "
                  f"not 35:45 ({target_ratio:.3f}) -- cropping with "
                  f"crop_bias={crop_bias}; head framing is not guaranteed "
                  f"to meet ID-photo rules")
            if ratio > target_ratio:
                new_w = int(round(h * target_ratio))
                left = int(round((w - new_w) * crop_bias))
                img = img.crop((left, 0, left + new_w, h))
            else:
                new_h = int(round(w / target_ratio))
                top = int(round((h - new_h) * crop_bias))
                img = img.crop((0, top, w, top + new_h))
        if img.size != (px_w, px_h):
            img = img.resize((px_w, px_h), Image.LANCZOS)
        slot_images.extend([img] * n_copies)

    idx = 0
    for r in range(ROWS):
        for c in range(COLS):
            x = off_x + gap + c * (px_w + gap)
            y = off_y + gap + r * (px_h + gap)
            sheet.paste(slot_images[idx], (x, y))
            corners = [(x, y), (x + px_w, y), (x, y + px_h), (x + px_w, y + px_h)]
            for (cx, cy) in corners:
                dx = -1 if cx == x else 1
                dy = -1 if cy == y else 1
                draw.line([(cx, cy), (cx + dx * mark_len, cy)], fill=mark_col, width=2)
                draw.line([(cx, cy), (cx, cy + dy * mark_len)], fill=mark_col, width=2)
            idx += 1

    sheet.save(out_path, dpi=(DPI, DPI), quality=95)
    print(f"copies per photo: {copies}, crop_bias={crop_bias} -> {out_path} "
          f"({sheet.size[0]}x{sheet.size[1]}px @ {DPI}dpi)")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("out_path")
    parser.add_argument("photos", nargs="+")
    parser.add_argument("--crop-bias", type=float, default=0.5,
                         help="0=top/left, 0.5=centered (default), 1=bottom/right")
    parser.add_argument("--variants", action="store_true",
                         help="generate 3 files (crop-bias 0.15/0.5/0.85) instead of one")
    args = parser.parse_args()

    if args.variants:
        stem, dot, ext = args.out_path.rpartition(".")
        if not dot:
            stem, ext = args.out_path, "jpg"
        for label, bias in (("top", 0.15), ("center", 0.5), ("bottom", 0.85)):
            build_sheet(args.photos, f"{stem}_{label}.{ext}", crop_bias=bias)
    else:
        build_sheet(args.photos, args.out_path, crop_bias=args.crop_bias)


if __name__ == "__main__":
    main()
