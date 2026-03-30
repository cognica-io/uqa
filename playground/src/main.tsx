import { StrictMode, lazy, Suspense } from "react"
import { createRoot } from "react-dom/client"
import "./index.css"

const App = lazy(() => import("./App"))

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Suspense
      fallback={
        <div className="flex items-center justify-center h-screen">
          <span className="text-gray-400 text-sm">Loading UQA Engine...</span>
        </div>
      }
    >
      <App />
    </Suspense>
  </StrictMode>,
)
