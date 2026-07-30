---
name: refactoring-suggestion
description: Search on the refactorings knowledge base for a relevant refactoring for a given code smell.
allowed-tools: Bash(find *) Read
---

## Skill Instructions

You are going to search on ${CLAUDE_SKILL_DIR}/references for refactorings related to the given code smell. You must use the `rule_id` to search on the knowledge base, using `find` and then read the content of the file.

The refactorings are described in Markdown files, each with a Description and a Suggestion section.

Example: For the smell `hidden-side-effects` you are going to execute:

```sh
find ${CLAUDE_SKILL_DIR}/references -name "hidden-side-effects.md"
```
