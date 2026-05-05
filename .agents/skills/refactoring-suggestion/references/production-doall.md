# Description

This code smell occurs when the doall function is used in production code to force realization of lazy sequences, often to trigger side effects or avoid deferred evaluation. While doall can be useful in REPL experimentation, its use in production undermines one of Clojure’s core strengths: laziness. For large or infinite sequences, this can lead to memory spikes and unpredictable performance. In production contexts, doall often signals poor abstraction choices and should prompt reconsideration of the control flow or evaluation strategy.

```clj
(defn print-evens []
  (doall (map #(println %) (filter even? (range 1000)))))

(print-evens)
```

# Suggestion

Consider using eager operations (mapv, into, vec) or restructuring to avoid forcing evaluation.