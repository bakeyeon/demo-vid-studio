# 🎬 Demo Video Storyboard — {{PROJECT_NAME}}

> **Status**: Draft (Awaiting User Approval)  
> **Layout Preset**: `{{LAYOUT}}` (1920×1080 1080p)  
> **Visual & Audio Style**: `{{STYLE}}`  
> **Narration Voice**: `{{VOICE}}`  
> **AI Asset Provider**: `{{AI_PROVIDER}}`  
> **Estimated Total Duration**: ~45–60s

---

## 1. Highlight Features & Directing Notes
- **Core Hook**: Introduce what the prototype does and why it matters in the first 6 seconds.
- **Feature 1**: Primary user workflow demonstration with live interaction.
- **Feature 2**: Deep-dive highlight using a live cropped region zoom (`rect`) inside the side card.
- **Pre-cached APIs**: Any LLM / slow backend calls listed below will be prefetched into `demo/api-cache.json` before recording so the take is 100% deterministic and free of 503 delays.

---

## 2. Scene-by-Scene Storyboard

| Scene # | Voice / Card ID | Screen Action & API Cache | Feature Card & Live Zoom | Narration (`say`) & Caption (`cap`) | Est. Time |
| :---: | :--- | :--- | :--- | :--- | :---: |
| **1** | `intro1`<br/>`intro2`<br/>*(Card: `intro`)* | App loaded at initial screen, gentle pause | **Intro Card**: App logo, title, core value proposition, and feature chips | **say**: "Meet [Project Name], a prototype that..."<br/>**cap**: "Meet [Project Name] — [Tagline]" | ~7s |
| **2** | `feat1`<br/>*(Card: `feature-1`)* | Tap input field, type example query, tap Submit (served from `api-cache.json`) | **Feature 1 Card**: Step badge + large preview of input query and key takeaway | **say**: "First, let's try..."<br/>**cap**: "1 · [Feature 1 summary]" | ~10s |
| **3** | `zoom1`<br/>*(Card: `detail-zoom`)* | Tap detail button / open visualization panel | **Live Zoom Card**: Left slot shows live 2× cropped zoom of the panel; right side explains the axes/metrics | **say**: "Notice how the detail view highlights..."<br/>**cap**: "Live breakdown of [Metric/Visual]" | ~9s |
| **4** | `outro`<br/>*(Card: `outro`)* | Scroll back to top overview | **Outro Card**: GitHub repo link, paper/author credits, and thank-you note | **say**: "Built with open tools. Thanks for watching!"<br/>**cap**: "Explore the code at github.com/..." | ~6s |

---

## 3. Approval Checklist
- [ ] Are the highlighted features and order accurate?
- [ ] Do you want to tweak any narration lines or captions?
- [ ] Are the chosen `--style` (`{{STYLE}}`) and `--layout` (`{{LAYOUT}}`) good to go?
- [ ] Also generate a **silent `preview.gif` & silent MP4 (`--preview-gif --silent-mp4`)** for embedding in your GitHub `README.md`?
