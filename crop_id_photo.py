"""
Crop a portrait photo into a proper 35x45mm ID/document photo, framed so the
head occupies a chosen fraction of the frame height (most official rules,
including Polish ones, want the chin-to-crown head height to be roughly
70-80% of the 45mm photo height).

This needs three pixel measurements from YOUR source photo, taken by eye in
any image viewer (e.g. macOS Preview: open the image, hover the cursor and
read the pixel position, or use the loupe/zoom):
  --hair-top       y of the top of the hair/head
  --chin           y of the bottom of the chin
  --face-center-x  x of the horizontal center of the face

There is no face detection here -- these three numbers are supplied by you.

Usage:
    python3 crop_id_photo.py SOURCE.heic --hair-top 83 --chin 1858 \\
        --face-center-x 1134 --out id_photo.jpg

    # generate 3 framings at once (head ~75% / ~68% / ~63% of frame height)
    # to compare, instead of a single --ratio/--crop-top:
    python3 crop_id_photo.py SOURCE.heic --hair-top 83 --chin 1858 \\
        --face-center-x 1134 --out id_photo.jpg --variants
"""
import argparse
from PIL import Image

try:
    import pillow_heif
    pillow_heif.register_heif_opener()  # lets Image.open() read .heic/.heif directly
except ImportError:
    pass

DPI = 600
MM_W, MM_H = 35, 45


def crop_id_photo(source, hair_top, chin, face_center_x, ratio=0.68, crop_top=None, out_path="id_photo_35x45.jpg"):
    """ratio: target fraction of the 45mm frame height occupied by the head
    (hair-top to chin). crop_top: y where the crop window starts; defaults
    to a small, sensible headroom above hair_top."""
    im = Image.open(source).convert("RGB")
    head_h = chin - hair_top
    if head_h <= 0:
        raise ValueError("--chin must be greater than --hair-top")

    crop_h = int(round(head_h / ratio))
    crop_w = int(round(crop_h * MM_W / MM_H))

    if crop_top is None:
        crop_top = max(0, hair_top - int(round(0.03 * crop_h)))

    crop_left = int(round(face_center_x - crop_w / 2))
    crop_left = max(0, min(crop_left, im.width - crop_w))
    crop_bottom = crop_top + crop_h
    crop_right = crop_left + crop_w

    if crop_right > im.width or crop_bottom > im.height or crop_top < 0:
        raise ValueError(
            f"requested crop ({crop_left},{crop_top},{crop_right},{crop_bottom}) "
            f"exceeds source image bounds ({im.width}x{im.height}); "
            f"try a higher --ratio (less zoomed out) or lower --crop-top"
        )

    face = im.crop((crop_left, crop_top, crop_right, crop_bottom))
    px_w = int(round(MM_W / 25.4 * DPI))
    px_h = int(round(MM_H / 25.4 * DPI))
    face = face.resize((px_w, px_h), Image.LANCZOS)
    face.save(out_path, dpi=(DPI, DPI), quality=95)
    print(f"ratio={ratio} crop_top={crop_top} -> {out_path} ({face.size[0]}x{face.size[1]}px @ {DPI}dpi)")
    return out_path


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source")
    parser.add_argument("--hair-top", type=int, required=True, help="y pixel of top of hair/head")
    parser.add_argument("--chin", type=int, required=True, help="y pixel of bottom of chin")
    parser.add_argument("--face-center-x", type=int, required=True, help="x pixel of horizontal face center")
    parser.add_argument("--ratio", type=float, default=0.68, help="head-height fraction of frame (default 0.68)")
    parser.add_argument("--crop-top", type=int, default=None, help="y where crop starts (default: small headroom above --hair-top)")
    parser.add_argument("--out", default="id_photo_35x45.jpg")
    parser.add_argument("--variants", action="store_true",
                         help="generate 3 files (ratio 0.75/0.68/0.63) instead of one")
    args = parser.parse_args()

    if args.variants:
        stem, dot, ext = args.out.rpartition(".")
        if not dot:
            stem, ext = args.out, "jpg"
        for label, ratio in (("tight", 0.75), ("medium", 0.68), ("zoomedout", 0.63)):
            crop_id_photo(args.source, args.hair_top, args.chin, args.face_center_x,
                           ratio=ratio, out_path=f"{stem}_{label}.{ext}")
    else:
        crop_id_photo(args.source, args.hair_top, args.chin, args.face_center_x,
                       ratio=args.ratio, crop_top=args.crop_top, out_path=args.out)


if __name__ == "__main__":
    main()
