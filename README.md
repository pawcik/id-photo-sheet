# id-photo-sheet

Turn a portrait photo (JPEG/PNG/HEIC/HEIF) into print-ready 35x45mm ID/document
photo sheets: 6 copies laid out on one 10x15cm page, with cut-mark guides, sized
for self-service photo kiosks (e.g. Rossmann in Poland, whose standard print
format is 10x15cm / 3:2).

Two small scripts, no face-detection dependency:

- `crop_id_photo.py` -- crop one source photo into a proper 35x45mm ID photo,
  given the pixel coordinates of the hairline, chin, and face center (you
  supply these by eye from any image viewer).
- `compose_sheet.py` -- tile one or more 35x45mm photos onto a 10x15cm sheet
  (6 slots, 2 columns x 3 rows), splitting the 6 copies evenly across however
  many input photos you give it.

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

### 1. Find the crop landmarks

Open your source photo in any image viewer that shows pixel coordinates
(macOS Preview: hover the cursor, or use Tools > Show Inspector; GIMP; etc.)
and note three values:

- `--hair-top`: y pixel of the top of the hair/head
- `--chin`: y pixel of the bottom of the chin
- `--face-center-x`: x pixel of the horizontal center of the face

### 2. Crop to a 35x45mm ID photo

```bash
python3 crop_id_photo.py photo.heic \
  --hair-top 83 --chin 1858 --face-center-x 1134 \
  --out id_photo.jpg
```

By default the head fills about 68% of the 45mm frame height (a reasonable
middle ground for most official document-photo rules, which typically call
for 70-80%). Adjust with `--ratio` (e.g. `0.75` = tighter/closer, `0.6` =
more zoomed out), or generate three framings at once to compare:

```bash
python3 crop_id_photo.py photo.heic \
  --hair-top 83 --chin 1858 --face-center-x 1134 \
  --out id_photo.jpg --variants
# -> id_photo_tight.jpg / id_photo_medium.jpg / id_photo_zoomedout.jpg
```

### 3. Compose the printable 10x15cm sheet

```bash
python3 compose_sheet.py sheet.jpg id_photo.jpg
```

One photo fills all 6 slots. Give it more than one photo and the 6 copies
split evenly across them, filled in order (two photos -> 3 copies each; three
photos -> 2 copies each; etc.):

```bash
python3 compose_sheet.py sheet.jpg kasia_id.jpg pawel_id.jpg
# -> 3 copies of kasia_id.jpg, then 3 copies of pawel_id.jpg
```

`compose_sheet.py` also accepts raw, uncropped photos directly (including
`.heic`/`.heif`) -- if the input isn't already 35x45mm-shaped, it center-crops
to that aspect ratio instead of stretching it, and prints a warning. That
fallback crop is **not** face-aware, so for an actual document photo, always
run it through `crop_id_photo.py` first.

Use `--crop-bias` (0.0-1.0, default 0.5) to control where that fallback crop
is taken from when it isn't a pre-made 35x45mm image: `0` keeps the top/left,
`1` keeps the bottom/right. Or use `--variants` to generate three sheets at
once (`_top` / `_center` / `_bottom`) to compare:

```bash
python3 compose_sheet.py sheet.jpg photo.heic --crop-bias 0.2
python3 compose_sheet.py sheet.jpg photo.heic --variants
```

### 4. Print

Take the resulting `sheet.jpg` (10x15cm, 600 DPI) to a Rossmann photo kiosk
(or any photo printer) and print it at the standard **10x15cm** size. Cut
along the corner guide marks to separate the 6 individual 35x45mm photos.

## Notes / limitations

- No face-detection: the crop landmarks in step 1 are measured by eye. For a
  real submitted document photo (dowod osobisty, wniosek, etc.), double-check
  the result against the current official requirements (neutral expression,
  mouth closed, eyes open, plain light background, correct head-height
  proportion) before relying on it.
- `compose_sheet.py`'s fallback aspect-ratio crop for raw/uncropped inputs is
  a convenience for casual reprints, not a substitute for `crop_id_photo.py`
  when framing actually matters.
