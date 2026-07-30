# Description

This smell occurs when a channel-based data stream uses a custom sentinel value (e.g., :done, :EOF, ::end) to signal termination, rather than relying on the standard core.async semantic contract. This contract dictates that a stream is terminated by closing the channel with a/close!, which causes subsequent reads (a/<!) to return nil. Violating this semantic coupling introduces brittle inspection logic ((when (not= :done event) ...)) and breaks the idiomatic flow control pattern of when-let and loop/recur.

```clj
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

# Suggestion

```clj
;; Refactored version
(def my-chan (a/chan 1))
(a/close! my-chan)

(a/go
  (loop []
    (when-let [event (a/<! my-chan)] ; loop terminates naturally when channel is closed
      (prn "Processing" event)
      (recur))))
```
