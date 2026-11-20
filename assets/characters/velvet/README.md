# Velvet: the owner's female character (from 2026-11-20)

Blanket's companion. Personality and role: `docs/CHARACTERS.md` (cheerful, curious, expressive; Blanket is the calm
one). Design, from the owner's own images: gray skin, a faceless oval head with only two round glowing white eyes (no
mouth, no nose), a long golden-blonde high ponytail through the back of a plain navy cap, a dark purple short-sleeve
crop top, dark purple shorts, pink over-ear headphones, a pink smartwatch, white crew socks and white sneakers, and
sometimes a pink tumbler with a straw. First used in r029 (scene s2b). Voice (owner's choice, 2026-11-20): ElevenLabs
«Nora S - Saudi Natural & Calm», voice_id `FZeLZd39ejvLgzR2gY0t`, model `eleven_v4`.

## The owner's sheets (`sheets/`, as he sent them)

- `front.jpg`: main front view with accessory details (source of `reference_front.png` and
  `images/refs/female_front_dark_headroom.png`).
- `turnaround.jpg`: front and back views, accessories, silhouettes.
- `exercises.jpg`: squat, push-ups, glute exercises, side lunge.
- `poses1.jpg`, `poses_outfit.jpg`: everyday poses; `poses_outfit.jpg` also has the outfit details
  (copied to `outfit_details.jpg`). The details panel draws the top sleeveless; the poses and the front view draw
  short sleeves, which is the look to keep.
- `fitness1.jpg`, `fitness2.jpg`: fitness and stretching poses.

## 9:16 references for image editing

Cleaned 720x1280 references on the series' dark background (labels, panel borders and neighbouring figures removed),
for `scripts/image_job.py` entries with `"reference"` (Qwen/Qwen-Image-Edit-2509, as for Blanket):

- `reference_front.png`: standard front view; `images/refs/female_front_dark_headroom.png` when a scene has an overlay.
- Exercises (`move_<name>.png`): `squat`, `pushup`, `pushup_incline` (hands on a box), `plank`, `donkey_kick`,
  `glute_bridge`, `side_lunge`, `warmup_lunge`, `run`, `quad_stretch`, `side_stretch`, `cobra`, `seated_twist`,
  `band` (standing with a resistance band).
- Poses (`pose_<name>.png`): `front`, `back`, `power_stance`, `cap_touch`, `jump`, `dance_kick`, `handstand`,
  `sit_floor`, `sit_stool`, `sit_chair`, `kneel`, `lean_wall`, `rest_bench` (towel and tumbler), `selfie`,
  `look_back`.

Rules for her scenes: blank face apart from the eyes (the close-up "intense focus" panel adds brows and a mouth line,
so it is not used), no labels or text in the image, plain unmarked props (her phone and earbuds stay generic, never a
recognisable brand), expressive and dynamic poses that suit her personality.

Kept out of the references: the unclothed anatomy figures, the two rear-focused poses, the silhouettes, the joint rig
and the fire hydrants on the exercise sheet. The account is family-friendly, and Instagram lists "content that may be
sexually suggestive" among content that may not be eligible for recommendations
([Instagram Creators](https://creators.instagram.com/recommendations-and-originality)), which is how Reels reach
people who do not follow the account.
