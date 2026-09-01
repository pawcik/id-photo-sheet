# id-photo-sheet

Turn one or more portrait photos (JPEG/PNG/HEIC/HEIF) into a print-ready
sheet of 35x45mm ID/document photos: 6 copies laid out on one 10x15cm page,
with cut-mark guides, sized for self-service photo kiosks (e.g. Rossmann in
Poland, whose standard print format is 10x15cm / 3:2).

Everything lives in a single script, `id_photo_sheet.py`, no face-detection
dependency.

## Requirements

- Python 3.9+
- macOS, Linux, or Windows -- nothing OS-specific, no `sips`/ImageMagick needed

## Setup on a bare machine

```bash
git clone <this-repo-url> id-photo-sheet
cd id-photo-sheet
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

There are two ways to feed it a photo.

### Precise mode (recommended for a real document photo)

Open your source photo in any image viewer that shows pixel coordinates
(macOS Preview: hover the cursor, or Tools > Show Inspector; GIMP; etc.) and
note three values: the y of the top of the hair/head, the y of the bottom of
the chin, and the x of the horizontal center of the face. Then:

```bash
python3 id_photo_sheet.py sheet.jpg --photo me.heic 83 1858 1134
```

(`--photo PATH HAIR_TOP CHIN FACE_CENTER_X`, repeatable.) The crop is framed
so the head fills `--zoom` of the 45mm frame height -- default `0.68`, a
reasonable middle ground for most official rules, which typically want
70-80%. Higher = zoomed in/tighter, lower = zoomed out:

```bash
python3 id_photo_sheet.py sheet.jpg --photo me.heic 83 1858 1134 --zoom 0.75
```

Give it more than one `--photo` and the 6 slots split evenly across them,
filled in order (two photos -> 3 copies each, then 3 of the next):

```bash
python3 id_photo_sheet.py sheet.jpg \
  --photo kasia.heif 289 1991 1110 \
  --photo pawel.heif 83 1858 1134 \
  --zoom 0.65
```

Add `--variants` to generate 3 sheets at once (zoom 0.75 / 0.68 / 0.63,
suffixed `_tight` / `_medium` / `_zoomedout`) instead of picking one zoom
level up front:

```bash
python3 id_photo_sheet.py sheet.jpg --photo me.heic 83 1858 1134 --variants
# -> sheet_tight.jpg / sheet_medium.jpg / sheet_zoomedout.jpg
```

### Quick mode (casual reprints, no measuring)

Just pass bare image paths, no `--photo`/landmarks:

```bash
python3 id_photo_sheet.py sheet.jpg kasia.heif pawel.heif
```

Each photo that isn't already 35x45mm-shaped gets center-cropped to that
aspect ratio instead of stretched (a warning is printed). This is **not**
face-aware -- head size and position aren't guaranteed to meet any
document-photo rule, so use precise mode for anything you'll actually submit.

`--crop-bias` (0.0-1.0, default 0.5) controls where that fallback crop is
taken from: `0` keeps the top/left, `1` keeps the bottom/right. `--variants`
here generates 3 sheets (`_top` / `_center` / `_bottom`, bias 0.15/0.5/0.85):

```bash
python3 id_photo_sheet.py sheet.jpg photo.heic --crop-bias 0.2
python3 id_photo_sheet.py sheet.jpg photo.heic --variants
```

### Print

Take the resulting sheet (10x15cm, 600 DPI) to a Rossmann photo kiosk (or
any photo printer) and print it at the standard **10x15cm** size. Cut along
the corner guide marks to separate the 6 individual 35x45mm photos.

## Notes / limitations

- No face-detection: precise-mode landmarks are measured by eye. For a real
  submitted document photo (dowod osobisty, wniosek, etc.), double-check the
  result against the current official requirements (neutral expression,
  mouth closed, eyes open, plain light background, correct head-height
  proportion) before relying on it.
- Quick mode's fallback aspect-ratio crop is a convenience for casual
  reprints, not a substitute for precise mode when framing actually matters.
