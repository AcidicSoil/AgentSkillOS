# Custom Skill Groups Example

**Created:** 3/1/2026 12:58:42  
**Updated:** 3/1/2026 13:05:08  
**Exported:** 3/1/2026 18:36:40  
**Link:** [https://chatgpt.com/g/g-p-699e141c586c8191a60c161296bf2ae0-g-chat/c/69a48c59-659c-8326-beae-7ea3fda72b17](https://chatgpt.com/g/g-p-699e141c586c8191a60c161296bf2ae0-g-chat/c/69a48c59-659c-8326-beae-7ea3fda72b17)  

## Response:
Thought for 3m 17s

1) Register new skill groups in `src/config.py`
-----------------------------------------------

```
# path: src/config.py
# Add these entries inside SKILL_GROUPS = [ ... ] (keep existing ones)

{
    "id": "project_toolifier",
    "name": "Project Toolifier (local)",
    "description": "Turn local repos/apps into callable tools (wrappers + manifests).",
    "skills_dir": str(DATA_DIR / "project_toolifier"),
    "tree_path": str(Path(__file__).parent / "skill_retriever/capability_tree/tree_project_toolifier.yaml"),
},
{
    "id": "llm_routing",
    "name": "LLM Routing & Proxies",
    "description": "OpenAI-compatible routing, provider quirks, tool-output hardening.",
    "skills_dir": str(DATA_DIR / "llm_routing"),
    "tree_path": str(Path(__file__).parent / "skill_retriever/capability_tree/tree_llm_routing.yaml"),
},
{
    "id": "local_devops",
    "name": "Local DevOps (WSL/Docker)",
    "description": "Ports, processes, docker networking, reproducible debug bundles.",
    "skills_dir": str(DATA_DIR / "local_devops"),
    "tree_path": str(Path(__file__).parent / "skill_retriever/capability_tree/tree_local_devops.yaml"),
},
{
    "id": "docs_media",
    "name": "Docs & Media Output",
    "description": "Docx reports, screenshot annotation, README digests.",
    "skills_dir": str(DATA_DIR / "docs_media"),
    "tree_path": str(Path(__file__).parent / "skill_retriever/capability_tree/tree_docs_media.yaml"),
},
```

2) Drop in a practical example pack (folders + full `SKILL.md` contents)
------------------------------------------------------------------------

### Folder layout

```
data/
  project_toolifier/
    scan-projects/
      SKILL.md
    generate-tool-manifest/
      SKILL.md
    generate-cli-wrapper/
      SKILL.md
  llm_routing/
    openai-compatible-proxy-config/
      SKILL.md
    gemini-tool-output-sanitizer/
      SKILL.md
    quota-aware-fallback-routing/
      SKILL.md
  local_devops/
    port-process-audit/
      SKILL.md
    docker-network-debug/
      SKILL.md
    collect-debug-bundle/
      SKILL.md
  docs_media/
    design-research-report-docx/
      SKILL.md
    screenshot-annotator/
      SKILL.md
    readme-digest/
      SKILL.md
```

* * *

### `data/project_toolifier/scan-projects/SKILL.md`

