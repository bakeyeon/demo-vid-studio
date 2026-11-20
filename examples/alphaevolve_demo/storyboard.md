# 🎬 Demo Video Storyboard — `alphaevolve-plugin`

> **Status**: Approved & Rendered (`examples/alphaevolve_demo/alphaevolve-cyberpunk-demo.mp4`)  
> **Style Preset**: `cyberpunk` (Deep Dark Cyber Grid + Neon Cyan/Magenta HUD Cards + Synthwave Arpeggio BGM)  
> **Layout Preset**: `desktop` (Left `1280×800` Live Evolution Console & Code Diff Viewer at 2× DPR + Right `620×700` Cyberpunk HUD Cards + Bottom Neon Caption Bar)  
> **Narration Voice**: `en-US-AvaNeural`  
> **Total Duration**: 50.04 seconds

---

## 1. Visual Stage & Simulated App Design
Since `alphaevolve-plugin` is a coding-agent plugin, `examples/alphaevolve_demo/cockpit.html` provides an interactive **AlphaEvolve Live Evolution Cockpit** web UI (`1280×800`) driven by actual outputs from `scaffold_evolve.py` / `evolve_local.py` (0/1 Knapsack evolution from `gen_000` Greedy → `gen_003` Optimal DP):
- **Top Left**: `# EVOLVE-BLOCK-START` live Python code editor showing mutations across generations with highlighted diffs.
- **Top Right**: Live **MAP-Elites Fitness & Complexity Chart** (`combined_score` climbing from `0.724` → `0.865` → `0.942` → `1.000`).
- **Bottom Panel**: Agent terminal executing `evolve_local.py sample`, `evaluate --rationale`, and `status --held-out` with `BLIND_MODE = True` badge.

---

## 2. Scene-by-Scene Storyboard

| Scene # | Voice / Card ID | Screen Action (Left 1280×800 Cockpit) | Cyberpunk HUD Card (Right 620×700) | Narration (`say`) & Caption (`cap`) | Est. Time |
| :---: | :--- | :--- | :--- | :--- | :---: |
| **1** | `intro1`<br/>`intro2`<br/>*(Card: `intro`)* | Cockpit loads at `gen_000` baseline (`combined_score: 0.724`). Glowing `EVOLVE-BLOCK` markers pulse. | **Intro HUD Card**: Official AlphaEvolve SVG logo + `"AlphaEvolve Plugin"` neon title + chips (`Claude Code`, `Antigravity`, `MAP-Elites`) | **say**: "Meet AlphaEvolve, an evolutionary coding plugin for Claude Code and Antigravity."<br/>**cap**: "Meet AlphaEvolve — evolutionary algorithm discovery for coding agents."<br/><br/>**say**: "Instead of stopping at a first draft, it evolves algorithms against an automated evaluator."<br/>**cap**: "Iteratively mutates and benchmarks code inside `# EVOLVE-BLOCK`." | ~11.5s |
| **2** | `scaffold`<br/>*(Card: `baseline`)* | Click **`[1 · Verify Baseline]`** → Terminal runs `evaluator.py initial_program.py`, logs deterministic baseline score `0.724`. | **Baseline & Oracle Card**: Explains the L1 reference oracle & deterministic scoring rule (`combined_score: 0.724`). | **say**: "First, it scaffolds an initial baseline and verifies correctness against a reference oracle."<br/>**cap**: "1 · Verify deterministic baseline (`gen_000` · score `0.724`)." | ~7.0s |
| **3** | `mutate1`<br/>`mutate2`<br/>*(Card: `loop`)* | Click **`[2 · Mutate Gen 1]`** (`0.865`), then **`[3 · Mutate Gen 2]`** (`0.942`), then **`[4 · Evolve Gen 3 (DP)]`** (`1.000` + Ding SFX!). | **Mode A Evolution Loop Card**: Shows `sample` (Exploit + Explore) → Hypothesis Rationale → `evaluate` delta climbing to `1.000`. | **say**: "In Mode A, the agent samples top parents, writes a hypothesis, and mutates the evolve block."<br/>**cap**: "2 · Agent-driven loop: `sample` → hypothesis rationale → `evaluate`."<br/><br/>**say**: "Across three generations, the knapsack solver climbs from greedy to optimal dynamic programming."<br/>**cap**: "Score climbs `0.724` → `0.865` → `0.942` → `1.000` (`gen_003`)." | ~14.0s |
| **4** | `zoom_map`<br/>*(Card: `map-zoom`)* | Click **`[5 · Inspect MAP-Elites]`** to highlight the fitness trajectory chart & archive table. | **Live 2× Region Zoom Card**: Top slot shows a **live cropped 2× zoom** of the MAP-Elites fitness chart from the cockpit; bottom explains archive lineage & runtime metrics. | **say**: "Every candidate, parent lineage, and runtime metric is tracked live in the MAP-Elites archive."<br/>**cap**: "Live 2× zoom: MAP-Elites fitness progression & parent lineage." | ~6.5s |
| **5** | `guardrails`<br/>*(Card: `guardrails`)* | Click **`[6 · Held-Out & Blind Mode]`** → Terminal runs `status --held-out`, confirming `held_out_score: 1.000` and `BLIND_MODE = True`. | **Anti-Overfitting & Privacy Card**: Highlights `--held-out` verification split, `MAX_CODE_CHARS` anti-memorization, and GDPR `BLIND_MODE = True`. | **say**: "Held-out verification prevents overfitting, while Blind Mode protects private datasets from leaking into agent context."<br/>**cap**: "3 · Guardrails: `--held-out` split, `MAX_CODE_CHARS`, and `BLIND_MODE = True`." | ~7.0s |
| **6** | `outro`<br/>*(Card: `outro`)* | Cockpit displays `"EVOLUTION COMPLETE — best_program.py saved"` banner. | **Outro HUD Card**: `github.com/bakeyeon/alphaevolve-plugin` + Mode A (Agent-driven) & Mode B (OpenEvolve CLI) summary. | **say**: "Available now for Claude Code and Antigravity. Thanks for watching!"<br/>**cap**: "Explore `github.com/bakeyeon/alphaevolve-plugin` — Thanks for watching!" | ~4.5s |
