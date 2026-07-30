# Description

This code smell occurs when a state is incrementally constructed through a series of let, if, and assoc expressions, leading to verbose and imperative-style code. Rather than clearly expressing the transformation logic, this pattern scatters conditional state mutations across multiple branches, making it harder to reason about the overall flow.

```clj
(defn f0 [in] (* in 10))
(defn f1 [in] (+ in 1))
(defn f2 [in] (- in 1))
(defn p1 [in] (pos? in))
(defn p2 [in] (even? in))

(defn foo [in]
  (let [m {:k0 (f0 in)}
        m (if (p1 in) (assoc m :k1 (f1 in)) m)
        m (if (p2 in) (assoc m :k2 (f2 in)) m)]
    m))

(foo 2)
```

# Suggestion

Consider using a more functional way to do this, you can use a more idiomatic clojure way to do this, such as `cond->`, for instance:

```clj
(defn f0 [in] (* in 10))
(defn f1 [in] (+ in 1))
(defn f2 [in] (- in 1))
(defn p1 [in] (pos? in))
(defn p2 [in] (even? in))

(defn foo [in]
  (cond-> {:k0 (f0 in)}
    (p1 in) (assoc :k1 (f1 in))
    (p2 in) (assoc :k2 (f2 in))))

(foo 2)
```