```
<!-- path: data/project_toolifier/scan-projects/SKILL.md -->
---
name: Scan local projects into an inventory
description: Walk a projects/ directory, detect app types (python/node/docker/etc.), and output a structured inventory for toolification.
---

## When to use
- You have a monorepo or `~/projects` folder with many subprojects.
- You need an inventory to decide what is worth turning into callable tools.

## Inputs
- `root_dir`: directory to scan (default: `~/projects`)
- `max_depth`: recursion depth (default: 3)
- Optional filters: include/exclude globs

## Outputs
- `project_inventory.json` containing:
  - project path
  - language/runtime signals (pyproject, package.json, go.mod, Cargo.toml, etc.)
  - entrypoints (Makefile targets, scripts, docker compose, CLI bins)
  - “toolability” score + recommended wrapper type

## Procedure
1. Enumerate immediate subdirectories under `root_dir`.
2. For each project, detect signals:
   - Python: `pyproject.toml`, `requirements.txt`, `uv.lock`
   - Node: `package.json`, `pnpm-lock.yaml`, `yarn.lock`
   - Docker: `Dockerfile`, `docker-compose.yml`
   - CLI: `bin/`, `scripts/`, `Makefile`, `justfile`
3. Extract candidate entrypoints:
   - `make help`, `just --list`, `npm run`, `uv run`, `python -m ...` patterns
4. Assign a wrapper recommendation:
   - “shell wrapper” if it’s already a CLI/script
   - “python wrapper” if it needs env + module execution
   - “docker wrapper” if it’s container-first
5. Emit `project_inventory.json` sorted by toolability score.

## Validation
- Inventory includes every scanned repo (count matches directory listing).
- Each repo has at least one detected signal or is marked “unknown”.

## Failure modes
- Repos with nested apps: increase `max_depth`.
- Missing permissions: skip and record error per-project.
```

### `data/project_toolifier/generate-tool-manifest/SKILL.md`

```
<!-- path: data/project_toolifier/generate-tool-manifest/SKILL.md -->
---
name: Generate a tool manifest from the inventory
description: Convert an inventory into a consistent tool registry (names, args, contracts) usable by agents and tool servers.
---

## When to use
- You already have `project_inventory.json`.
- You need a single source of truth for “what tools exist” and how to call them.

## Inputs
- `project_inventory.json`
- `naming_policy`: kebab-case tool names, stable prefixes, collision handling
- `default_timeout_s`, `default_cwd_policy`

## Outputs
- `tool_manifest.json` with:
  - tool id, title, description
  - command template (or module entrypoint)
  - args schema (name/type/required/default)
  - environment requirements (vars, files, ports)
  - timeout + working directory rules
  - expected artifacts (files written)

## Procedure
1. Normalize tool naming:
   - `tool_id = <project>-<capability>` with collision suffixes when needed.
2. For each project, pick 1–3 top entrypoints to expose as tools:
   - prefer deterministic commands with clear inputs/outputs
3. Define argument schema:
   - map flags/positional args to a JSON schema-like structure
4. Define contracts:
   - what files are created, where logs go, exit codes
5. Emit a manifest that is “agent-friendly”:
   - concise descriptions
   - strict, machine-parseable arg definitions

## Validation
- Every manifest tool references an existing project path.
- Command template is runnable in a clean shell with declared env vars.

## Notes
- Keep the manifest stable; tool ids should not churn across runs.
```

### `data/project_toolifier/generate-cli-wrapper/SKILL.md`

```
<!-- path: data/project_toolifier/generate-cli-wrapper/SKILL.md -->
---
name: Create a consistent CLI wrapper for a project tool
description: Build a small wrapper script that standardizes invocation, logging, cwd, env, and outputs for a project command.
---

## When to use
- A project has a useful command but it’s messy (needs env, cwd, extra steps).
- You want tools to behave consistently across many repos.

## Inputs
- One tool entry from `tool_manifest.json`
- Wrapper target: `scripts/tools/<tool_id>` (recommended)

## Outputs
- Executable wrapper script that:
  - validates args
  - sets working directory
  - exports required env vars (or errors if missing)
  - writes logs to `artifacts/logs/<tool_id>.log`
  - returns non-zero on failure

## Procedure
1. Decide wrapper type:
   - bash for simple forwarding
   - python for complex arg parsing + structured outputs
2. Implement:
   - `set -euo pipefail` (bash) or strict exceptions (python)
   - arg parsing that matches the manifest schema
   - consistent logging + timestamps
3. Run a smoke test:
   - minimal args, confirm exit code + artifacts
4. Add a `--help` output that matches the manifest.

## Validation
- Wrapper runs from anywhere (does not rely on current shell state).
- Logs are written even on failure.
```

