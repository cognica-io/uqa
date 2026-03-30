import { useCallback, useEffect, useRef, useState } from "react"

import Editor, { type Monaco } from "@monaco-editor/react"
import type { editor } from "monaco-editor"

import {
  ChevronDownIcon,
  ChevronRightIcon,
  CircleStackIcon,
  ClockIcon,
  CommandLineIcon,
  ExclamationTriangleIcon,
  PlayIcon,
  TableCellsIcon,
  TagIcon,
} from "@heroicons/react/24/outline"

import {
  EXAMPLE_QUERIES,
  CATEGORY_LABELS,
  ExampleQuery,
} from "./example-queries"
import { SAMPLE_DATA, useUQAEngine, QueryResult } from "./use-uqa-engine"

type MonacoEditorInstance = editor.IStandaloneCodeEditor
const MonacoEditor = Editor

function configureMonaco(monaco: Monaco) {
  monaco.editor.defineTheme("uqa-light", {
    base: "vs",
    inherit: true,
    rules: [
      { token: "keyword", foreground: "7c3aed", fontStyle: "bold" },
      { token: "operator.sql", foreground: "7c3aed" },
      { token: "number", foreground: "0284c7" },
      { token: "string", foreground: "059669" },
      { token: "comment", foreground: "9ca3af", fontStyle: "italic" },
      { token: "identifier", foreground: "1e293b" },
      { token: "type", foreground: "0369a1" },
      { token: "predefined", foreground: "c026d3" },
    ],
    colors: {
      "editor.background": "#ffffff",
      "editor.foreground": "#1e293b",
      "editor.lineHighlightBackground": "#f8fafc",
      "editorLineNumber.foreground": "#cbd5e1",
      "editorLineNumber.activeForeground": "#94a3b8",
      "editor.selectionBackground": "#dbeafe",
      "editorCursor.foreground": "#1e293b",
    },
  })

  monaco.editor.defineTheme("uqa-dark", {
    base: "vs-dark",
    inherit: true,
    rules: [
      { token: "keyword", foreground: "a78bfa", fontStyle: "bold" },
      { token: "operator.sql", foreground: "a78bfa" },
      { token: "number", foreground: "38bdf8" },
      { token: "string", foreground: "34d399" },
      { token: "comment", foreground: "6b7280", fontStyle: "italic" },
      { token: "identifier", foreground: "e2e8f0" },
      { token: "type", foreground: "7dd3fc" },
      { token: "predefined", foreground: "e879f9" },
    ],
    colors: {
      "editor.background": "#111827",
      "editor.foreground": "#e2e8f0",
      "editor.lineHighlightBackground": "#1e293b",
      "editorLineNumber.foreground": "#4b5563",
      "editorLineNumber.activeForeground": "#6b7280",
      "editor.selectionBackground": "#1e3a5f",
      "editorCursor.foreground": "#e2e8f0",
    },
  })
}

const DEFAULT_QUERY =
  "SELECT title, director, year, genre, rating\nFROM movies\nORDER BY rating DESC\nLIMIT 10"

