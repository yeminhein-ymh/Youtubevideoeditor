# Energy Hub Video Studio

A local Streamlit app that converts a raw lecture or screen recording into a YouTube-ready package:

- 1080p H.264/AAC MP4 with a clean 16:9 canvas
- opening cover image and optional subscribe end card
- voice normalization, rumble removal, light denoise, and smooth fades
- optional low-volume background music
- generated 1280×720 YouTube thumbnail
- 30-second preview mode before a long final render

The default **Reference style** preset is based on the supplied sample: 1920×1080, 30 fps, an approximately 8-second cover, lecture content, and a short end card.

## Run

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Then upload the raw recording, cover, optional song, and optional end card. Keep **Render a 30-second preview first** enabled until the result looks right.

## Notes for long recordings

The supplied raw recording is about 2 hours 17 minutes. A full 1080p render can take a long time and needs several gigabytes of free disk space. The browser upload limit is configured to 4 GB. Finished files are stored in the local `renders` folder, and files over 500 MB are intentionally not copied into browser memory for download.

Only use music and artwork that you own or are licensed to publish on YouTube.

## Facebook 9:16 page

Use **Facebook Reels Studio** from Streamlit's page navigation to create a 1080×1920 portrait MP4 and vertical cover. Landscape recordings can preserve the full frame on a branded background or fill the portrait screen by cropping the sides. This page also has a fast 20-second preview mode.
