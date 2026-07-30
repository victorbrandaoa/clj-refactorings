#!/bin/bash
if [ -z "$KONDO_DIR" ]; then
    echo "KONDO_DIR is not set." >&2
    exit 1
fi

cd "$KONDO_DIR" && clojure -M:clj-kondo/dev "$@"
