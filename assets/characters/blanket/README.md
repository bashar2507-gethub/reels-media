# The Blanket — the owner's character (from 2026-10-24)

- `sheet.jpg`: character sheet (navy cap with a B, whistle on a cord, khaki cargo shorts, faceless gray head with two round white eyes).
- `anatomy_sheet.jpg`: muscle-anatomy supplement; use it for scenes about specific muscles.
- `reference_front.png`, `reference_anatomy.png`: 9:16 references for image editing.

Scene images are made with `scripts/image_job.py` (entries with `"reference"`), model Qwen/Qwen-Image-Edit-2509
(Apache-2.0) through Hugging Face, then used in a script with `"image_file"`. Keep the face blank apart from the eyes
(no mouth or nose), no labels or text in the image, and put on-screen figures above the head (`"y": 330`).
First used in r005.
