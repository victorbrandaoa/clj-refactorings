# Description

This code smell occurs when a blocking operation (a/<!!, a/>!!, or general blocking I/O) is called inside a go block. go blocks are designed for non-blocking, cooperative concurrency and execute on a small, fixed-size thread pool. Blocking inside a go block defeats this purpose, risking thread starvation, deadlocks, and system-wide performance degradation.

```clj
(ns my-app.async-fail
  (:require [clojure.core.async :as a]))

(def my-chan (a/chan))

(a/go
  (println "Blocked thread consuming:" (a/<!! my-chan)))
```

# Suggestion

Consider using `a/<!` and `a/>!` instead of `a/<!!` and `a/>!!` when inside a go block.
