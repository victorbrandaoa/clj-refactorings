# clj-refactorings

## Configs

### GitHub CLI
Install GitHub CLI with the following commands:

```sh
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo gpg --dearmor -o /usr/share/keyrings/githubcli-archive-keyring.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null

sudo apt update
sudo apt install gh
```

After this, run the following command to authenticate:

```sh
gh auth login
```

### Arit
Follow the steps below:

1. Clone the repository https://github.com/nufuturo-ufcg/clj-smells-arit any place you want;
2. Enter the clj-smells-arit dir and run `go build` to create the `arit` binary;
3. Run `chmod +x arit` to allow execution;
4. Copy `.env.example` to `.env`, and then fill the ARIT_DIR variable with the absolute path to `clj-smells-arit` clone;
5. Finally, run `source .env` to load the env vars.

### Kondo
Follow the steps below:

1. Clone the repository https://github.com/nufuturo-ufcg/clj-kondo any place you want;
2. Copy `.env.example` to `.env`, and then fill the KONDO_DIR variable with the absolute path to `clj-kondo` clone;
3. Run the following commands to make `kondo.sh` executable:

```sh
source .env
chmod +x .agents/skills/kondo-smell-detection/scripts/kondo.sh
```

## Prompts tested

### Prompt 1

I want you to search for smells on the project /home/victor/Documents/git/clerk using $smell-detection, then create a new branch with a name pattern "fix/<smell-name>" using $git-helper. After this use $refactoring-suggestion to find suggestions of refactorings for the specific smell, so clj_developer can fix all the occurences of the smell according to the suggestion. Finally, use $git-helper to add and commit the fix

### Prompt 2

For the repository <url>, I want you to follow the steps bellow:

1. Fork the repository for me using $gh-helper.
2. Clone the repository within /home/victor/Documents/git using $git-helper with ssh method.
3. Then, use <$arit-smell-detection | $kondo-smell-detection> to find smells on the project.
4. Create a new branch with a name pattern "fix/<smell-name>" using $git-helper.
5. Use $refactoring-suggestion to find suggestions of refactorings for the specific smell, so clj_developer can fix all the occurences of the smell according to the suggestion.
6. Commit the fixes using $git-helper.
7. Push the branch to the forked remote repository using $git-helper.
8. Create a pull request for the original repo using $gh-helper.
9. Show me the link to the pull request.
