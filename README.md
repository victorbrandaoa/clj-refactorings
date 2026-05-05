# clj-refactorings

## Prompts tested

### Prompt 1

I want you to search for smells on the project /home/victor/Documents/git/clerk using $smell-detection, then create a new branch with a name pattern "fix/<smell-name>" using $git-helper. After this use $refactoring-suggestion to find suggestions of refactorings for the specific smell, so clj_developer can fix all the occurences of the smell according to the suggestion. Finally, use $git-helper to add and commit the fix

### Prompt 2

For the repository <url>, I want you to follow the steps bellow:

1. Fork the repository for me.
2. Clone the repository within /home/victor/Documents/git using the ssh method.
3. Then, use $smell-detection to find smells on the project.
4. Create a new branch with a name pattern "fix/<smell-name>".
5. Use $refactoring-suggestion to find suggestions of refactorings for the specific smell, so clj_developer can fix all the occurences of the smell according to the suggestion.
6. Commit the fixes.
7. Push the branch to the repository.
8. Create a pull request for the original repo.
9. Show me the link to the pull request.