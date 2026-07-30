# Description

The use of a private function (defn-) or metadata to define a defmulti or its defmethods. Multimethods are designed for dynamic, open polymorphism and external extension. Making them private defeats their architectural purpose, forces the abstraction to behave as a closed system, and introduces unnecessary complexity and overhead.

```clj
;; Example from source
(defmulti ^:private indenter-fn
  "Multimethod for applying indentation rules to forms."
  ;; Accepts [rule-key list-indent-size [rule-type & args]]
  (fn dispatch
    [_ _ rule]
    (first rule)))
```

# Suggestion

Remove the private metadata from the multimethod or convert it to a standard private function, depending on the specific requirements of the abstraction.
