# Token Benchmark Playbook (For Dummies & Haters)

You want hard numbers showing how much context `aud query`, `aud refactor`, `aud context`, etc. save compared to brute‑force “read 20 files” workflows. This guide walks through a repeatable benchmark so you can publish deterministic data—no marketing fluff, just measurements.

---

## TL;DR

1. **Pick real questions** your AI agents must answer (e.g., “Who imports Products.tsx?”, “Where is `product_variant_id` assigned?”, “List files calling `AuthService.login`.”).
2. **Measure baseline tokens** by feeding the AI the actual files needed to answer the question (no tooling).
3. **Measure tool-assisted tokens** by running `aud query` / `aud refactor --file ...` locally and only sending the results to the AI.
4. **Repeat for ~10 scenarios**, average the totals, and publish the before/after numbers.

Everything else in this doc shows you exactly how to do that.

---

## 1. Prep work

### 1.1. Ensure TheAuditor data is fresh

Run the index/build steps once per repo version:

```bash
aud full --offline          # Recommended (runs index, detect-patterns, graph)
# OR the minimal combo:
aud index && aud graph build
```

This guarantees `.pf/repo_index.db` + optional `graphs.db` exist so `aud query`/`aud refactor` have data.

### 1.2. Pick representative scenarios

Make a table of real tasks, for example:

| Scenario | Question | Files involved (baseline) | Tool command |
|----------|----------|---------------------------|--------------|
| S1 | “Who imports Products.tsx?” | `frontend/src/pages/dashboard/Products.tsx` + whatever it imports | `aud query --file frontend/src/pages/dashboard/Products.tsx --show-dependencies --show-dependents` |
| S2 | “Where is `product_variant_id` assigned?” | All TS/JS files referencing it | `aud query --search "product_variant_id" --include-tables assignments,symbols --format json` |
| S3 | “List files still referencing `cartItem.product_id`” | POS files, receipts, services | `aud refactor --file profile.yaml` (profile rule) |

10–12 scenarios is usually enough to get a meaningful average.

### 1.3. Decide how you’ll record tokens

Pick a logging method:

- Use your API client’s usage stats (OpenAI/Anthropic return token counts per request).
- If using Claude Desktop or a proxy, enable logs that include prompt/output tokens.
- Create a simple Google Sheet / CSV with columns:
  ```
  Scenario | Approach (baseline/tool) | Prompt tokens | Completion tokens | Total tokens
  ```

---

## 2. Baseline measurement (no tooling)

For each scenario:

1. **Gather the actual files.** Example: for “Who imports Products.tsx?”, open `Products.tsx`, trace imports manually, collect all relevant files.
2. **Send the prompt + file contents** to your AI (whatever model you normally use). Ask the question and let it reason using only raw files. **Do not** use `aud query`/`aud refactor` output.
3. **Record token usage** from the API response/log.
4. **Repeat 3 times** per scenario to smooth out variance; average the token counts for that scenario’s baseline.

Yes, this is tedious. That’s the point—you’ll see how expensive manual context really is.

---

## 3. Tool-assisted measurement

For the same scenarios:

1. **Run the relevant tool command locally** (zero tokens):
   - `aud query --file ... --show-dependencies`
   - `aud query --search ... --include-tables ...`
   - `aud refactor --file profile.yaml` (then copy the relevant rule section)
   - `aud context --file semantic_rules/...` (if you’re benchmarking finding classification)
2. **Send only the tool output** to the AI (e.g., the JSON or text that lists files/lines). Ask the same question.
3. **Record token usage** (prompt + completion).
4. **Repeat 3 times** per scenario; average the numbers.

Most prompts will be tiny because you’re only showing a short structured output, not entire files.

---

## 4. Crunch the numbers

For each scenario:

```
Average baseline tokens  = (baseline run1 + run2 + run3) / 3
Average tool tokens      = (tool run1 + run2 + run3) / 3
Savings                  = baseline - tool
Savings %                = Savings / baseline * 100
```

Then compute overall averages (sum totals across scenarios and divide by #scenarios). Present it in a simple table:

| Scenario | Baseline tokens | Tool tokens | Δ tokens | Δ % |
|----------|-----------------|-------------|----------|-----|
| S1 | 8,200 | 700 | 7,500 | 91% |
| S2 | 15,000 | 1,100 | 13,900 | 93% |
| ... | ... | ... | ... | ... |

Include wall-clock time if possible (baseline vs tool), since the CLIs respond in milliseconds.

---

## 5. Tips for clean runs

- **Use the same model + temperature** for every trial to keep token counts consistent.
- **Reset the conversation** between runs so the AI doesn’t reuse state.
- **Save tool outputs to files** (`aud query ... --save logs/s1.json`) so you can re-run the prompt without re-querying the DB.
- **Version-lock the repo** (e.g., use the same Git commit) so file contents don’t change between baseline and tool runs.

---

## 6. Example script snippet (optional automation)

If you’re using an API directly, you can script the measurement. Pseudocode:

```python
import openai, time

def run_prompt(prompt):
    resp = openai.ChatCompletion.create(model="gpt-4o", messages=[{"role":"user","content":prompt}])
    tokens = resp["usage"]["total_tokens"]
    return tokens

baseline_prompt = open("baseline_S1.txt").read()
tool_prompt = open("tool_S1.txt").read()   # e.g., contains aud query output

baseline_tokens = [run_prompt(baseline_prompt) for _ in range(3)]
tool_tokens = [run_prompt(tool_prompt) for _ in range(3)]

print("Baseline avg:", sum(baseline_tokens)/3)
print("Tool avg:", sum(tool_tokens)/3)
```

You still need to curate the prompts, but this automates the counting.

---

## 7. Share results

Once you’ve got the data:

1. Publish the table + methodology (copy/paste this playbook).
2. Include the exact commands used, models queried, and repo commit hash.
3. Optional: include zipped logs or CSV for reproducibility.

That way nobody can call BS—the benchmark is deterministic and easy to replicate.

---

## FAQ

- **Q:** “What if my repo isn’t indexed?”  
  **A:** Run `aud full` or `aud index` first. If the DB is missing tables, `aud query` will tell you which commands to run.

- **Q:** “Why three runs?”  
  **A:** Token counts fluctuate slightly (especially if the model elaborates differently). Averaging keeps the numbers fair.

- **Q:** “Can I benchmark `aud blueprint` or `aud context`?”  
  **A:** Yes. For blueprint, compare minutes spent summarizing architecture vs one `aud blueprint --structure` call. For context, measure manual triage of findings vs `aud context` output.

- **Q:** “Do I need to show the actual tool outputs?”  
  **A:** For transparency, yes. Attach them to the benchmark report or link to a gist.

---

Now you’ve got a no-excuses, for-dummies measurement plan. Run it, publish the numbers, and let the data shut down the skeptics.*** End Patch
