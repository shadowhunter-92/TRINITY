# Import TRINITY's main branch-protection ruleset

The **importable GitHub ruleset** is [`.github/rulesets/main-protection.json`](../.github/rulesets/main-protection.json). It is versioned source configuration, but is **not active merely because it is committed**. The repository administrator must import it once in GitHub settings.

1. Download the raw JSON file to your computer from GitHub.
2. Visit [TRINITY repository Rulesets](https://github.com/shadowhunter-92/TRINITY/settings/rules).
3. Choose **New ruleset → Import a ruleset**, select `main-protection.json`, and review its parsed settings.
4. Verify that it targets **only `main`** and enforces pull requests, no deletion, no force pushes and status checks.
5. Verify required CI checks correspond to the current workflow job names: `Python 3.10 / Ubuntu`, `Python 3.11 / Ubuntu`, `Python 3.12 / Ubuntu`, `Python 3.13 / Ubuntu`.
6. Select **Create** to activate it, then check the Rulesets listing to confirm it shows **Active**. Do not assume file upload equals rule activation.

This ruleset requires **zero approving reviews** deliberately: the repository currently has one maintainer, so requiring a separate reviewer could permanently block self-service changes. It **does require pull requests and successful CI checks**, including up-to-date checks on the target branch. For a team, increase the approval count and require code-owner approval as appropriate. The file does not contain bypass actors.

**Warnings**: enabling required checks while a workflow is missing, disabled, renamed or failing can block merges. Before activation, confirm these exact four jobs have recently passed. GitHub settings/rulesets and your subscription may affect feature availability. The GitHub connector used during initial setup does not expose a write action for the settings endpoint, so a human owner must complete the import.

References: [GitHub importing rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/managing-rulesets-for-a-repository#importing-a-ruleset) and [GitHub Rules API](https://docs.github.com/en/rest/repos/rules).
