# Reef: anchor vs anchor2 sweep

Run on **reef** (`owner@192.168.68.20`, **Windows** + local Ollama). From COOPER:

```powershell
cd C:\Users\gmhow\dev\trust-but-anchor
.\scripts\start-reef-anchor2.ps1
```

Reef repo path: `C:\Users\Owner\dev\trust-but-anchor` (cloned from GitHub if missing).

The sweep runs `granite3.3:8b`, `qwen2.5-coder:7b`, and `mistral:7b` on `corpus/questions_anchor2.json` with both `--arm anchor` and `--arm anchor2` (3 repeats each). Logs: `results\anchor2-sweep.log` and `results\anchor2-sweep.nohup`.

Check progress:

```powershell
ssh owner@192.168.68.20 "powershell -NoProfile -Command \"Get-Content C:\\Users\\Owner\\dev\\trust-but-anchor\\results\\anchor2-sweep.log -Tail 20\""
```

Linux reef (if ever): `bash scripts/anchor2-sweep.sh`