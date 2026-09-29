// Server-only access to the health API. Imported only by server functions, so
// the browser never talks to FastAPI directly.
import createClient from "openapi-fetch"
import type { paths } from "@/lib/api/schema.gen"
import type { Issue } from "@/lib/api/types"

export const api = createClient<paths>({
  baseUrl: process.env.HEALTH_API_URL ?? "http://127.0.0.1:8000",
})

/** Turn any API error body into field issues the UI can show. */
export function toIssues(error: unknown): Array<Issue> {
  const detail = (error as { detail?: unknown } | undefined)?.detail
  if (Array.isArray(detail)) {
    return detail.map((item: Record<string, unknown>) => {
      // Our own issues are {field, message}; FastAPI's are {loc, msg}.
      if (typeof item.field === "string") {
        return { field: item.field, message: String(item.message) }
      }
      const loc = Array.isArray(item.loc) ? item.loc.slice(1).join(".") : ""
      return { field: loc, message: String(item.msg) }
    })
  }
  if (typeof detail === "string") return [{ field: "", message: detail }]
  return [{ field: "", message: "The health API could not be reached" }]
}

/** Unwrap an openapi-fetch result or throw with a readable message. */
export function unwrap<T>(result: { data?: T; error?: unknown }): T {
  if (result.data !== undefined) return result.data
  throw new Error(
    toIssues(result.error)
      .map((issue) => issue.message)
      .join("; ")
  )
}
