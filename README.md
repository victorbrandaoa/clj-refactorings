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
chmod +x .claude/skills/kondo-smell-detection/scripts/kondo.sh
```

### clojure-mcp

clojure-mcp is an MCP server that gives Claude native Clojure tools (`clojure_eval`, `clojure_edit`, `grep`, `read_file`, etc.) connected directly to a live nREPL in a target project. The `.mcp.json` at the root of this repo already contains the configuration.

#### One-time setup

1. Make sure the Clojure CLI is version 1.12 or later (clojure-mcp requires it):

```sh
clojure --version  # must be 1.12.x or later
```

If it's older, upgrade via the official Homebrew tap:

```sh
brew unlink clojure
brew install clojure/tools/clojure
```

2. Install clojure-mcp as a Clojure tool:

```sh
clojure -Ttools install-latest :lib io.github.bhauman/clojure-mcp :as mcp
```

#### Per-session usage

Before starting Claude Code, open a terminal inside the target Clojure project and start a headless nREPL server:

```sh
lein repl :start :port 7888
```

Then start Claude Code in this repo. It will read `.mcp.json`, launch clojure-mcp connected to the nREPL, and prompt for approval on first use. After that, Clojure tools are available automatically in every session as long as the nREPL is running.

To use a different port, set `NREPL_PORT` before starting Claude Code:

```sh
NREPL_PORT=1234 claude
```

## Prompts tested

### Prompt 1

I want you to search for smells on the project /home/victor/Documents/git/clerk using /arit-smell-detection, then create a new branch with a name pattern "fix/<smell-name>" using /git-helper. After this use /refactoring-suggestion to find suggestions of refactorings for the specific smell, so @clj-developer can fix all the occurences of the smell according to the suggestion. Finally, use /git-helper to add and commit the fix

### Prompt 2

For the repository <url>, I want you to follow the steps bellow:

1. Fork the repository for me using /gh-helper.
2. Clone the repository within <destination-path> using /git-helper with ssh method.
3. Then, use </arit-smell-detection or /kondo-smell-detection> to find smells on the project.
4. Create a new branch with a name pattern "fix/<smell-name>" using /git-helper.
5. Use /refactoring-suggestion to find suggestions of refactorings for the specific smell, so @clj-developer can fix all the occurences of the smell according to the suggestion.
6. Commit the fixes using /git-helper.
7. Push the branch to the forked remote repository using /git-helper.
8. Create a pull request for the original repo using /gh-helper.
9. Show me the link to the pull request.

### Prompt 3

You need to run the following command using /gh-helper to find clojure repositories.

```sh
gh search repos --language=Clojure --updated=">=2023-01-01" --stars=">=100" --sort=stars --limit=10
```

Then, for each repository found, follow the steps below:

Important notes:
 - You must focus on clojure specific tests and linters. Ignore any other language.
 - If you find missing tool or dependency mismatch, just list them in the end (not in the csv) and skip the repository.

1. Clone the repository within /home/victor/Documents/git/clojure-search-tests using /git-helper with ssh method.
2. Ask @clj-tester to find out how to run tests and linters available on the project and apply them.
3. Write an entry on a csv file within /home/victor/Documents/git/clojure-search-tests called scrap.csv with the following columns:
	- repo-name
	- repo-url
	- passing-tests (true/false)
	- passing-linters (true/false)
	- issues (empty if no issue was found running tests and linters, otherwise list all issues found wiht execution logs)

### Prompt 4

Then, for each repository found on /home/victor/Documents/git/clojure-search-tests, follow the steps below:

Important notes:
 - You must focus on clojure specific tests and linters. Ignore any other language.
 - If you find missing tool or dependency mismatch, just list them in the end (not in the csv) and skip the repository.
 - If it is not a clojure-related tool missing, explain why is it required in the end.
 - You are not allowed to edit any code in the provided repository.

1. Ask ops_developer to create a Dcokerfile for the project.
2. Ask @clj-tester to run the tests and linters inside the container using the commands given by ops_developer and return the results.
3. Write an entry on a csv file within /home/victor/Documents/git/clojure-search-tests called scrap.csv with the following columns:
	- repo-name
	- repo-url
	- passing-tests (true/false)
	- passing-linters (true/false)
	- issues (empty if no issue was found running tests and linters, otherwise list all issues found wiht execution logs)

### Prompt 5

For the repositories present on leiningen_projects_summary.csv that have lein command working and have tests running, I want you to follow the steps bellow:

1. Verify if the project was cloned within ~/Documents/tmp/refactorings.
2. If not, clone the repository within ~/Documents/tmp/refactorings using /git-helper.
3. Then, use /arit-smell-detection to find smells on the project.
4. Then, for the smells (blocking-inside-go, conditional-build-up and production-doall), verify if there are tests that exercise the code that has the smell.
5. If there are tests that exercise that specific part of the code that has the smell:
  5.1. Write a md file within the repo summarize which of the three smells were found, where they are located on the code and where the test that exercise them are located.

### Prompt 6

For the repo juji-io/datalevin, I want you to follow the steps bellow:

1. Clone the repository within /home/victor/Documents/tmp/refactorings using /git-helper if not cloned yet.
2. Then, use /arit-smell-detection to find smells on the project.
3. Then, for the smells present on the repo, verify if there are tests that exercise the code that has the smell. Search for usages of the namespaces, functions and vars across the codebase to find tests that exercise the code.
  3.1. If there are no tests that exercise the parts of the code that have smells, please ask @clj-tester to generate tests for the code that has the smell.
  3.2. Then, use @clj-tester to run the tests and linters available on the project and return the results. If necessary, iterate until the tests work.
4. Use /refactoring-suggestion to find suggestions of refactorings for the specific smell, so @clj-developer can fix all the occurences of the smell according to the suggestion.
5. Use @clj-tester to run the tests and linters and verify if the refatorings were done correctly.
6. Then, use /arit-smell-detection to check if the smells are gone.

### Prompt 7

For the repo juji-io/datalevin, I want you to follow the steps bellow:

1. Clone the repository within /home/victor/Documents/tmp/refactorings using /git-helper if not cloned yet.
2. Then, use /arit-smell-detection to find smells on the project.
3. Then, for the smells present on the repo, verify if there are tests that exercise the code that has the smell. Search for usages of the namespaces, functions and vars across the codebase to find tests that exercise the code.
  3.1. If there are no tests that exercise the parts of the code that have smells, please ask @clj-tester to generate tests for the code that has the smell.
  3.2. Then, use @clj-tester to run the tests and linters available on the project and return the results. If necessary, iterate until the tests work.
4. Load clojure-mcp to help you with the remaining steps. Use it to double check your changes.
5. Use /refactoring-suggestion to find suggestions of refactorings for the specific smell, so @clj-developer can fix the occurences of the smell according to the suggestion.
6. Use @clj-tester to run the tests and linters and verify if the refatorings were done correctly.
7. Then, use /arit-smell-detection to check if the smells are gone.

### Prompt 8

For the repo clojure-emacs/cider-nrepl, I want you to follow the steps bellow:

Note: No need to ask if a smell should be fixed or not, you should fix it regardless of its level. You are only allowed to ignore a smell if it is a false positive.

1. Clone the repository within /home/victor/Documents/tmp/refactorings using /git-helper if not cloned yet.
2. Then, use /arit-smell-detection to find smells on the project, filter out any smells within test code and benchmark code.
3. Then, ask @clj-tester to find out if there are working tests that exercise the parts of the code that have smells. If not, it must generate the tests and make sure they pass.
4. Check if you can connect to clojure-mcp, if not, there is a .mcp.json file in the root of this repo, use it to connect to clojure-mcp. Use this mcp to help you with the remaining steps. Use it to double check your changes.
5. Use /refactoring-suggestion to find suggestions of refactorings for the specific smell, so @clj-developer can fix the occurences of the smell according to the suggestions. This should be really straight forward fixes for @clj-developer.
6. Use @clj-tester to run the tests and linters and verify if the refatorings were done correctly.
7. Then, use /arit-smell-detection to check if the smells are gone.


### Prompt 9

For the repo thheller/shadow-cljs within /home/victor/Documents/tmp/refactorings, I want you to follow the steps bellow:

Note: No need to ask if a smell should be fixed or not, you should fix it regardless of its level. You are only allowed to ignore a smell if it is a false positive.

1. Use /arit-smell-detection to find smells on the project, filter out any smells within test code and benchmark code. Save the scan result in a json file within the project called scan-before.json.
2. Use @clj-tester to find out if there are working tests that exercise the parts of the code that have smells. If not, it must generate the tests and make sure they pass.
  2.1. If the tests are not running you must stop and explain why the tests are not running and the results.
3. Check if you can connect to clojure-mcp, if not, there is a .mcp.json file in the root of this repo, use it to connect to clojure-mcp. Use this mcp to help you with the remaining steps. Use it to double check your changes.
4. Use /refactoring-suggestion to find suggestions of refactorings for the specific smell, so @clj-developer can fix the occurences of the smell according to the suggestions. This should be really straight forward fixes for @clj-developer.
5. Use @clj-tester to run the tests and linters and verify if the refatorings were done correctly.
6. Then, use /arit-smell-detection to check if the smells are gone. Save the scan result in a json file within the project called scan-after.json.

### Prompt 10

For the repo xtdb/xtdb within /home/victor/Documents/tmp/refactorings, I want you to follow the steps bellow:

Note: No need to ask if a smell should be fixed or not, you should fix it regardless of its level. You are only allowed to ignore a smell if it is a false positive.

1. Use /arit-smell-detection to find smells on the project, filter out any smells within test code and benchmark code. Save the scan result in a json file within the project called scan-before.json.
2. Use @clj-tester to find out if there are working tests that exercise the parts of the code that have smells. If not, it must generate the tests and make sure they pass.
  2.1. If the tests are not running you must stop and explain why the tests are not running and the results.
3. Use /refactoring-suggestion to find suggestions of refactorings for the specific smell, so @clj-developer can fix the occurences of the smell according to the suggestions. This should be really straight forward fixes for @clj-developer.
4. Use @clj-tester to run the tests and linters and verify if the refatorings were done correctly.
5. Then, use /arit-smell-detection to check if the smells are gone. Save the scan result in a json file within the project called scan-after.json.

### Prompt 11

For the repo xtdb/xtdb within /home/victor/Documents/tmp/refactorings, I want you to follow the steps bellow:

Note: No need to ask if a smell should be fixed or not, you should fix it regardless of its level. You are only allowed to ignore a smell if it is a false positive.

1. Use /arit-smell-detection to find smells on the project, filter out any smells within test code and benchmark code. Save the scan result in a json file within the project called scan-before.json.
2. Use @clj-tester to find out if there are working tests that exercise the parts of the code that have smells. If not, it must generate the tests and make sure they pass.
  2.1. If the tests are not running you must stop and explain why the tests are not running and the results.
3. Use /refactoring-suggestion to find suggestions of refactorings for the specific smell, so @clj-developer can fix the occurences of the smell according to the suggestions. This should be really straight forward fixes for @clj-developer.
4. Use @clj-tester to run the tests and linters and verify if the refatorings were done correctly.
5. Then, use /arit-smell-detection to check if the smells are gone. Save the scan result in a json file within the project called scan-after.json.
6. Format your output just with the essential information, as shown bellow:

```md
Project: [project-name]

Smells:

<!-- For each smell found do: -->
[smell-name]: [number-of-occurrences-before] -> [number-of-occurrences-after]
  - False Positives: [number-of-false-positives]
    - [explanation-of-why-they-are-false-positives]

Command(s) To Run the Whole Test Suite:

```bash
[command-to-run-tests]
...
```

Tests Coverage:

<!-- For each smell found do: -->
[smell-name]: [number-of-tests-before] -> [number-of-tests-after]
  <!-- For each test found/created do: -->
  - [absolute-path-of-test-file-exercising-the-smell-before-and-after]:[test-line-before-and-after]
```