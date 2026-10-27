# GitHub repository metadata and recommended owner settings

The source repository is `https://github.com/shadowhunter-92/TRINITY`.

**Suggested repository display name:** `TRINITY` (already set).

**Suggested About description (copy into GitHub Settings):**

> Open-source research lab for AI runtime verification, industrial interoperability, and efficient data exchange.

**Suggested topics:** `interoperability`, `ai-infrastructure`, `industrial-automation`,
`modbus`, `serialization`, `benchmarking`, `python`, `open-source`, `systems-engineering`.

**Website:** Leave empty until a real website is published.

## Owner-only GitHub UI changes

The available GitHub connection can upload source files, but does not expose
repository metadata and branch-protection configuration. The owner should:

1. Open **About → gear icon** and paste the description/topics above.
2. Open **Settings → General** to verify repository name and visibility.
3. Import [the version-controlled JSON branch ruleset](../.github/rulesets/main-protection.json) through **Settings → Rules → Rulesets → New ruleset → Import a ruleset**. Follow [the step-by-step import instructions](RULESET_IMPORT.md); committing JSON does not activate protection.
4. Open **Settings → Code security and analysis** and enable available scanning,
   dependency alerts, and private vulnerability reporting where supported.
5. Verify GitHub Actions are enabled under **Settings → Actions**.
6. Publish releases only after independent versioned verification; v0.1.0 is a research
   snapshot, not production software.

Do not enable automatic deployment to industrial networks or external services.
