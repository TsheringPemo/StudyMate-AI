# How to turn on the LLM (Ollama + Qwen3) - step by step

StudyMate uses a **local** LLM, so it is free, private and needs no API key. Ollama is the program that runs the model.

## 1. Install Ollama
1. Go to **https://ollama.com/download** and download the Windows installer.
2. Run it. Ollama starts in the background (look for the llama icon in the system tray).

## 2. Download a model (one time, needs internet)
Open **PowerShell** and run:
```powershell
ollama pull qwen3:8b
```
This is a large download (about 5 GB) and wants roughly 8 GB of free RAM. If your computer is slow or the
internet is limited, use a smaller model instead:
```powershell
ollama pull qwen3:4b
```
Then tell StudyMate to use it **before** starting the app (same PowerShell window):
```powershell
$env:STUDYMATE_MODEL = "qwen3:4b"
```

## 3. Test the model on its own
```powershell
ollama run qwen3:8b "Say hello in one sentence"
```
If it answers, press `Ctrl+D` (or type `/bye`) to leave.

## 4. Start StudyMate
```powershell
cd path\to\studymate
.venv\Scripts\Activate.ps1
streamlit run app.py
```
Open the **Study Planner** page and run a request (next step shows what to look for).

## 5. What you should see when the LLM works
On the **Study Planner** page, press *Ask StudyMate to plan*, then check:
* metric **LLM status = ok**
* a **🤖 Coach note** card above the plan
* in *Agent trace*: step 3 shows `llm_status: ok` and step 8b shows `status: ok`

## What the LLM does (say this in your defence)
| Job | Where | Safety check |
|---|---|---|
| Understands the request (intent + focus) | step 3 | Intent must be on an allow-list, else rule-based fallback |
| Suggests tools | step 3 -> 4 | Every tool name is validated against the registry |
| Writes a short coach note | step 8b | Rejected if it contains any number that is not in the plan, or is too long |

The LLM never ranks tasks or decides hours - Python tools do.

## Troubleshooting
| Problem | Fix |
|---|---|
| LLM status says `offline` | Open the Ollama app, or run `ollama serve` in a separate PowerShell window |
| LLM status `offline` and Ollama is running (model missing) | Run `ollama pull qwen3:8b` (or set `STUDYMATE_MODEL` to a model you have: `ollama list`) |
| Very slow first answer | Normal - the model is loading into memory. Use `qwen3:4b` if it stays slow |
| LLM status shows `invalid response` | Small models sometimes fail JSON; the agent safely falls back. Try again or use the 8b model |
| Need another address/port | `$env:STUDYMATE_OLLAMA_URL = "http://localhost:11434/api/chat"` |

---

# I don't have Ollama on my laptop - using a friend's laptop

You have two options. **Option A is simpler and safer.**

## Option A - run StudyMate on your friend's laptop (recommended for the final demo)
1. Copy the project folder (the zip, or a USB stick) to her laptop and unzip it.
2. On her laptop: install Python, then in PowerShell inside the folder:
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   streamlit run app.py
   ```
3. Her Ollama already has the model, so **LLM status** on the Study Planner page should say `ok`.
   If she has a different model, check with `ollama list` and set `$env:STUDYMATE_MODEL = "that-model-name"` first.
4. Your tasks and feedback live in `data/studymate.db`, so copy that file too if you want your data.

## Option B - run the app on YOUR laptop but use HER Ollama over Wi-Fi
Both laptops must be on the **same Wi-Fi/network**.

**On her laptop**
1. Quit Ollama (right-click the tray icon -> Quit).
2. Open PowerShell and run:
   ```powershell
   $env:OLLAMA_HOST = "0.0.0.0"
   ollama serve
   ```
   Leave this window open. If Windows Firewall asks, allow access on **Private** networks.
3. Find her IP address: run `ipconfig` and read **IPv4 Address** (for example `192.168.1.25`).

**On your laptop**
1. Test in a browser: `http://192.168.1.25:11434` -> it should say "Ollama is running".
2. In PowerShell (same window you start the app from):
   ```powershell
   $env:STUDYMATE_OLLAMA_URL = "http://192.168.1.25:11434/api/chat"
   $env:STUDYMATE_MODEL = "qwen3:8b"     # must match a model on HER laptop (ollama list)
   streamlit run app.py
   ```
3. Run a request on the **Study Planner** page and check that **LLM status** says `ok`.

**Cautions for Option B**
* Ollama has **no password**. Only do this on a network you trust, and close it afterwards.
* Your request text is sent to her laptop. Do not type personal information. (Without a remote host, nothing leaves your computer.)
* If the connection drops, StudyMate falls back to the rule-based interpreter automatically - it will not crash.
* Do **not** rely on this for the live defence unless you have tested it in the same room beforehand.

## For the assessment
* Your app works **without** Ollama, so you can always demo on your own laptop and say: "The LLM layer is optional; when it is offline the agent falls back to rules."
* Use your friend's laptop once to run the LLM, take screenshots, and fill in **Appendix B** of the report.
