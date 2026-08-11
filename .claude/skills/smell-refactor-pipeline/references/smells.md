# Catalog of Clojure-related code smells

A smaller version of the [clj-smells-catalog](https://github.com/nufuturo-ufcg/clj-smells-catalog) README, restricted to the following smells:

- Production `doall`
- Blocking Inside Go
- Conditional Build-Up
- Redundant `do` block
- Implicit Namespace Dependencies
- Private Multimethods
- Direct usage of `clojure.lang.RT`
- Misuse of Channel Closing Semantics
- Single-segment Namespace

### Production `doall`

* __Description:__ This code smell occurs when the `doall` function is used in production code to force realization of lazy sequences, often to trigger side effects or avoid deferred evaluation. While `doall` can be useful in REPL experimentation, its use in production undermines one of Clojure’s core strengths: laziness. For large or infinite sequences, this can lead to memory spikes and unpredictable performance. In production contexts, doall often signals poor abstraction choices and should prompt reconsideration of the control flow or evaluation strategy.

* __Example:__
```clojure
(defn print-evens []
  (doall (map #(println %) (filter even? (range 1000)))))

(print-evens)
```

---

### Blocking Inside Go

* __Description:__ This code smell occurs when a blocking operation (e.g., `a/alts!!`, `a/<!!`, `a/>!!`, or other blocking I/O calls) is used inside a `go` block. `go` blocks are designed for non-blocking concurrency and execute on a finite thread pool. Introducing blocking calls inside them violates this model, potentially exhausting the thread pool and preventing other tasks from progressing. This can lead to thread starvation, deadlocks, and overall performance degradation.

* __Example:__
```clojure
;; Not from source
(a/go
  (a/alts!! [started-chan (a/timeout 1000)])
  (a/close! result-chan))
```

---

### Conditional Build-Up

* __Description:__ This code smell occurs when a state is incrementally constructed through a series of `let`, `if`, and `assoc` expressions, leading to verbose and imperative-style code. Rather than clearly expressing the transformation logic, this pattern scatters conditional state mutations across multiple branches, making it harder to reason about the overall flow.

* __Example:__
```clojure
;; Not from source
(let [m {}
      m (if (:a input) (assoc m :a 1) m)
      m (if (:b input) (assoc m :b 2) m)
      m (if (:c input) (assoc m :c 3) m)
      m (if (:d input) (assoc m :d 4) m)
      m (if (:e input) (assoc m :e 5) m)]
  m)
```

---

### Redundant `do` block

* __Description:__ This code smell occurs when developers wrap expressions in a (do ...) block inside constructs that already support an implicit do, such as let, when, fn, try, and others. This redundant use of do adds no semantic value but introduces unnecessary syntax, making the code appear more complex and imperative than it actually is.

* __Example:__
```clojure
(defn process-item [x]
  (when (pos? x)
    (do
      (println "Processing:" x)
      (* x 2))))

(process-item 2)
```

---

### Implicit Namespace Dependencies

* __Description:__ This smell occurs when code relies on namespaces whose dependencies are not made explicit through clear and precise `:require` declarations. This may happen through broad imports such as `:use` or `:refer :all`, which obscure the origin of symbols, or by relying on namespaces that happen to be loaded indirectly by other libraries or by Clojure's runtime implementation. Such practices create hidden coupling, reduce code clarity, and make static analysis, refactoring, and maintenance more difficult. They may also lead to symbol conflicts, namespace pollution, or code that depends on implementation details rather than explicit declarations.

* __Example:__
```clojure
(ns foo
  (:require [clojure.string :refer :all]) ; imports all symbols from clojure.string
  (:use clojure.set))                     ; makes all symbols from clojure.set available
```

---

### Private Multimethods

* __Description:__ The use of a private function (`defn-`) or metadata to define a `defmulti` or its `defmethods`. Multimethods are designed for dynamic, open polymorphism and external extension. Making them private defeats their architectural purpose, forces the abstraction to behave as a closed system, and introduces unnecessary complexity and overhead.

* __Example:__
```clojure
;; Example from source
(defmulti ^:private indenter-fn
  "Multimethod for applying indentation rules to forms."
  ;; Accepts [rule-key list-indent-size [rule-type & args]]
  (fn dispatch
    [_ _ rule]
    (first rule)))
```

---

### Direct usage of `clojure.lang.RT`

* __Description:__ This code smell occurs when Clojure code directly invokes methods from the `clojure.lang.RT` class, such as `clojure.lang.RT/iter`, to perform operations that are not exposed through the public Clojure API. The RT class is part of Clojure's internal implementation and is not intended for direct use in application code. Directly invoking methods from this class can lead to fragile code that is susceptible to breakage with future updates to the language.

* __Example:__
```clojure
(iterator-seq (clojure.lang.RT/iter [1 2 3]))
```

---

### Misuse of Channel Closing Semantics

* __Description:__ This smell occurs when a channel-based data stream uses a custom sentinel value (e.g., `:done`, `:EOF`, `::end`) to signal termination, rather than relying on the standard `core.async` semantic contract. This contract dictates that a stream is terminated by closing the channel with `a/close!`, which causes subsequent reads (`a/<!`) to return `nil`. Violating this semantic coupling introduces brittle inspection logic (`(when (not= :done event) ...)`) and breaks the idiomatic flow control pattern of `when-let` and `loop/recur`.

* __Example:__
```clojure
;; Not from source
(def my-chan (a/chan 1))
(a/put! my-chan :done)

(a/go
  (loop []
    (when-let [event (a/<! my-chan)]
      (when (not= event :done) ; <-- Brittle sentinel check
        (prn "Processing" event)
        (recur)))))
```

---

### Single-segment Namespace

* __Description:__ This structural anti-pattern occurs when a project uses single-segment namespaces (e.g., `digest` or `config` instead of `my-app.digest` or `my-app.config`). This practice violates the standard, hierarchical naming convention of the Clojure ecosystem, causing issues: it increases the risk of global naming collisions, reduces the clarity of code organization, and frequently leads to tooling errors that rely on predictable, qualified names.

* __Example:__
```clojure
;; Not from source
(ns digest) 
(defn md5 [s] ...)
```
