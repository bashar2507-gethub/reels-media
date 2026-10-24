# fitness-reels

خط إنتاج Reels عربية علمية عن اللياقة: تركيب الفيديو، والترجمة العربية، وبوابة التحقق قبل الجدولة.

## الحالة

- **PoC-1 (هذا الإصدار):** تركيب فيديو 1080×1920 مع ترجمة عربية تُبرز الكلمة المنطوقة، وبوابة وسائط من 27 فحصًا. يعمل دون مفاتيح أو اتصال خارجي.
- **PoC-1 معتمد:** اعتمده صاحب الحساب للنشر في 16 أكتوبر 2026. الخطوات والإعدادات المعتمدة في `docs/APPROVED_STEPS.md`.
- **PoC-2 (التالي):** صور FLUX.1-schnell وفيديو CogVideoX-5B عبر Hugging Face Inference Providers، وصوت ElevenLabs، ورفع الوسائط إلى Cloudflare R2.
- الجدولة عبر موصل Metricool في Claude، لأن خطة Metricool المجانية لا تتيح الـ API.

## التشغيل

المتطلبات: Python 3.11 أو أحدث، وFFmpeg مبني مع libass (مع HarfBuzz وFriBidi)، وespeak-ng للصوت المؤقت فقط.

```bash
pip install -r requirements.txt
python -m pytest
python scripts/run_poc1.py
```

المخرجات في `output/poc1/`: الفيديو، والغلاف، و`captions.ass`، و`timeline.json`، و`media_gate.json`.

## الصوت (ElevenLabs)

```bash
python scripts/run_poc1.py --tts elevenlabs --estimate-only   # الأحرف والرصيد المتوقع، دون أي اتصال
python scripts/run_poc1.py --tts elevenlabs                   # يتطلب ELEVENLABS_API_KEY وخطة مدفوعة
python scripts/run_poc1.py --narration content/audio/poc1_narration_words.json   # سرد مولّد مسبقًا مع توقيت كلماته
python scripts/run_poc1.py --narration content/audio/poc1_narration_words.json --out output/poc1_release --release   # نسخة النشر: دون ملصق الاختبار
```

- الإيقاع: تُضاف توقفات عند حدود الجمل (0.40 ث) والمشاهد (0.70 ث) في أهدأ نقطة بين الكلمات، دون تمطيط الصوت أو تغيير سرعته (`--sentence-gap` و`--scene-gap`).
- الكلمات القصيرة جدًا (في، مع، قد) تُضاء مع الكلمة التالية، فلا يقل الإبراز عن 0.15 ثانية.

- الواجهة الرسمية `POST /v1/text-to-speech/{voice_id}/with-timestamps`، ومنها توقيت كل كلمة لمزامنة الترجمة.
- الصوت «Jeddawi Echo» `yXEnnEln9armDCyhkXcA` (منذ 24 أكتوبر 2026، بدل «عبدالله سعدون»)، والنموذج `eleven_v4`.
- السرد كاملًا في طلب واحد، فالتوقفات والتنغيم من الصوت نفسه. لا يُسرَّع الصوت لملاءمة المدة؛ المدة خارج 25–30 ثانية تظهر تحذيرًا فقط.
- المفتاح من `ELEVENLABS_API_KEY` فقط (GitHub Secrets، أو ملف `.env` محلي لا يُرفع). لا يُطبع ولا يُكتب في أي سجل أو رسالة خطأ.
- إعادة المحاولة لأخطاء 429 و5xx فقط؛ أخطاء المصادقة والخطة تُوقف التشغيل فورًا.

## البنية

| الملف | الوظيفة |
| --- | --- |
| `app/config.py` | مواصفات الفيديو والمسارات |
| `app/tts.py` | طبقة صوت قابلة للاستبدال: ElevenLabs للإنتاج، وespeak-ng مؤقت للاختبار فقط |
| `app/audio_metrics.py` | قياس سرعة النطق والتوقفات وحركة النغمة |
| `app/timeline.py` | توقيت الجمل والمشاهد، وتقسيم الترجمة إلى مقاطع طبيعية |
| `app/subtitles.py` | ترجمة ASS عربية مع إبراز الكلمة المنطوقة والمصطلحات الإنجليزية |
| `app/motion.py` | حركة Ken Burns ناعمة للصور الثابتة |
| `app/placeholders.py` | خلفيات مؤقتة للتشغيل التجريبي |
| `app/video_assembler.py` | التركيب والترميز بمواصفات Reels |
| `app/validation.py` | بوابة الوسائط مقابل مواصفات Instagram وMetricool |
| `app/caption_qa.py` | فحص آلي لاتجاه الترجمة العربية من اليمين إلى اليسار |

## ملاحظات

- الترجمة تستخدم `Encoding=-1` في أنماط ASS؛ القيمة الافتراضية تجعل libass يرتب الكلمات الملونة من اليسار إلى اليمين. `caption_qa` يكشف ذلك تلقائيًا.
- الخطوط: Cairo بترخيص SIL Open Font License 1.1 (`assets/fonts/OFL.txt`).
- لا أسرار في الكود. المفاتيح لاحقًا عبر GitHub Secrets فقط.
- `content/poc1.json` معتمد للنشر، وسجل أدلته في `content/evidence/poc1.json`، ووصف المنشور فيه.
