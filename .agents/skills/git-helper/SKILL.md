---
name: git-helper
description: Use git tool to manage local git repository.
compatibility: Requires git
allowed-tools: Bash(git:*) Read
---

## Skill Instructions

It uses the git tool to perform git operations on a given local repository.

Allowed git commands:

```sh
git clone # always use ssh protocol
git log --oneline
git diff
git add <file>
git commit -m "<message>"
git pull origin <base> --rebase
git status
git checkout -b <branch>
git push origin <branch>
```
