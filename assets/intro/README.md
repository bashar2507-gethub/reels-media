# THE BLANKET EFFECT

`blanket_effect.mp4`: the 1.8 s signature intro for every Reel (1080x1920, 30 fps, H.264 + AAC).
Built by `scripts/build_intro.py` from `images/intro-frames/` (a_dormant, b_ignite, c_lunge; The Blanket made from
the owner's character sheet with Qwen-Image-Edit-2509, Apache-2.0). Beats: 0-0.7 s dark and still; 0.7-1.05 s eyes
ignite golden-white; 1.05-1.45 s lunge toward the camera (push, motion blur, shake) on a synthesised sub-bass impact
after a noise whoosh; 1.45-1.8 s golden-white flash. `app/intro.py` prepends it with a 0.2 s transition, so the
Reel's own content starts 1.667 s later. Keep this file fixed so every Reel opens the same way.
