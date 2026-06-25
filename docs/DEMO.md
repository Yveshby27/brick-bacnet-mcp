# Meeting Demo: Remote Call Runbook

Single-scenario script for a live Zoom / Teams / Meet call with an MSI prospect. 15-30 minute meeting; ~7 minutes of actual demo. Copy-pasteable.

For other settings (in-person site visits, conference talks), see [DEMO.md](DEMO.md).

---

## T-5 minutes: pre-call setup

Do this before the call starts. If anything below fails, recover BEFORE joining the call.

### 1. Open two terminals at repo root, venv activated

**PowerShell:**
```powershell
cd C:\Users\User\Desktop\Me\brick-bacnet-mcp
.\.venv\Scripts\Activate.ps1
```

**Git Bash:**
```bash
cd /c/Users/User/Desktop/Me/brick-bacnet-mcp
source .venv/Scripts/activate
```

### 2. Smoke test the install

```bash
brick-bacnet-mcp --version
```
Should print `brick-bacnet-mcp 0.1.0a2` or later. If not, install is broken; do not enter the call until fixed.

### 3. Confirm Claude Desktop is wired

Open Claude Desktop. Start a fresh chat. Type:
> what tools do you have

Confirm `list_devices`, `list_objects`, `get_object_value`, `get_tagged_topology` appear. If they don't, check `%APPDATA%\Claude\claude_desktop_config.json` and restart Claude Desktop.

### 4. Arrange the screen

Layout for screen share:
- **Top half:** Terminal 1 (simulator) + Terminal 2 (demo script) side-by-side
- **Bottom half:** Claude Desktop chat window

Close Slack, email, anything with notifications. Set status to DND.

### 5. Have these tabs ready (not yet shared)

- [README.md](../README.md) on GitHub
- The research note: https://habchy.dev/research/bacnet-msi-semantic-gap
- Your calendar (for booking the followup)

---

## T-0: meeting starts

### Opening (1 minute)

Don't open the screen share yet. Two sentences only:

> "Vendor BAS platforms keep their semantic AI inside their own controls portfolio. JCI, Honeywell, Siemens, Tridium all do this. If you're running mixed-vendor portfolios, you have BACnet point databases but no clean way to expose them to external LLM agents. This gateway is one answer to that gap. Let me show you instead of pitching."

Now start the screen share.

---

## The demo (7 minutes)

### Step 1 — start the simulator (Terminal 1) [30 seconds]

```bash
python scripts/run_simulator.py --fixtures tests/fixtures/simulator_devices.yaml
```

**Say:** "Simulated 20-point building running on UDP 47808. One AHU, two VAVs, a chiller plant, two meters. Standing in for your BACnet network. Real BACnet protocol, fake building."

Leave it running.

### Step 2 — run the pipeline (Terminal 2) [90 seconds]

```bash
python scripts/loopback_demo.py
```

While it scrolls, narrate:

- **At "STEP 1: unicast Who-Is":** "BACnet discovery. The gateway broadcasts Who-Is, the building's controllers respond with I-Am."
- **At "STEP 2: enumerate":** "Per-device object enumeration, then ReadProperty for present-value and units. This is the read-only surface."
- **At "STEP 3: assemble + tag":** "Here's the layer the vendors keep proprietary. Each BACnet object gets mapped to a Brick class and a Haystack tag set."
- **At the tagged-object table:** "Notice OAT became `Outside_Air_Temperature_Sensor`, AHU-1_DAT became `Supply_Air_Temperature_Sensor`. The LLM doesn't need to know BACnet object types or vendor naming conventions."
- **At the coverage report:** "On your real portfolio, this number is the diagnostic. 100% on the synthetic fixture. A fresh real-world site starts at 30-50% with the default rules. You extend the YAML rule files for your naming conventions until it clears 70%."

### Step 3 — switch to Claude Desktop [4 minutes]

Open Claude Desktop. Ask these three prompts in order. Wait for each answer before moving on.

**Prompt 1:**
> List every temperature sensor in the building.

**Say:** "Notice the prompt doesn't mention BACnet, point names, or object types. Claude calls `get_tagged_topology` with a Haystack filter and gets back the 12 temp sensors."

**Prompt 2:**
> What's the current outside air temperature?

**Say:** "Claude looks up the object tagged as outside air temp, calls `get_object_value`, returns the present-value. Same query against a real building gives the live reading."

**Prompt 3:**
> Compare AHU-1 discharge air temp to mixed air temp. Is the economizer doing anything useful?

**Say:** "Now you can see why the semantic tagging matters. Claude pulls both points, computes the delta, and reasons about it in building terms. This is what your customers are paying vendor platforms five figures a year to do, except this works across all your vendors."

### Step 4 — wrap [60 seconds]

Ctrl-C the simulator in Terminal 1.

