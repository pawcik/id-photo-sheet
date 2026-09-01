"""
One-shot tool: turn one or more portrait photos into a printable 10x15cm
sheet of 35x45mm ID/document photos (6 slots, 2 columns x 3 rows, with
corner cut-mark guides), sized for kiosk printing (e.g. Rossmann in Poland,
whose standard print format is 10x15cm / 3:2).

Three ways to feed it a photo:

1. PRECISE (recommended for a real document photo) -- give the pixel
   coordinates of the hairline, chin, and face center (read them off the
   photo in any image viewer: macOS Preview, hover the cursor, etc.):

     --photo SOURCE HAIR_TOP CHIN FACE_CENTER_X

   The crop is framed so the head occupies --zoom of the 45mm frame height
   (most official rules, including Polish ones, want ~70-80%). Repeat
   --photo for more than one person; the 6 slots split evenly across them.

2. AUTO -- like precise mode, but the hairline/chin/face-center landmarks
   are estimated for you via face detection (OpenCV) instead of measured by
   hand. Takes bare image paths (like quick mode), plus the --auto flag:

     --auto SOURCE [SOURCE2 ...]

   Then runs through the exact same precise-mode crop math, so it also aims
   to satisfy gov.pl's two main rules: head height in the 70-80% range
   (--zoom, default 0.75 here) and the full head-plus-upper-shoulders
   framing (baked into that same crop math). Needs
   opencv-python-headless (pip install -r requirements-validate.txt).
   Approximate, like --validate below -- always double-check the result.

   If the requested --zoom doesn't fit the source photo (not enough margin
   around the detected face -- common with an already-tightly-cropped
   source image), --auto zooms in further automatically until it fits,
   prints what it adjusted to, and reports PASS/WARN against the *actual*
   zoom used. This can't always land inside 70-80%: a source photo with too
   little margin may force a result above 80% no matter how far it's
   zoomed in, since zooming in is the only direction that can still fit
   (there's no way to "zoom out" past the edges of the source). Precise
   mode does NOT do this -- an out-of-bounds --photo/--zoom combination
   still raises an error there, since the fix is for you to pick different
   numbers, not for the tool to silently override them.

3. QUICK (no measuring, default) -- just pass bare image paths, assuming
   each photo is more or less just the portrait (subject roughly centered,
   like a typical selfie/headshot). It crops straight to the 35:45 aspect
   ratio instead of stretching. This is NOT face-aware, so head size and
   position aren't guaranteed to meet any document-photo rule -- but you can
   play with --zoom (crop in tighter) and --crop-bias (shift the crop up or
   down) until it looks right.

   In quick mode, the two baseline ("do nothing extra") values are:
     --zoom 1.0        no extra zoom -- the largest 35:45 crop that fits
                        the source untouched (this IS the default)
     --crop-bias 0.5   centered -- no upward/downward shift (this IS the
                        default too; 0.5 is the neutral value, NOT 1.0 --
                        --crop-bias 1.0 means "push the crop all the way to
                        the bottom", it is not a no-op)

--variants generates several sheets at once instead of one, so you can
compare framing levels before printing. Pass it a comma-separated list to
sweep custom values instead of the built-in default sweep -- each entry is
either ZOOM alone, or CROP_BIAS-ZOOM to vary both together. In QUICK mode,
every zoom value in that list must be >= 1.0 (same rule as --zoom itself --
quick mode can only crop tighter than the original photo, never "zoom out"
past it); in PRECISE mode zoom is a 0-1 fraction instead (see above), so
that constraint doesn't apply there.

Examples:
    # quick mode: no landmarks, raw photos straight in, one photo -> 6 copies
    python3 id_photo_sheet.py out.jpg photo.heic

    # two photos -> 3 copies of each
    python3 id_photo_sheet.py out.jpg bonnie.heif clyde.heif

    # zoom in (crop tighter into the center) and nudge the crop upward
    python3 id_photo_sheet.py out.jpg photo.heic --zoom 1.3 --crop-bias 0.2

    # compare 3 crop positions (top/center/bottom) at once
    python3 id_photo_sheet.py out.jpg photo.heic --variants

    # compare specific zoom levels instead (comma-separated list, any count)
    python3 id_photo_sheet.py out.jpg photo.heic --variants 1.1,1.2,1.3

    # sweep crop-bias and zoom together, per entry (CROP_BIAS-ZOOM); the
    # first entry (0.5-1.0) is the baseline/no-op case, for comparison
    # against the two zoomed-in, downward-biased variants after it
    python3 id_photo_sheet.py out.jpg photo.heic --variants 0.5-1.0,0.65-1.1,0.84-1.2

    # precise mode: exact pixel landmarks instead of guessing
    python3 id_photo_sheet.py out.jpg --photo me.heic 83 1858 1134
    python3 id_photo_sheet.py out.jpg --photo me.heic 83 1858 1134 --zoom 0.75
    python3 id_photo_sheet.py out.jpg --photo me.heic 83 1858 1134 --variants 0.6,0.65,0.7,0.75

    # auto mode: no landmarks needed, face-detected instead (needs opencv)
    python3 id_photo_sheet.py out.jpg photo.heic --auto
    python3 id_photo_sheet.py out.jpg bonnie.heif clyde.heif --auto --zoom 0.78

    # no corner cut-mark guides (clean sheet, e.g. for a printer that adds its own)
    python3 id_photo_sheet.py out.jpg photo.heic --no-cut-marks

VALIDATING against the gov.pl rule that the head should fill 70-80% of the
photo height (https://www.gov.pl/web/gov/zdjecie-do-dowodu-lub-paszportu):

  - Precise and AUTO modes report this automatically, for free, every time
    they crop a photo -- --zoom IS the head-height fraction by construction
    (auto mode's is just estimated instead of measured), so it's a PASS/WARN
    against whatever --zoom was used, printed right when the crop happens.

  - --validate PHOTO [PHOTO2 ...] runs real face detection (OpenCV Haar
    cascade) on any already-cropped 35x45mm photo -- from this script's
    quick mode, or from anywhere else -- and estimates head-height coverage
    instead of just trusting the crop math. Needs opencv-python-headless
    (pip install opencv-python-headless); the estimate is approximate (a
    frontal-face cascade detects roughly eyebrows-to-chin, not the true
    hairline-to-chin head height, so a correction factor is applied) --
    treat it as a sanity check, not an authoritative pass/fail.

    python3 id_photo_sheet.py --validate sheet_photo.jpg
    python3 id_photo_sheet.py --validate photo1.jpg photo2.jpg
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
GOVPL_HEAD_HEIGHT_RANGE = (0.70, 0.80)  # gov.pl: head should fill 70-80% of frame height

# 2 * 35mm = 70mm <= 100mm and 3 * 45mm = 135mm <= 150mm, so 6 copies of a
# 35x45mm photo do fit on one 10x15cm sheet (tighter than the common 4-up
# layout, confirmed against Rossmann's own 10x15cm = 3:2 standard format).


def mm_to_px(mm):
    return int(round(mm / 25.4 * DPI))


PX_W, PX_H = mm_to_px(MM_W), mm_to_px(MM_H)


def crop_precise(source, hair_top, chin, face_center_x, zoom=0.68, crop_top=None, auto_fit=False):
    """zoom: fraction of the 45mm frame height the head (hair-top to chin)
    should occupy. Higher = zoomed in/tighter, lower = zoomed out.

    auto_fit: if the requested zoom's crop doesn't fit the source photo
    (not enough margin around the detected/given head), zoom in further
    (the only direction that can still fit -- there's no way to "zoom out"
    past the edges of the source) until it does, instead of raising. Used
    by --auto, where there are no manually-chosen landmarks to blame for
    the mismatch; precise mode (manual --photo) still raises, since there
    the fix is for the user to pick different numbers."""
    im = Image.open(source).convert("RGB")
    head_h = chin - hair_top
    if head_h <= 0:
        raise ValueError("chin must be below hair_top")

    crop_h = int(round(head_h / zoom))

    def geometry(crop_h):
        crop_w = int(round(crop_h * MM_W / MM_H))
        top = crop_top if crop_top is not None else max(0, hair_top - int(round(0.03 * crop_h)))
        left = int(round(face_center_x - crop_w / 2))
        left = max(0, min(left, im.width - crop_w))
        return left, top, left + crop_w, top + crop_h

    crop_left, top, crop_right, crop_bottom = geometry(crop_h)
    out_of_bounds = crop_right > im.width or crop_bottom > im.height or top < 0 or crop_left < 0

    if out_of_bounds and auto_fit:
        original_crop_h = crop_h
        while out_of_bounds and crop_h > 1:
            crop_h -= 1
            crop_left, top, crop_right, crop_bottom = geometry(crop_h)
            out_of_bounds = crop_right > im.width or crop_bottom > im.height or top < 0 or crop_left < 0
        if not out_of_bounds:
            new_zoom = head_h / crop_h
            print(f"{source}: requested zoom {zoom:.3f} needs more margin than this photo has "
                  f"-- auto-adjusted to zoom {new_zoom:.3f} (tightest crop that still fits)")
            zoom = new_zoom

    if out_of_bounds:
        raise ValueError(
            f"{source}: crop ({crop_left},{top},{crop_right},{crop_bottom}) "
            f"exceeds image bounds ({im.width}x{im.height}) -- try a higher "
            f"--zoom (less zoomed out) or a lower --crop-top"
        )

    lo, hi = GOVPL_HEAD_HEIGHT_RANGE
    status = "PASS" if lo <= zoom <= hi else "WARN"
    print(f"{source}: head height = {zoom * 100:.1f}% of frame "
          f"[{status}: gov.pl wants {lo * 100:.0f}-{hi * 100:.0f}%] "
          f"(exact -- this is precise mode, zoom IS the head-height fraction by construction)")

    face = im.crop((crop_left, top, crop_right, crop_bottom))
    return face.resize((PX_W, PX_H), Image.LANCZOS)


def crop_fallback(source, zoom=1.0, crop_bias=0.5):
    """No landmarks needed: crop straight to the 35:45 aspect ratio instead
    of stretching (assumes the subject is roughly centered in the photo,
    which holds for a typical selfie/portrait framing). Not face-aware, so
    head size/position aren't guaranteed to meet any document-photo rule.

    zoom: 1.0 = the largest 35:45 box that fits inside the source (as
    "zoomed out" as this can go); >1.0 crops a smaller, centered region and
    scales it up, i.e. zooms in (2.0 = crop half the width/height).
    crop_bias: where that box sits in the leftover vertical space when the
    source is wider than 35:45 relative to it (0=top, 0.5=centered, 1=bottom).
    """
    if zoom < 1.0:
        raise ValueError("--zoom must be >= 1.0 in quick mode (can't zoom out past the original photo)")
    img = Image.open(source).convert("RGB")
    w, h = img.size
    ratio = w / h

    # largest 35:45 box that fits fully inside the source
    if ratio > TARGET_RATIO:
        max_w, max_h = int(round(h * TARGET_RATIO)), h
    else:
        max_w, max_h = w, int(round(w / TARGET_RATIO))

    box_w = max(1, int(round(max_w / zoom)))
    box_h = max(1, int(round(max_h / zoom)))
    left = int(round((w - box_w) * 0.5))
    top = int(round((h - box_h) * crop_bias))
    left = max(0, min(left, w - box_w))
    top = max(0, min(top, h - box_h))

    print(f"{source}: {w}x{h} -> box {box_w}x{box_h} at ({left},{top}), "
          f"zoom={zoom}, crop_bias={crop_bias} (not face-aware)")
    img = img.crop((left, top, left + box_w, top + box_h))
    return img.resize((PX_W, PX_H), Image.LANCZOS)


# A frontal-face Haar cascade typically detects a box spanning roughly
# eyebrows-to-chin, not the true hairline-to-chin head height gov.pl means.
# This factor scales the detected box up to approximate the full head
# height. It's an empirical rule of thumb, not a measured constant --
# treat the result as a sanity check, not an authoritative pass/fail.
FACE_TO_HEAD_HEIGHT_CORRECTION = 1.3

AUTO_DEFAULT_ZOOM = 0.75  # middle of the gov.pl 70-80% range, used as --auto's default --zoom


def _require_cv2(flag_name):
    try:
        import cv2
        return cv2
    except ImportError:
        raise SystemExit(f"{flag_name} needs opencv-python-headless: "
                          f"pip install -r requirements-validate.txt")


def _detect_largest_face(path, flag_name):
    """Returns (x, y, w, h, img_w, img_h) of the largest detected frontal
    face box in `path`, or None if no face was found."""
    cv2 = _require_cv2(flag_name)
    import numpy as np
    # load via PIL (which has HEIF/HEIC support registered above) rather
    # than cv2.imread, which can't read HEIF at all
    pil_img = Image.open(path).convert("RGB")
    img = np.array(pil_img)  # RGB
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5,
                                      minSize=(int(w * 0.2), int(h * 0.2)))
    if len(faces) == 0:
        return None
    fx, fy, fw, fh = max(faces, key=lambda f: f[2] * f[3])
    return fx, fy, fw, fh, w, h


def auto_landmarks(path):
    """Estimate (hair_top, chin, face_center_x) for crop_precise() from face
    detection alone -- no manual measuring. The cascade box approximates
    eyebrows-to-chin, not the true hairline-to-chin head height, so the
    extra height (from FACE_TO_HEAD_HEIGHT_CORRECTION) is added above the
    box, extending it upward through the forehead toward the hairline;
    the box bottom is used as-is for the chin. This is an approximation."""
    detected = _detect_largest_face(path, "--auto")
    if detected is None:
        raise ValueError(f"{path}: no face detected -- can't auto-crop, use precise mode instead")
    fx, fy, fw, fh, w, h = detected
    est_head_h = fh * FACE_TO_HEAD_HEIGHT_CORRECTION
    hair_top = max(0, int(round(fy - (est_head_h - fh))))
    chin = int(round(fy + fh))
    face_center_x = int(round(fx + fw / 2))
    print(f"{path}: auto-detected face box {fw}x{fh} at ({fx},{fy}) -- "
          f"estimated hair_top={hair_top} chin={chin} face_center_x={face_center_x} (approximate)")
    return hair_top, chin, face_center_x


def validate_face_coverage(path):
    """Detect the face in `path` (any image, not necessarily 35x45mm) and
    estimate what fraction of the frame height the head occupies, printing
    a PASS/WARN against the gov.pl 70-80% rule. Returns the estimated
    fraction, or None if no face was detected."""
    detected = _detect_largest_face(path, "--validate")
    if detected is None:
        print(f"{path}: no face detected -- can't validate")
        return None
    _, _, _, face_h, _, h = detected

    raw_fraction = face_h / h
    est_fraction = min(1.0, raw_fraction * FACE_TO_HEAD_HEIGHT_CORRECTION)

    lo, hi = GOVPL_HEAD_HEIGHT_RANGE
    status = "PASS" if lo <= est_fraction <= hi else "WARN"
    print(f"{path}: detected face height = {raw_fraction * 100:.1f}% of frame -> "
          f"estimated head height (hairline-to-chin) ~= {est_fraction * 100:.1f}% "
          f"[{status}: gov.pl wants {lo * 100:.0f}-{hi * 100:.0f}%] (approximate, not authoritative)")
    return est_fraction


def build_sheet(cropped_images, out_path, copies=None, cut_marks=True):
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
            if cut_marks:
                corners = [(x, y), (x + PX_W, y), (x, y + PX_H), (x + PX_W, y + PX_H)]
                for (cx, cy) in corners:
                    dx = -1 if cx == x else 1
                    dy = -1 if cy == y else 1
                    draw.line([(cx, cy), (cx + dx * mark_len, cy)], fill=mark_col, width=2)
                    draw.line([(cx, cy), (cx, cy + dy * mark_len)], fill=mark_col, width=2)
            idx += 1

    sheet.save(out_path, dpi=(DPI, DPI), quality=95)
    print(f"copies per photo: {copies} -> {out_path} ({sheet.size[0]}x{sheet.size[1]}px @ {DPI}dpi)")


def make_sheet(precise_photos, quick_photos, out_path, zoom=None, crop_bias=0.5, cut_marks=True, auto_fit=False):
    if precise_photos:
        images = [crop_precise(path, hair_top, chin, face_x, zoom=zoom if zoom is not None else 0.68, auto_fit=auto_fit)
                  for (path, hair_top, chin, face_x) in precise_photos]
    else:
        images = [crop_fallback(path, zoom=zoom if zoom is not None else 1.0, crop_bias=crop_bias)
                  for path in quick_photos]
    build_sheet(images, out_path, cut_marks=cut_marks)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("out_path", nargs="?", help="output sheet path (not used with --validate)")
    parser.add_argument("photos", nargs="*", help="quick mode: bare image paths (no landmarks)")
    parser.add_argument("--photo", dest="precise_photos", action="append", nargs=4,
                         metavar=("PATH", "HAIR_TOP", "CHIN", "FACE_CENTER_X"),
                         help="precise mode: source path + pixel landmarks (repeatable)")
    parser.add_argument("--zoom", "--ratio", dest="zoom", type=float, default=None,
                         help="precise mode: head-height fraction of frame (default 0.68); "
                              "higher = zoomed in, lower = zoomed out. "
                              "quick mode: >=1.0 zoom-in factor (default 1.0 = no extra zoom)")
    parser.add_argument("--crop-bias", type=float, default=0.5,
                         help="quick mode only: where the crop sits vertically -- "
                              "0=top, 0.5=centered (default), 1=bottom")
    parser.add_argument("--variants", nargs="?", const="__default__", default=None,
                         help="generate multiple sheets instead of one, to compare framing. "
                              "Bare --variants uses the default sweep (quick mode: crop-bias "
                              "top/center/bottom; precise mode: zoom 0.75/0.68/0.63). Or pass "
                              "a comma-separated list to sweep custom values: each entry is "
                              "either ZOOM alone (crop-bias stays fixed at --crop-bias), e.g. "
                              "--variants 1.1,1.2,1.3, or CROP_BIAS-ZOOM to vary both together, "
                              "e.g. --variants 0.5-1.0,0.65-1.1,0.84-1.2 (0.5-1.0 there is the "
                              "quick-mode baseline/no-op: bias 0.5=centered, zoom 1.0=no extra "
                              "zoom -- NOT 1.0 for bias, which means fully bottom-shifted). "
                              "In quick mode every ZOOM in this list must be >= 1.0, same as "
                              "plain --zoom")
    parser.add_argument("--cut-marks", action=argparse.BooleanOptionalAction, default=True,
                         help="draw corner cut-mark guides around each photo (default: on). "
                              "Use --no-cut-marks to get a clean sheet with no guides")
    parser.add_argument("--validate", nargs="+", metavar="PHOTO", default=None,
                         help="validate one or more photos against the gov.pl 70-80%% "
                              "head-height rule via face detection, instead of building a "
                              "sheet (requires opencv-python-headless). No out_path needed")
    parser.add_argument("--auto", action="store_true",
                         help="auto-detect face landmarks (via OpenCV face detection) instead "
                              "of needing --photo's manual pixel coordinates, then crop through "
                              "the same precise-mode math -- meets gov.pl's head-height (--zoom, "
                              "default 0.75) and full-head-plus-shoulders framing rules without "
                              "measuring anything by hand. Approximate, like --validate: double"
                              "-check the result. Requires opencv-python-headless; takes bare "
                              "image paths, not --photo")
    args = parser.parse_args()

    if args.validate:
        for path in args.validate:
            validate_face_coverage(path)
        return

    if args.out_path is None:
        parser.error("out_path is required unless using --validate")

    if args.auto:
        if args.precise_photos:
            parser.error("--auto and --photo are mutually exclusive -- --auto detects its own landmarks")
        if not args.photos:
            parser.error("--auto needs one or more bare image paths")
        precise_photos = [(path, *auto_landmarks(path)) for path in args.photos]
        quick_photos = []
    elif args.precise_photos:
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

    def try_make_sheet(*a, **kw):
        """Like make_sheet, but in a --variants sweep one out-of-bounds zoom
        (common with --auto on a close-up photo, where the estimated head
        height leaves little room to zoom out further) shouldn't abort the
        other variants -- skip it and keep going."""
        try:
            make_sheet(*a, **kw)
        except ValueError as e:
            print(f"skipping variant: {e}")

    if args.variants == "__default__":
        if precise_photos:
            for label, zoom in (("tight", 0.75), ("medium", 0.68), ("zoomedout", 0.63)):
                try_make_sheet(precise_photos, quick_photos, f"{stem}_{label}.{ext}", zoom=zoom, cut_marks=args.cut_marks, auto_fit=args.auto)
        else:
            for label, bias in (("top", 0.15), ("center", 0.5), ("bottom", 0.85)):
                try_make_sheet(precise_photos, quick_photos, f"{stem}_{label}.{ext}", zoom=args.zoom, crop_bias=bias, cut_marks=args.cut_marks)
    elif args.variants is not None:
        for token in args.variants.split(","):
            token = token.strip()
            if "-" in token:
                bias_str, zoom_str = token.split("-", 1)
                try:
                    bias, zoom = float(bias_str), float(zoom_str)
                except ValueError:
                    parser.error(f"--variants entries must be ZOOM or CROP_BIAS-ZOOM numbers, got {token!r}")
                label = f"bias{bias}_zoom{zoom}".replace(".", "p")
            else:
                try:
                    zoom = float(token)
                except ValueError:
                    parser.error(f"--variants entries must be ZOOM or CROP_BIAS-ZOOM numbers, got {token!r}")
                bias = args.crop_bias
                label = f"zoom{zoom}".replace(".", "p")
            try_make_sheet(precise_photos, quick_photos, f"{stem}_{label}.{ext}", zoom=zoom, crop_bias=bias, cut_marks=args.cut_marks, auto_fit=args.auto)
    else:
        zoom = args.zoom
        if zoom is None and args.auto:
            zoom = AUTO_DEFAULT_ZOOM
        make_sheet(precise_photos, quick_photos, args.out_path, zoom=zoom, crop_bias=args.crop_bias, cut_marks=args.cut_marks, auto_fit=args.auto)


if __name__ == "__main__":
    main()
