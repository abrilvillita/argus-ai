# Argus AI — Demo Video Script

Target length: **2:00–2:30**. Record your screen at the live demo (https://argus-ai-5n2k.onrender.com) or `localhost:8000` with the simulator running. No background music needed — if you add any, make sure it's royalty-free/licensed for reuse.

---

### [0:00–0:10] Hook — cold open on the problem

**VISUAL:** Start on the live dashboard already running, telemetry actively updating. Don't explain anything yet — just let it breathe for 2-3 seconds, then cut to you on camera (or stay on screen, narrating over it).

**VOICEOVER:**
> "Every IoT dashboard looks like this — numbers updating, charts moving. The question nobody answers is: what happens when something actually goes wrong?"

---

### [0:10–0:30] The problem

**VISUAL:** Stay on the dashboard, maybe scroll to the Fleet panel.

**VOICEOVER:**
> "Most teams handle this with a static threshold — alert if temperature goes above 80 degrees. That misses slow degradation and problems that only show up when *multiple* sensors drift together. And building real anomaly detection usually means hiring a data scientist and standing up a training pipeline most small teams don't have. Even once you catch the problem, turning it into an automatic response still means writing and shipping code."

---

### [0:30–0:45] Introduce Argus AI

**VISUAL:** Show the header / title of the app ("Argus AI — No-code IoT anomaly detection & auto-remediation").

**VOICEOVER:**
> "This is Argus AI. It streams in telemetry from any IoT fleet, learns what normal looks like per device with zero training data, and lets anyone — not just a developer — wire up an automatic response through a plain web form."

---

### [0:45–1:20] Live demo — AI catching an anomaly

**VISUAL:** Point at the Fleet panel and the Live Telemetry chart. Let a spike happen naturally (the simulator injects them every ~15-20s), or narrate over one as it happens. Then scroll to the **Alerts & auto-remediation log** and point at an entry with `source: mahalanobis` or `source: ewma_zscore`.

**VOICEOVER:**
> "In the background, two AI techniques are watching every reading in real time. One tracks each sensor's own rolling baseline and flags a sudden spike. The other watches a device's *combined* metrics — temperature, humidity, vibration — together, so it catches the anomalies a single threshold would miss entirely. Watch what happens right here — no config, no manual labeling, it just flagged it."

*(Point at the alert entry with the anomaly message and timestamp as it appears.)*

---

### [1:20–1:50] Live demo — no-code rule builder

**VISUAL:** Move to the "No-code rule builder" panel. Fill it in on camera: pick a device, a metric, an operator, a threshold, and an action (e.g. `furnace-01`, `temperature`, `is greater than`, `65`, `Shutdown device`). Click **+ Add rule**. Then either wait for or trigger a matching reading, and point at the resulting alert with `action: shutdown_device`.

**VOICEOVER:**
> "Say I want to auto-shutdown the furnace if it overheats. I don't touch a line of code — I fill out this form: furnace-01, temperature, greater than 65, shutdown device. That's it. The moment a reading crosses that line, it's logged right here as an executed action."

---

### [1:50–2:10] How it's built (credibility / tech depth)

**VISUAL:** Optional — cut briefly to the GitHub repo or the architecture diagram in the README.

**VOICEOVER:**
> "Under the hood it's a FastAPI backend pushing updates over WebSocket, with the AI engine written in pure Python — deliberately no numpy, no scikit-learn. That means no compiled dependencies to fail to install, and a much faster cold start when it's deployed serverless. It ships with a Dockerfile, an AWS Lambda handler, and this live version is running on Render right now."

---

### [2:10–2:25] Close

**VISUAL:** Back to the full dashboard view.

**VOICEOVER:**
> "This is Argus AI — built for the DevNetwork API, Cloud, and AI Hackathon. Detect, decide, and act, in one no-code loop. Thanks for watching."

*(Optional end card: live demo URL + GitHub link.)*

---

## Recording checklist

- [ ] Make sure the simulator is producing an anomaly during the 0:45–1:20 window (either time your recording around the ~15-20s injection cadence, or run `simulator/simulate.py --anomaly-chance 0.3` locally right before recording for a denser demo)
- [ ] Test your mic levels before the full take
- [ ] Keep total runtime under ~2:30 — judges review many submissions
- [ ] Export as MP4, upload to YouTube (unlisted is fine, just not private) for the public "Video demo link" field
- [ ] Also upload the same MP4 to Google Drive/Dropbox/OneDrive with link sharing on, for the organizer backup field
