#!/usr/bin/env clojure
"""
Static, var-level test reachability analysis backed by clj-kondo.

This deliberately does not execute tests: see --help and the adjacent README.
"""
(ns kondo-test-coverage
  (:require [clj-kondo.core :as kondo]
            [clojure.data.json :as json]
            [clojure.java.io :as io]
            [clojure.string :as str]))

(def source-candidates ["src" "src/main" "src/clj" "src/cljc" "src/cljs"])
(def test-candidates ["test" "test/clj" "test/cljc" "test/cljs"])

(def usage "Usage: kondo-test-coverage.clj [options] [project-dir]

Build a static dependency graph with clj-kondo and report production vars that
are reachable from clojure.test/deftest definitions.

Options:
  --source-root PATH    Source root (repeatable; disables source auto-discovery)
  --test-root PATH      Test root (repeatable; disables test auto-discovery)
  --project PATH        Project directory (default: current directory)
  --format FORMAT       json (default) or summary
  --output FILE         Write the JSON report to FILE
  --fail-under PERCENT  Exit 1 when static reachability is below PERCENT
  -h, --help            Show this help

The result is static var reachability, not runtime line or branch coverage.")

(defn die! [message]
  (binding [*out* *err*] (println (str "error: " message)))
  (System/exit 2))

(defn parse-args [args]
  (loop [args args opts {:source-roots [] :test-roots [] :format "json"}]
    (if-let [arg (first args)]
      (case arg
        ("-h" "--help") (assoc opts :help true)
        "--source-root" (recur (nnext args) (update opts :source-roots conj (second args)))
        "--test-root" (recur (nnext args) (update opts :test-roots conj (second args)))
        "--project" (recur (nnext args) (assoc opts :project (second args)))
        "--format" (recur (nnext args) (assoc opts :format (second args)))
        "--output" (recur (nnext args) (assoc opts :output (second args)))
        "--fail-under" (recur (nnext args) (assoc opts :fail-under (second args)))
        (if (str/starts-with? arg "-")
          (die! (str "unknown option " arg))
          (if (:project opts)
            (die! "only one project directory may be supplied")
            (recur (next args) (assoc opts :project arg)))))
      opts)))

(defn absolute [project path]
  (.getCanonicalPath (io/file project path)))

(defn directory? [path]
  (.isDirectory (io/file path)))

(defn canonical-path [path]
  (.getCanonicalPath (io/file path)))

(defn existing-roots [project supplied candidates]
  (let [roots (if (seq supplied)
                (map #(absolute project %) supplied)
                (->> candidates (map #(absolute project %)) (filter directory?)))]
    (doseq [root roots :when (not (directory? root))]
      (die! (str "directory does not exist: " root)))
    (vec (distinct roots))))

(defn var-id [{:keys [ns name]}]
  (str ns "/" name))

(defn contains-position? [definition usage]
  (and (= (:filename definition) (:filename usage))
       (let [start [(:row definition) (:col definition)]
             end   [(or (:end-row definition) (:row definition))
                    (or (:end-col definition) Integer/MAX_VALUE)]
             point [(:row usage) (:col usage)]]
         (and (not (pos? (compare start point)))
              (not (neg? (compare end point)))))))

(defn enclosing-definition [definitions usage]
  (->> definitions
       (filter #(contains-position? % usage))
       (sort-by (fn [{:keys [row end-row]}] (- (or end-row row) row)))
       first))

(defn analyze [project source-roots test-roots]
  (let [result (kondo/run! {:lint (vec (concat source-roots test-roots))
                            :config-dir (absolute project ".clj-kondo")
                            :config {:analysis {:var-definitions {:meta true}}}
                            :cache false})
        definitions (get-in result [:analysis :var-definitions] [])
        usages (get-in result [:analysis :var-usages] [])
        source? #(some (fn [root] (str/starts-with? (canonical-path (:filename %)) root)) source-roots)
        test? #(some (fn [root] (str/starts-with? (canonical-path (:filename %)) root)) test-roots)
        production (->> definitions (filter source?) (sort-by var-id) vec)
        known (into #{} (map var-id definitions))
        test-vars (->> definitions (filter #(and (test? %) (:test %))) (map var-id) set)
        edges (reduce (fn [graph usage]
                        (if-let [owner (enclosing-definition definitions usage)]
                          (let [from (var-id owner)
                                to (str (:to usage) "/" (:name usage))]
                            (if (and (:to usage) (contains? known to))
                              (update graph from (fnil conj #{}) to)
                              graph))
                          graph))
                      {} usages)
        paths (loop [queue (into clojure.lang.PersistentQueue/EMPTY
                                 (map #(vector % [%]) (sort test-vars)))
                     found {}]
                (if-let [[node path] (peek queue)]
                  (if (contains? found node)
                    (recur (pop queue) found)
                    (recur (reduce (fn [q next-node] (conj q [next-node (conj path next-node)]))
                                   (pop queue) (sort (get edges node)))
                           (assoc found node path)))
                  found))
        rows (mapv (fn [definition]
                     (let [id (var-id definition) path (get paths id)]
                       (cond-> {:var id :file (canonical-path (:filename definition))
                                :line (:row definition) :end-line (:end-row definition)
                                :classification (if path "covered" "likely-untested")}
                         path (assoc :test (first path) :path path))))
                   production)
        covered (count (filter #(= "covered" (:classification %)) rows))
        total (count rows)]
    {:project (absolute project ".")
     :analysis "static-var-test-reachability"
     :source-roots source-roots :test-roots test-roots
     :tests (count test-vars) :total-vars total :covered-vars covered
     :likely-untested-vars (- total covered)
     :static-reachability-percent (if (zero? total) 100.0 (* 100.0 (/ covered total)))
     :vars rows}))

(defn summary [{:keys [tests total-vars covered-vars likely-untested-vars static-reachability-percent]}]
  (format "Static test reachability: %.2f%% (%d/%d vars); %d test vars; %d likely untested"
          (double static-reachability-percent) covered-vars total-vars tests likely-untested-vars))

(defn stable-json-data [value]
  (cond
    (map? value) (into (sorted-map-by #(compare (name %1) (name %2)))
                        (map (fn [[k v]] [k (stable-json-data v)]) value))
    (vector? value) (mapv stable-json-data value)
    (set? value) (mapv stable-json-data (sort value))
    :else value))

(defn -main [& args]
  (let [{:keys [help project source-roots test-roots format output fail-under]} (parse-args args)]
    (when help (println usage) (System/exit 0))
    (when-not (#{"json" "summary"} format) (die! "--format must be json or summary"))
    (let [project (or project ".")
          source-roots (existing-roots project source-roots source-candidates)
          test-roots (existing-roots project test-roots test-candidates)]
      (when (empty? source-roots) (die! "no source roots found; pass --source-root"))
      (when (empty? test-roots) (die! "no test roots found; pass --test-root"))
      (let [report (analyze project source-roots test-roots)
            rendered (json/write-str (stable-json-data report))]
        (when output (spit output rendered))
        (if (= format "json")
          (println rendered)
          (println (summary report)))
        (binding [*out* *err*] (println (summary report)))
        (when fail-under
          (let [threshold (Double/parseDouble fail-under)]
            (when (< (:static-reachability-percent report) threshold) (System/exit 1))))))))

(apply -main *command-line-args*)