* * *

### `data/llm_routing/openai-compatible-proxy-config/SKILL.md`

```
<!-- path: data/llm_routing/openai-compatible-proxy-config/SKILL.md -->
---
name: Validate OpenAI-compatible proxy configuration
description: Check base_url, headers, auth, and model naming for OpenAI-compatible APIs (local proxies, routers, gateways).
---

## When to use
- Tools fail with auth errors, 404 model not found, or tool-calling mismatches.
- You are routing through a proxy endpoint instead of the native provider.

## Inputs
- `base_url`
- `api_key`
- target `model` string(s)
- optional proxy-specific headers

## Outputs
- A verified configuration block:
  - base_url correctness (v1 path, trailing slash handling)
  - auth header mapping
  - model naming conventions + examples
- A minimal `curl` test command set (chat + models list)

## Procedure
1. Confirm endpoint shape:
   - should expose `/v1/models` and `/v1/chat/completions` (or equivalents)
2. Confirm auth expectations:
   - `Authorization: Bearer ...` vs custom header
3. Confirm model naming:
   - whether proxy expects `provider/model` or raw provider ids
4. Produce smoke tests:
   - list models
   - 1-turn chat completion
   - tool call request (if supported)

## Validation
- `models` call succeeds.
- `chat` call succeeds with the exact model string you plan to use.
```

### `data/llm_routing/gemini-tool-output-sanitizer/SKILL.md`

```
<!-- path: data/llm_routing/gemini-tool-output-sanitizer/SKILL.md -->
---
name: Harden tool-calling for Gemini-style outputs
description: Reduce tool errors by forcing strict JSON, adding output guards, and applying repair/retry logic for non-conforming tool calls.
---

## When to use
- Tool calls intermittently fail due to malformed JSON, wrong fields, or mixed prose + JSON.
- A Gemini-backed model behaves differently than Claude/OpenAI style tool calling.

## Inputs
- tool schema (function name + args schema)
- model output that should contain tool call args
- retry budget (default: 2)

## Outputs
- A “tool-output guard” plan:
  - strict JSON mode prompt block
  - validation rules
  - repair strategy (re-ask with the invalid snippet)
- A wrapper pattern for agents to apply consistently

## Procedure
1. Force a single-channel structured output:
   - demand: “Return ONLY valid JSON object. No markdown. No prose.”
2. Validate output:
   - parse JSON
   - check required keys + types
   - reject extra top-level keys when strict
3. Repair attempt (1):
   - feed back the invalid output
   - ask for corrected JSON only
4. Repair attempt (2):
   - ask model to emit args using an explicit example object template
5. Fail closed:
   - stop and surface validation errors verbosely

## Validation
- Parsed JSON passes schema checks before calling the tool.

## Notes
- Treat “almost JSON” as failure; do not best-effort guess args.
```

### `data/llm_routing/quota-aware-fallback-routing/SKILL.md`

```
<!-- path: data/llm_routing/quota-aware-fallback-routing/SKILL.md -->
---
name: Quota-aware fallback routing strategy
description: Decide when to switch models/accounts based on remaining quota, tool requirements, and failure modes.
---

## When to use
- You have multiple accounts/providers and want automatic fallback.
- You want to avoid burning high-tier quota on low-value steps.

## Inputs
- quota signals per provider/account (percent remaining + reset time)
- task requirements:
  - tool calling needed?
  - long context needed?
  - reliability vs cost preference

## Outputs
- A routing decision matrix:
  - primary model per task type
  - downgrade/upgrade conditions
  - forced routing for “must succeed” steps
- A minimal policy spec usable by a router component

## Procedure
1. Categorize steps:
   - planning, retrieval, transformation, tool-calling, verification
2. Assign default model tiers:
   - cheap for planning/retrieval
   - reliable for tool-calling/verification
3. Apply quota rules:
   - if near reset and quota remains: spend on high-value reliability steps
   - if far from reset and low remaining: downgrade aggressively
4. Apply failure rules:
   - repeated tool JSON failures => switch to a stricter tool-calling model
5. Emit a deterministic policy (no ambiguity).

## Validation
- Same inputs produce same routing choice.
- Tool-required steps never select a model known to break tool output.
```

