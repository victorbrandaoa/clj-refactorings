---
name: test-discovery
description: For a given clojure project, discover how to execute the whole test suite.
---

## Instructions

Input:
- Path to the project that will be analyzed;

Output:
- The command that execute tests and any necessary notes;

Restrictions:
- Do not change tests that might fail;
- Do just a discovery: which command successfully run the test suite? and is the test suite green?

1. Start looking at the project configuration files, and the documentation present on the project.
  1.1. If the project documentation has links to other documentations, you are allowed to retrieve them if necessary.

2. Identify which tool the project use for the build process and for running tests.

3. Build the command that execute the enteri test suite of the project, and run it.
  3.1. If the suite fail to run (missing tooling, unresolved dependency, broken build), stop here and report the blocker.

4. When the tests run successfully finishes, you must write the exact commands that worked on the output and add any note you might think it is important. Follow the template below:

```md
# Command to run tests

Notes on the usage of the cmd to run the tests:
Note 1: [...]
Note 2: [...]

```sh
<-working-cmd-to-run-tests>
```
```
