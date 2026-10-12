---
name: identify-leiningen
description: Use a deterministic script to verify if a set of projects use leiningen as build tool.
---

## Input

repos_index - a csv file with the the columns repo, path and clonned_success.
repos_path - the path to the directory where all the projects from the index are clonned.
lein_config_path - the path to the directory where you will place the lein_config.csv

## Output

repos_index - updated version of the input csv with two new columns called uses_leiningen, which is True or False.
report - summary of how many projects use leiningen as build tool.
lein_config - a csv file with multi-rows by repo and project.clj identified saved within lein_config_path.

## Instructions

1. Run the script to check which projects use leiningen using the command bellow:

```sh
${CLAUDE_SKILL_DIR}/scripts/detect_lein.sh repos_path
```

2. Double check the detections to see if any of them is a false positive.

3. Update repos_index by adding the columns uses_leiningen.

4. Save the lein_config.csv with the columns repo and project_clj_path for each project, save it in lein_config_path.

5. Report a summary of how many projects use leiningen and any false positives you might found. Include the number of project.clj files by project in your report.
