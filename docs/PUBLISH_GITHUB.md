# Publish to GitHub

Target: **MAPIT-Project/MAPIT-AI-Tool-v1**, visibility: **public**.
Run these commands inside this fresh repository, not inside the original checkout.
You need permission to create public repositories in the MAPIT-Project organization.
Install GitHub CLI (`gh`) if needed, then authenticate.

```bash
gh auth login --hostname github.com
git init -b main
git add .
git diff --cached --stat
git diff --cached --check
git status --short
# Review the staged files; do not include local credentials or datasets.
git commit -m "Initial public source release of MAPIT AI Tool v1"
gh repo create MAPIT-Project/MAPIT-AI-Tool-v1 --public --source=. --remote=origin --description "MAPIT AI Domain Expert Tool: research discovery, funding calls and partner exploration"
git push -u origin main
```

If Git asks for author identity, configure `git config user.name` and
`git config user.email` with your intended public commit identity before committing.
The repository is created by the `gh repo create` command and uploaded by `git push`.
No remote repository was created during local preparation.

Alternative: create an **empty public repository** with this exact name under
MAPIT-Project in GitHub's UI (do not generate a README, license or .gitignore there),
then replace `gh repo create` above with:

```bash
git remote add origin https://github.com/MAPIT-Project/MAPIT-AI-Tool-v1.git
git push -u origin main
```

Choose one method. If `origin` or the repository already exists, inspect it before
changing anything; do not force-push. If public-repository creation is restricted,
an organization administrator must grant access or create the empty repository.

CLI reference: https://cli.github.com/manual/gh_repo_create
