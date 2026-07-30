# Description

This structural anti-pattern occurs when a project uses single-segment namespaces (e.g., digest or config instead of my-app.digest or my-app.config). This practice violates the standard, hierarchical naming convention of the Clojure ecosystem, causing issues: it increases the risk of global naming collisions, reduces the clarity of code organization, and frequently leads to tooling errors that rely on predictable, qualified names.

```clj
;; Not from source
(ns digest) 
(defn md5 [s] ...)
```

# Suggestion

Rewrite the namespace to use a hierarchical name, such as my-app.digest.
