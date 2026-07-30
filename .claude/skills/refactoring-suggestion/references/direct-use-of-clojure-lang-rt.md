# Description

This code smell occurs when Clojure code directly invokes methods from the clojure.lang.RT class, such as clojure.lang.RT/iter, to perform operations that are not exposed through the public Clojure API. The RT class is part of Clojure's internal implementation and is not intended for direct use in application code. Directly invoking methods from this class can lead to fragile code that is susceptible to breakage with future updates to the language.

```clj
(iterator-seq (clojure.lang.RT/iter [1 2 3]))
```

# Suggestion

Use the public Clojure API instead of directly invoking methods from the clojure.lang.RT class.