* * *

### `data/local_devops/port-process-audit/SKILL.md`

```
<!-- path: data/local_devops/port-process-audit/SKILL.md -->
---
name: Identify and resolve port/process conflicts
description: Find what is listening on a port in WSL/Linux, map to process/container, and cleanly stop or rebind it.
---

## When to use
- “Address already in use” errors.
- A service won’t start, or docker ports won’t bind.

## Inputs
- `port` (tcp/udp)
- context: native process vs docker vs systemd

## Outputs
- The owning PID/container
- A safe stop plan (terminate, systemctl, docker stop)
- Optional rebind plan (pick alternative port + update config)

## Procedure
1. Identify listener:
   - `ss -ltnp | grep :<port>` (tcp) / `ss -lunp` (udp)
   - fallback: `lsof -i :<port>`
2. Map to service:
   - if docker: `docker ps --format ...` + published ports
   - if systemd: `systemctl status <unit>`
3. Stop cleanly:
   - systemd stop > docker stop > kill (last resort)
4. Confirm freed:
   - rerun `ss`/`lsof`

## Validation
- Port no longer appears in listeners.
- Service starts successfully after remediation.
```

### `data/local_devops/docker-network-debug/SKILL.md`

```
<!-- path: data/local_devops/docker-network-debug/SKILL.md -->
---
name: Debug docker networking between containers
description: Diagnose container-to-container connectivity, DNS/service-name resolution, ports, and host access from containers.
---

## When to use
- One container cannot reach another by service name.
- Confusion between `host.docker.internal` vs compose service DNS.

## Inputs
- docker compose file (services + networks)
- source container, target container/service, target port

## Outputs
- Root cause classification:
  - wrong network
  - wrong hostname/service name
  - port not exposed vs not published
  - firewall/iptables
- Exact fixes (compose network wiring + correct base URLs)

## Procedure
1. Confirm same network:
   - `docker network inspect <net>` and check both containers
2. DNS check inside source container:
   - `getent hosts <service>` or `nslookup <service>`
3. Connectivity check:
   - `curl -v http://<service>:<port>/health`
   - `nc -vz <service> <port>`
4. Distinguish:
   - *exposed* (internal) vs *published* (host)
5. Apply fixes:
   - use `http://<compose_service>:<port>` for container-to-container
   - use `http://host.docker.internal:<port>` for container-to-host (when supported)

## Validation
- Health endpoint reachable from source container consistently.
```

### `data/local_devops/collect-debug-bundle/SKILL.md`

```
<!-- path: data/local_devops/collect-debug-bundle/SKILL.md -->
---
name: Collect a reproducible debug bundle
description: Gather logs, configs, versions, and minimal repro steps into a single artifact for fast debugging and escalation.
---

## When to use
- Intermittent failures, proxy issues, tool errors.
- You need a shareable bundle without leaking secrets.

## Inputs
- project root path
- services involved (docker compose, uv, node, python)
- timeframe for logs (last N minutes)

## Outputs
- `debug_bundle/` containing:
  - `repro_steps.md`
  - `env_redacted.txt`
  - `versions.txt`
  - `docker_ps.txt`, `docker_logs_*.txt` (if applicable)
  - app logs (bounded)
  - config snapshots (non-secret)

## Procedure
1. Capture versions:
   - python/uv/node/docker/git + OS info
2. Capture configs:
   - include config files; redact keys/tokens
3. Capture logs with bounds:
   - last N lines only
4. Write minimal repro:
   - exact commands + expected vs actual
5. Pack:
   - tar/zip bundle directory

