# Build, publish and update guide

This guide takes you from the zip file to a live dashboard on the internet, then shows the loop you use
to keep improving it. Total time: about 30 minutes the first time.

## What you need

- A GitHub account (free)
- Python 3.10 or newer: check with `python --version` (or `python3 --version` on macOS)
- Git: check with `git --version`. If missing, install from git-scm.com
- A code editor; VS Code is a good free choice

## Step 1. Unzip and open the project

Unzip `agent-under-watch.zip` somewhere you keep projects, then open a terminal in that folder:

```bash
cd agent-under-watch
```

## Step 2. Run it locally first

```bash
python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
pytest -q                          # expect: 17 passed
streamlit run app.py               # opens http://localhost:8501
```

The first load takes about 15 seconds while it trains the baselines. Stop the app with `Ctrl+C`.

## Step 3. Create an empty repository on GitHub

1. Go to github.com → **+** (top right) → **New repository**.
2. Name: `agent-under-watch`. Choose **Public** (needed for free Streamlit hosting) or Private.
3. **Do not** tick "Add a README", ".gitignore" or "license". The project already has them.
4. Click **Create repository** and keep the page open; it shows your repository URL.

## Step 4. Push the code

In the project folder (replace `YOUR-USERNAME`):

```bash
git init -b main                   # skip if the folder already has a .git folder
git add .
git commit -m "Initial version of Agent Under Watch"
git remote add origin https://github.com/YOUR-USERNAME/agent-under-watch.git
git push -u origin main
```

If Git asks for a password, GitHub needs a **personal access token**, not your account password:
GitHub → Settings → Developer settings → Personal access tokens. Alternatively, install the GitHub CLI and run
`gh auth login` once.

Refresh the GitHub page: your code and README are now there.

## Step 5. Check the automatic tests

Open the **Actions** tab in your repository. A workflow called **tests** runs on every push. It lints the
code, runs all tests, and saves the evaluation metrics as a downloadable artifact. A green tick means
everything passed.

Optional: add a status badge to the top of `README.md`:

```markdown
![tests](https://github.com/YOUR-USERNAME/agent-under-watch/actions/workflows/ci.yml/badge.svg)
```

## Step 6. Deploy the dashboard (free)

1. Go to **share.streamlit.io** and sign in with GitHub.
2. Click **Create app** → **Deploy a public app from GitHub**.
3. Repository: `YOUR-USERNAME/agent-under-watch` · Branch: `main` · Main file path: `app.py`.
4. Click **Deploy**. After a few minutes you get a public link to share with your professor.

The app redeploys automatically every time you push to `main`.

**Optional AI explanations:** in the app's settings on Streamlit Cloud → **Secrets**, add
`ANTHROPIC_API_KEY = "your-key"`, and uncomment `anthropic` in `requirements.txt`. Never commit a key to
GitHub; `.gitignore` already excludes `.env` and `.streamlit/secrets.toml`.

## Step 7. The update loop: use it every time you change something

Work on a branch, so `main` (and your live app) always works:

```bash
git checkout -b add-after-hours-rule   # 1. a branch named after the change
# ... edit files ...
pytest -q                              # 2. tests still pass?
python scripts/evaluate.py --all       # 3. did the metrics improve?
git add .
git commit -m "Escalate sensitive lookups outside working hours"
git push -u origin add-after-hours-rule
```

Then on GitHub: **Compare & pull request** → wait for the green tick → **Merge**. Back in the terminal:

```bash
git checkout main
git pull
```

Your live dashboard updates within a few minutes.

**Good habits for a governance project**

- Record every metric change in `docs/RESULTS_LOG.md` with the date and commit. That history is evidence
  of a controlled, documented change process, which is exactly what NIST AI RMF and ISO/IEC 42001 ask for.
- When you change a threshold, write *why* in the commit message.
- Tag versions you present: `git tag v0.2 && git push --tags`.

## Common problems

| Problem | Fix |
| --- | --- |
| `python` not found | Use `python3` (macOS/Linux) or `py` (Windows) |
| `pip install` fails on scikit-learn | Upgrade pip: `python -m pip install --upgrade pip` |
| `git push` rejected: authentication | Use a personal access token or `gh auth login` |
| Streamlit Cloud: "ModuleNotFoundError" | The package is missing from `requirements.txt` |
| Tests fail after you edit a pack | Every agent needs an `owner`; check YAML indentation (2 spaces) |