function SchemaPanel() {
  const [expanded, setExpanded] = useState(true)

  const columns = [
    { name: "id", type: "SERIAL", key: true },
    { name: "title", type: "TEXT", indexed: true },
    { name: "director", type: "TEXT", indexed: true },
    { name: "year", type: "INTEGER" },
    { name: "genre", type: "TEXT", indexed: true },
    { name: "rating", type: "REAL" },
    { name: "description", type: "TEXT", indexed: true },
  ]

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 w-full px-4 py-3 bg-gray-50 dark:bg-gray-800/50 text-left text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
      >
        <CircleStackIcon className="size-4" />
        <span>Schema: movies</span>
        <span className="ml-auto text-xs text-gray-400">
          {SAMPLE_DATA.length} rows
        </span>
        {expanded ? (
          <ChevronDownIcon className="size-4" />
        ) : (
          <ChevronRightIcon className="size-4" />
        )}
      </button>
      {expanded && (
        <div className="px-4 py-3">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-gray-500 dark:text-gray-400 uppercase">
                <th className="text-left pb-2 font-medium">Column</th>
                <th className="text-left pb-2 font-medium">Type</th>
                <th className="text-left pb-2 font-medium">Index</th>
              </tr>
            </thead>
            <tbody>
              {columns.map((col) => (
                <tr
                  key={col.name}
                  className="border-t border-gray-100 dark:border-gray-800"
                >
                  <td className="py-1.5 font-mono text-xs text-gray-800 dark:text-gray-200">
                    {col.key && (
                      <span className="text-amber-500 mr-1" title="Primary Key">
                        *
                      </span>
                    )}
                    {col.name}
                  </td>
                  <td className="py-1.5 font-mono text-xs text-gray-500 dark:text-gray-400">
                    {col.type}
                  </td>
                  <td className="py-1.5 text-xs text-gray-400">
                    {col.indexed && (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 text-[10px] font-medium">
                        FTS
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="mt-3 pt-3 border-t border-gray-100 dark:border-gray-800">
            <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">
              Graph: cinema
            </p>
            <div className="space-y-1 text-xs font-mono text-gray-600 dark:text-gray-400">
              <p>
                <span className="text-purple-600 dark:text-purple-400">(:Movie)</span>
                {" -[:DIRECTED_BY]-> "}
                <span className="text-green-600 dark:text-green-400">(:Director)</span>
              </p>
              <p>
                <span className="text-purple-600 dark:text-purple-400">(:Movie)</span>
                {" -[:HAS_GENRE]-> "}
                <span className="text-orange-600 dark:text-orange-400">(:Genre)</span>
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function ExampleQueryPanel({
  onSelect,
}: {
  onSelect: (query: string) => void
}) {
  const [activeCategory, setActiveCategory] =
    useState<ExampleQuery["category"]>("basic")

  const categories = Object.entries(CATEGORY_LABELS) as [
    ExampleQuery["category"],
    string,
  ][]

  const filtered = EXAMPLE_QUERIES.filter(
    (q) => q.category === activeCategory,
  )

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 bg-gray-50 dark:bg-gray-800/50 text-sm font-medium text-gray-700 dark:text-gray-300">
        <CommandLineIcon className="size-4" />
        <span>Example Queries</span>
      </div>
      <div className="px-3 pt-3 pb-1">
        <div className="flex flex-wrap gap-1.5 mb-3">
          {categories.map(([key, label]) => (
            <button
              key={key}
              onClick={() => setActiveCategory(key)}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                activeCategory === key
                  ? "bg-gray-800 dark:bg-gray-200 text-white dark:text-gray-800"
                  : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="flex flex-col gap-1.5 pb-2">
          {filtered.map((example) => (
            <button
              key={example.label}
              onClick={() => onSelect(example.query)}
              className="flex flex-col items-start gap-0.5 px-3 py-2 rounded text-left hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors group"
            >
              <div className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300 group-hover:text-gray-900 dark:group-hover:text-white transition-colors">
                <TagIcon className="size-3.5 text-gray-400" />
                {example.label}
              </div>
              <p className="text-xs text-gray-400 dark:text-gray-500 pl-5.5">
                {example.description}
              </p>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

function SQLEditor({
  value,
  onChange,
  onExecute,
  executing,
}: {
  value: string
  onChange: (value: string) => void
  onExecute: () => void
  executing: boolean
}) {
  const editorRef = useRef<MonacoEditorInstance | null>(null)

  const lineCount = value.split("\n").length
  const editorHeight = Math.max(220, Math.min(400, lineCount * 20 + 20))

  const handleEditorMount = useCallback(
    (editor: MonacoEditorInstance, monaco: Monaco) => {
      editorRef.current = editor

      editor.addAction({
        id: "run-query",
        label: "Run Query",
        keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter],
        run: () => onExecute(),
      })
    },
    [onExecute],
  )

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 bg-gray-50 dark:bg-gray-800/50 border-b border-gray-200 dark:border-gray-700">
        <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
          SQL
        </span>
        <div className="flex items-center gap-3">
          <span className="text-[11px] text-gray-400 hidden sm:inline">
            {"\u2318"}+Enter to run
          </span>
          <button
            onClick={onExecute}
            disabled={executing || !value.trim()}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-gray-800 dark:bg-gray-200 text-white dark:text-gray-800 text-xs font-medium hover:bg-gray-700 dark:hover:bg-gray-300 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            <PlayIcon className="size-3.5" />
            Run
          </button>
        </div>
      </div>
      <div style={{ height: editorHeight }}>
        <MonacoEditor
          language="sql"
          theme="uqa-light"
          value={value}
          onChange={(v) => onChange(v ?? "")}
          onMount={handleEditorMount}
          beforeMount={configureMonaco}
          options={{
            minimap: { enabled: false },
            scrollBeyondLastLine: false,
            fontSize: 13,
            lineNumbers: "on",
            lineNumbersMinChars: 3,
            glyphMargin: false,
            folding: false,
            lineDecorationsWidth: 8,
            renderLineHighlight: "none",
            overviewRulerLanes: 0,
            hideCursorInOverviewRuler: true,
            overviewRulerBorder: false,
            scrollbar: {
              vertical: "auto",
              horizontal: "auto",
              verticalScrollbarSize: 8,
              horizontalScrollbarSize: 8,
            },
            padding: { top: 12, bottom: 12 },
            wordWrap: "on",
            automaticLayout: true,
            tabSize: 2,
          }}
          loading={
            <div className="flex items-center justify-center h-full bg-white dark:bg-gray-900">
              <span className="text-xs text-gray-400">
                Loading editor...
              </span>
            </div>
          }
        />
      </div>
    </div>
  )
}

function ResultTable({ result }: { result: QueryResult }) {
  if (result.error) {
    return (
      <div className="border border-red-200 dark:border-red-900/50 rounded-lg overflow-hidden">
        <div className="flex items-center gap-2 px-4 py-3 bg-red-50 dark:bg-red-900/20 border-b border-red-200 dark:border-red-900/50">
          <ExclamationTriangleIcon className="size-4 text-red-500" />
          <span className="text-sm font-medium text-red-700 dark:text-red-400">
            Error
          </span>
          <span className="ml-auto text-xs text-red-400">
            {result.elapsed.toFixed(1)}ms
          </span>
        </div>
        <div className="px-4 py-3 bg-white dark:bg-gray-900">
          <pre className="text-sm text-red-600 dark:text-red-400 whitespace-pre-wrap font-mono">
            {result.error}
          </pre>
        </div>
      </div>
    )
  }

  if (!result.result) return null

  const { columns, rows } = result.result

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 bg-gray-50 dark:bg-gray-800/50 border-b border-gray-200 dark:border-gray-700">
        <TableCellsIcon className="size-4 text-gray-500" />
        <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
          Result
        </span>
        <span className="text-xs text-gray-400">
          {rows.length} {rows.length === 1 ? "row" : "rows"}
          {columns.length > 0 && <> / {columns.length} columns</>}
        </span>
        <span className="ml-auto flex items-center gap-1 text-xs text-gray-400">
          <ClockIcon className="size-3" />
          {result.elapsed.toFixed(1)}ms
        </span>
      </div>
      {rows.length > 0 ? (
        <div className="overflow-auto max-h-[480px]">
          <table className="w-full text-sm">
            <thead className="sticky top-0 z-10">
              <tr className="bg-gray-50 dark:bg-gray-800/30">
                {columns.map((col) => (
                  <th
                    key={col}
                    className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide whitespace-nowrap border-b border-gray-200 dark:border-gray-700"
                  >
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr
                  key={i}
                  className="border-b border-gray-100 dark:border-gray-800 last:border-b-0 hover:bg-gray-50 dark:hover:bg-gray-800/30 transition-colors"
                >
                  {columns.map((col) => (
                    <td
                      key={col}
                      className="px-4 py-2 text-gray-700 dark:text-gray-300 whitespace-nowrap max-w-[400px] truncate font-mono text-xs"
                      title={String(row[col] ?? "")}
                    >
                      {formatCell(row[col])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="px-4 py-8 text-center text-sm text-gray-400">
          Query executed successfully. No rows returned.
        </div>
      )}
    </div>
  )
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return "NULL"
  if (typeof value === "number") {
    if (Number.isInteger(value)) return String(value)
    return value.toFixed(4)
  }
  return String(value)
}

function QueryHistory({
  history,
  onSelect,
}: {
  history: { query: string; result: QueryResult }[]
  onSelect: (query: string) => void
}) {
  const [expanded, setExpanded] = useState(false)

  if (history.length === 0) return null

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 w-full px-4 py-3 bg-gray-50 dark:bg-gray-800/50 text-left text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
      >
        <ClockIcon className="size-4" />
        <span>History</span>
        <span className="ml-auto text-xs text-gray-400">
          {history.length} {history.length === 1 ? "query" : "queries"}
        </span>
        {expanded ? (
          <ChevronDownIcon className="size-4" />
        ) : (
          <ChevronRightIcon className="size-4" />
        )}
      </button>
      {expanded && (
        <div className="max-h-[300px] overflow-y-auto">
          {history.map((entry, i) => (
            <button
              key={i}
              onClick={() => onSelect(entry.query)}
              className="flex items-start gap-3 w-full px-4 py-2.5 text-left border-t border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/30 transition-colors"
            >
              <span className="font-mono text-xs text-gray-800 dark:text-gray-200 whitespace-pre-wrap line-clamp-2 flex-1">
                {entry.query}
              </span>
              <span
                className={`text-[10px] font-medium px-1.5 py-0.5 rounded whitespace-nowrap ${
                  entry.result.error
                    ? "bg-red-50 dark:bg-red-900/30 text-red-600 dark:text-red-400"
                    : "bg-green-50 dark:bg-green-900/30 text-green-600 dark:text-green-400"
                }`}
              >
                {entry.result.error
                  ? "error"
                  : `${entry.result.result?.rows.length ?? 0} rows`}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export function UQAPlayground() {
  const { loading, ready, initialize, executeSQL } = useUQAEngine()
  const [query, setQuery] = useState(DEFAULT_QUERY)
  const [executing, setExecuting] = useState(false)
  const [lastResult, setLastResult] = useState<QueryResult | null>(null)
  const [history, setHistory] = useState<
    { query: string; result: QueryResult }[]
  >([])

  useEffect(() => {
    initialize()
  }, [initialize])

  const handleExecute = useCallback(async () => {
    if (!query.trim() || executing) return
    setExecuting(true)
    const result = await executeSQL(query.trim())
    setLastResult(result)
    setHistory((prev) => [{ query: query.trim(), result }, ...prev])
    setExecuting(false)
  }, [query, executing, executeSQL])

  const handleSelectExample = useCallback((exampleQuery: string) => {
    setQuery(exampleQuery)
    setLastResult(null)
  }, [])

  if (loading || !ready) {
    return (
      <div className="flex flex-col items-center justify-center h-[500px] gap-4">
        <div className="flex items-center gap-3">
          <div className="size-5 border-2 border-gray-300 dark:border-gray-600 border-t-gray-800 dark:border-t-gray-200 rounded-full animate-spin" />
          <span className="text-gray-500 dark:text-gray-400 text-sm">
            Initializing UQA Engine...
          </span>
        </div>
        <p className="text-xs text-gray-400 dark:text-gray-500">
          Loading WASM modules and sample data
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6 pb-16">
      {/* Main layout */}
      <div className="flex flex-col lg:flex-row gap-6">
        {/* Left sidebar */}
        <div className="flex flex-col gap-4 lg:w-[320px] lg:flex-shrink-0">
          <SchemaPanel />
          <ExampleQueryPanel onSelect={handleSelectExample} />
          <QueryHistory history={history} onSelect={handleSelectExample} />
        </div>

        {/* Main content */}
        <div className="flex flex-col gap-4 flex-1 min-w-0">
          <SQLEditor
            value={query}
            onChange={setQuery}
            onExecute={handleExecute}
            executing={executing}
          />
          {executing && (
            <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-gray-50 dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700">
              <div className="size-4 border-2 border-gray-300 dark:border-gray-600 border-t-gray-800 dark:border-t-gray-200 rounded-full animate-spin" />
              <span className="text-sm text-gray-500">Executing query...</span>
            </div>
          )}
          {lastResult && !executing && <ResultTable result={lastResult} />}

          {!lastResult && !executing && (
            <div className="flex flex-col items-center justify-center py-16 text-center border border-dashed border-gray-200 dark:border-gray-700 rounded-lg">
              <CommandLineIcon className="size-10 text-gray-300 dark:text-gray-600 mb-3" />
              <p className="text-sm text-gray-400 dark:text-gray-500 mb-1">
                Write a query above and press{" "}
                <kbd className="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 text-xs font-mono">
                  Ctrl+Enter
                </kbd>{" "}
                to execute
              </p>
              <p className="text-xs text-gray-300 dark:text-gray-600">
                or select an example query from the left panel
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Features footer */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-4">
        <div className="flex items-start gap-3 px-4 py-3 rounded-lg bg-gray-50 dark:bg-gray-800/30 border border-gray-100 dark:border-gray-800">
          <CircleStackIcon className="size-5 text-gray-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
              In-Memory Engine
            </p>
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
              Runs entirely in your browser via WebAssembly. No server required.
            </p>
          </div>
        </div>
        <div className="flex items-start gap-3 px-4 py-3 rounded-lg bg-gray-50 dark:bg-gray-800/30 border border-gray-100 dark:border-gray-800">
          <TableCellsIcon className="size-5 text-gray-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Full-Text Search
            </p>
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
              BM25 scoring with text_match(), @@ operator, and multi-field
              search.
            </p>
          </div>
        </div>
        <div className="flex items-start gap-3 px-4 py-3 rounded-lg bg-gray-50 dark:bg-gray-800/30 border border-gray-100 dark:border-gray-800">
          <CommandLineIcon className="size-5 text-gray-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
              PostgreSQL Compatible
            </p>
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
              Standard SQL with window functions, CTEs, subqueries, and more.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