## Validation
- Bundle contains enough to reproduce without private secrets.
```

* * *

### `data/docs_media/design-research-report-docx/SKILL.md`

```
<!-- path: data/docs_media/design-research-report-docx/SKILL.md -->
---
name: Produce a UI design research report (DOCX)
description: Research comparable products, capture screenshots, extract design tokens, and write a structured report.docx.
---

## When to use
- You need a doc artifact (DOCX) summarizing UI patterns and design language.
- You are comparing products (e.g., Notion vs Confluence) for synthesis.

## Inputs
- product list (names + URLs if available)
- target sections (typography, color, layout, components)
- screenshot list (or a capture plan)

## Outputs
- `report.docx` with:
  - screenshots + captions
  - token tables (colors, type scale, spacing)
  - pattern analysis (navigation, hierarchy, density)
  - synthesis recommendations

## Procedure
1. Define evaluation rubric (5–10 criteria).
2. Collect screenshots for key flows (home, editor, search, settings).
3. Extract tokens:
   - primary/secondary colors, neutrals
   - font sizes/weights
   - spacing and component radius/shadows
4. Write findings per product, then synthesis section.
5. Add an appendix: screenshot index + notes.

## Validation
- Report includes screenshots (not just text).
- Recommendations are tied to observed patterns.
```

### `data/docs_media/screenshot-annotator/SKILL.md`

```
<!-- path: data/docs_media/screenshot-annotator/SKILL.md -->
---
name: Annotate screenshots for bug reports or reviews
description: Mark issues on screenshots with clear callouts, numbered labels, and short captions; output annotated images + a summary.
---

## When to use
- Bug reports need “before/after” visual evidence.
- You want a consistent annotation style for review artifacts.

## Inputs
- one or more images (png/jpg)
- list of annotations:
  - bbox/region description
  - label text
  - severity (optional)

## Outputs
- `annotated_<name>.png` per input
- `annotations.md` summarizing each marker

## Procedure
1. For each image, define 1–6 markers max (avoid clutter).
2. Use consistent numbering and short labels.
3. Ensure contrast and readability at 100% zoom.
4. Export annotated images.
5. Write a short markdown summary linking marker numbers to explanations.

## Validation
- Markers are legible and unambiguous.
- Summary matches marker numbers exactly.
```

### `data/docs_media/readme-digest/SKILL.md`

```
<!-- path: data/docs_media/readme-digest/SKILL.md -->
---
name: Create a README digest across many repos
description: Aggregate many README.md files, normalize structure, and produce a single digest for discovery and brainstorming.
---

## When to use
- You have many repos and need a fast “what do we have?” view.
- You want to spot duplicated capabilities and gaps.

## Inputs
- root directory containing repos
- digest format:
  - “one file per repo” or “single consolidated file”
- optional rename convention

## Outputs
- `readme_digest/` or `README_DIGEST.md` containing:
  - repo name
  - 5–10 line summary
  - key commands
  - dependencies and runtime
  - “tool candidates” (entrypoints worth wrapping)

## Procedure
1. Locate README files at repo roots.
2. Extract:
   - purpose
   - setup/run commands
   - inputs/outputs
3. Normalize into a standard template per repo.
4. Add an index at top with quick links.
5. Add “tool candidates” section based on detected commands.

## Validation
- Digest includes all repos with a README.
- Each entry has at least purpose + how-to-run.
```

* * *

3) Build trees for the new groups
---------------------------------

```
python run.py build -g project_toolifier -v
python run.py build -g llm_routing -v
python run.py build -g local_devops -v
python run.py build -g docs_media -v
```

After building, set your active group in `config/config.yaml` via `skill_group: <id>` (or select it in the UI if exposed there).

Sources: [GitHub+4GitHub+4GitHub+4](https://raw.githubusercontent.com/ynulihao/AgentSkillOS/main/src/config.py)



---
Powered by [ChatGPT Exporter](https://www.chatgptexporter.com)