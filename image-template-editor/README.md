# Template Studio — reusable image template editor

A single-file, offline web app for turning a Photopea (or Photoshop) design into a
reusable template: load the design's exported PNG once, position a photo frame and
text fields (name, district, …) on top of it, and from then on producing a new image
is just *upload photo → type values → Download PNG*.

## One-time setup

1. Open your design in Photopea (e.g. `https://www.photopea.com/#tCLSNP8JM`).
2. Hide the sample photo and sample text layers (click their eye icons), so only the
   background/frame artwork remains.
3. **File → Export As → PNG** at full size.
4. Open `index.html` in any browser and load that PNG with **Load template**
   (or drop it on the canvas).
5. Drag the dashed **photo frame** over the spot where pictures go (corner handles
   resize it). Drag each text into place; use **+ Add field** for extra lines.
6. If the design uses a specific font, load its `.ttf`/`.otf` file with **+ Font file**
   so exports match exactly.

The layout is saved automatically in the browser (localStorage). **Export pack**
downloads a portable `.json` containing the template image, fonts and layout so the
setup can be moved to another browser or shared.

## Everyday use

1. **Upload photo** — it is cover-fitted into the frame; use *Adjust crop* + the zoom
   slider to frame it.
2. Edit the **Name** / **District** values in the Text section.
3. **Download PNG** (or JPG). The file exports at the template's full resolution and
   is named from the text values, e.g. `JANE-DOE-DISTRICT-5.png`.

Tips: templates exported *with a transparent photo window* should tick
**Photo behind template** so the artwork frames the photo. Arrow keys nudge the
selected item (Shift = 10 px). Everything runs locally — no uploads, no server.
