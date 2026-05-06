---
name: gh-helper
description: Use github cli to manage github repositories.
compatibility: Requires gh
allowed-tools: Bash(gh:*) Read
---

## Skill Instructions

It uses the github cli tool to perform github operations on a given repository.

Allowed github operations:

```sh
gh repo list
gh repo fork <repository>
gh pr create --repo <repository> --base <base-branch> --head <branch> --title <title> --body <body>
```

### Pull Request Creation Instructions

When creating the pull request, you must provide a title and a body following the instructions bellow:

Title:
```md
Fix: <code-smell-name>
```

Body:
```md
This pull request fixes the <code-smell-name> code smell.

### Smell Description:

<smell-description>

### Refactoring Suggestion:

<refactoring-suggestion>
```