**Say:** "That's the whole thing. Open-source, MIT, on GitHub. Read-only by design in v0.1 for the compliance surface reasons in the research article. Four MCP tools, simple YAML rule library, works with Claude Desktop or any MCP host."

---

## Closing / CTA (2 minutes)

Pick ONE based on signal during the demo:

### If they leaned in / asked technical questions

> "I'd like to point this at one of your real buildings. Send me a sanitized point list from one site and I'll run the coverage report against it. Forty-five minutes on a follow-up call to walk you through what it found. Does next week work?"

### If they were polite but quiet

> "If this is useful to you, the repo's at github.com/Yveshby27/brick-bacnet-mcp. I'd love your feedback if you try it against a real point list. I'm building this as a research instrument right now, so what I most need is signal from MSIs on whether the wedge is right."

### If they pushed back ("we already use SkySpark" / "we built our own" / etc.)

> "That makes sense. This is positioned next to those, not against them. The wedge is the LLM-agent surface, not Haystack tagging itself. If you ever want to plug an LLM into your existing Haystack store, this gives you the MCP layer. Worth a follow-up if that becomes interesting."

Don't argue. Note the objection. Move on.

---

## Common questions + crisp answers

| Question | Answer |
|---|---|
| "Why read-only?" | Compliance surface. WriteProperty means an LLM could change setpoints. Out of v0.1 by design. Roadmap has opt-in write for v0.3. |
| "Does it support BACnet/SC?" | v0.1 is BACnet/IP only. BACnet/SC is v0.2 if there's sustained-use signal. |
| "What about Niagara stations?" | Fox protocol is a separate design. Niagara exposes BACnet/IP, so this works against Niagara JACEs over BACnet today. |
| "How does this compare to SkySpark?" | SkySpark is the Haystack store and analytics. This is the BACnet-to-LLM gateway. Different layer. Could feed a SkySpark instance later. |
| "Why not just use vendor X's AI?" | Vendor AIs only work inside their own portfolio. If you have 40 buildings across 4 vendors, you have 4 AI platforms or zero. This is the cross-vendor option. |
| "Is it secure?" | v0.1 assumes a trusted local network. No auth. v0.3 candidate. Don't expose the gateway outside the BAS VLAN. |
| "Can I self-host the LLM?" | Yes. The MCP server doesn't care which LLM is on the other end. Claude Desktop today, Ollama or any MCP-compatible host tomorrow. |
| "What does it cost?" | MIT-licensed open source. Free. The LLM API or local inference cost is separate. |
| "How long to deploy?" | One day to install and tune the rule library for a site. Hours per additional site after the first. |
| "What if it doesn't tag my points well?" | The coverage report tells you exactly what's missing. You add YAML rules for your naming patterns. Aim for 70%+ before relying on it. |

---

## Failure recovery during the call

| Symptom | Mid-call fix |
|---|---|
| Simulator won't start, port in use | `taskkill /F /IM python.exe` then retry. If still broken, skip to "What if I don't run the live demo" below. |
| Loopback demo returns 0 devices | Simulator died. Restart it. If it dies again, skip to fallback. |
| Claude Desktop tools not showing | Restart Claude Desktop in a separate window. While restarting, talk through the architecture diagram from [ARCHITECTURE.md](ARCHITECTURE.md). |
| Total demo failure | See fallback below. Don't panic on camera. |

### What if I can't run the live demo (fallback)

Pre-record the Path A flow ([DEMO.md A.1-A.4](DEMO.md)) and have the file on disk. If everything breaks, share the recording:

> "The live demo's having an environment issue. Let me show you a recording from earlier this morning. Same flow."

Then go straight to the closing CTA. Offer to schedule a re-demo. Do NOT spend more than 60 seconds troubleshooting on camera.

---

## Post-call followup (within 2 hours)

Email template:

> Subject: brick-bacnet-mcp + [their portfolio name]
>
> [First name],
>
> Thanks for the time today. Three links from what we covered:
>
> - The repo: https://github.com/Yveshby27/brick-bacnet-mcp
> - The research note that drove this: https://habchy.dev/research/bacnet-msi-semantic-gap
> - The Claude Desktop wiring example: https://github.com/Yveshby27/brick-bacnet-mcp/blob/main/examples/03_query_via_claude_desktop.md
>
> Next step I proposed: send me a sanitized point list from one of your sites. I'll run the coverage report against it and we walk through the results next week. [Calendar link]
>
> Yves

Log the outcome at PIE. From PIE root:
```bash
pie touch bacnet-mcp-bas-integrators --event design_partner_inbound   # if they asked for a follow-up
pie touch bacnet-mcp-bas-integrators --event paid_signup              # if they bought
```

---

## One-line opener (memorize this)

> "Vendor BAS platforms keep their semantic AI inside their own controls portfolio. This gateway is the cross-vendor alternative. Let me show you."
