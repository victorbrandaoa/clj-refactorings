# Description

This smell occurs when code relies on namespaces whose dependencies are not made explicit through clear and precise :require declarations. This may happen through broad imports such as :use or :refer :all, which obscure the origin of symbols, or by relying on namespaces that happen to be loaded indirectly by other libraries or by Clojure's runtime implementation. Such practices create hidden coupling, reduce code clarity, and make static analysis, refactoring, and maintenance more difficult. They may also lead to symbol conflicts, namespace pollution, or code that depends on implementation details rather than explicit declarations.

```clj
(ns foo
  (:require [clojure.string :refer :all]) ; imports all symbols from clojure.string
  (:use clojure.set))                     ; makes all symbols from clojure.set available
```

# Suggestion

Rewrite the namespace declaration to use explicit :require for each dependency. Avoid using :refer :all or :use, as these can obscure the code's dependencies and make it harder to understand and maintain.
