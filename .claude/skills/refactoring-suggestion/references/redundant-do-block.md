# Description

This code smell occurs when developers wrap expressions in a (do ...) block inside constructs that already support an implicit do, such as let, when, fn, try, and others. This redundant use of do adds no semantic value but introduces unnecessary syntax, making the code appear more complex and imperative than it actually is.

```clj
(defn process-item [x]
  (when (pos? x)
    (do
      (println "Processing:" x)
      (* x 2))))

(process-item 2)
```

# Suggestion

Remove the (do ...) block wrapping the body of the when form, as it is redundant.
