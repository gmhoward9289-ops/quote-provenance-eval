# Reef — Remote Desktop (RDP)

Reef is the Windows GPU box (`owner@192.168.68.20`, SSH banner may show `192.168.68.53` if DHCP moved). Use RDP when you need a **persistent console** (Ollama serve, model pulls, watching sweep logs).

## One-time: enable RDP on reef

From COOPER:

```powershell
cd C:\Users\gmhow\dev\trust-but-anchor
.\scripts\setup-reef-rdp.ps1
```

If that hits UAC and cannot elevate over SSH, on reef **at the physical console** (or via lab HTTP drop `http://192.168.68.53:8765/`):

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Owner\lab\reef-enable-rdp.ps1
```

## Connect from COOPER

```powershell
mstsc C:\Users\gmhow\dev\trust-but-anchor\scripts\reef.rdp
```

Or: `mstsc /v:192.168.68.20`

| Field | Value |
| --- | --- |
| User | `Owner` or `swamp\owner` |
| Password | Owner account password |

Update `reef.rdp` `full address` if reef’s LAN IP changed (check SSH banner or `ipconfig` on reef).

## Once logged in — fix Ollama + sweep

**PowerShell (leave one window open):**

```powershell
$env:OLLAMA_MODELS = "Z:\ollama"
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" serve
```

**Second PowerShell window:**

```powershell
$env:OLLAMA_MODELS = "Z:\ollama"
ollama list
ollama pull granite3.3:8b
```

Do **not** open the Ollama desktop tray app (second serve binds `::11434`).

From COOPER after models are up:

```powershell
cd C:\Users\gmhow\dev\trust-but-anchor
.\scripts\reef-unstick-anchor2.ps1
.\scripts\check-reef-anchor2.ps1
```

## Troubleshooting

- **Can’t connect:** verify IP (`ping 192.168.68.20`), run `setup-reef-rdp.ps1` again, check Windows Firewall on reef.
- **Wrong IP:** SSH shows current address in banner; edit `scripts\reef.rdp`.
- **Ollama empty list:** confirm `OLLAMA_MODELS=Z:\ollama` in the serve window before `ollama list`.
