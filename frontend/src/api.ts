// Small wrapper around the backend API. All calls go to /api (proxied to FastAPI in dev).

export type Scope = 'rules' | 'projects'

export type Source = { doc: string; section: string; snippet: string }

export type Project = {
  number: string
  title: string
  type: string
  discipline: string
  client: string
  city: string
  year: number
  project_manager: string
  materials: string
  budget_eur: number
  summary: string
  folder_path: string
}

export type AskResponse = {
  question_id: number
  answer: string
  sources: Source[]
  projects: Project[] // only filled for past-project questions
  mode: 'ai' | 'search'
  found: boolean
  model: string | null // the local model that wrote it (null in search mode)
  ai_available: boolean
  latency_ms: number
}

// Sent first by the streaming endpoint: what was found, and whether the AI will write.
export type SearchStep = {
  sources: Source[]
  projects: Project[]
  found: boolean
  ai: boolean
  model: string
}

export type Health = { ollama: boolean; model: string }

// Optional filters for past projects ('' = no filter).
export type ProjectFilters = { projectType: string; yearFrom: string; yearTo: string }

export type FilterChoices = { types: string[]; min_year: number; max_year: number }

// An error whose message can be shown to the user as-is.
export class FriendlyError extends Error {}

const unreachable = () =>
  new FriendlyError("Ask Corvalis isn't responding right now. Please try again in a moment.")

async function send(url: string, body: unknown, signal?: AbortSignal): Promise<Response> {
  try {
    return await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    })
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e // the user pressed Stop
    throw unreachable()
  }
}

// Turn an error response into a message the user can read.
async function errorFrom(response: Response): Promise<FriendlyError> {
  const data = await response.json().catch(() => null)
  // No JSON at all means the reply didn't come from our API (e.g. the dev proxy
  // answering because the backend is stopped).
  if (data === null) return unreachable()
  // Our own validation messages are plain text; anything else gets a generic message.
  const detail = data?.detail
  return new FriendlyError(typeof detail === 'string' ? detail : 'Something went wrong, try again.')
}

async function post<T>(url: string, body: unknown): Promise<T> {
  const response = await send(url, body)
  if (!response.ok) throw await errorFrom(response)
  const data = await response.json().catch(() => null)
  if (data === null) throw unreachable()
  return data as T
}

export type Stats = {
  total: number
  answered_pct: number
  unanswered_count: number
  top_questions: { text: string; count: number; found: number }[]
  unanswered: { text: string; count: number; last_asked: string }[]
  thumbs_down: { id: number; text: string; answer: string; created_at: string }[]
}

export async function getStats(): Promise<Stats> {
  let response: Response
  try {
    response = await fetch('/api/stats')
  } catch {
    throw new FriendlyError("Ask Corvalis isn't responding right now. Please try again in a moment.")
  }
  const data = await response.json().catch(() => null)
  if (!response.ok || data === null) {
    throw new FriendlyError("The figures can't be loaded right now. Please try again in a moment.")
  }
  return data as Stats
}

function askBody(question: string, scope: Scope, filters?: ProjectFilters) {
  const body: Record<string, unknown> = { question, scope }
  if (scope === 'projects' && filters) {
    body.project_type = filters.projectType || null
    body.year_from = filters.yearFrom ? Number(filters.yearFrom) : null
    body.year_to = filters.yearTo ? Number(filters.yearTo) : null
  }
  return body
}

export function ask(question: string, scope: Scope, filters?: ProjectFilters): Promise<AskResponse> {
  return post('/api/ask', askBody(question, scope, filters))
}

type StreamHandlers = {
  onSearch: (step: SearchStep) => void // step 1 done: what was found
  onToken: (text: string) => void // step 2: one more piece of the AI's answer
}

// Ask with live progress. The server sends Server-Sent Events:
//   "event: sources\ndata: {...}\n\n", then "token" events, then "done".
// (EventSource can't POST a body, so we read the fetch stream ourselves.)
export async function askStream(
  question: string,
  scope: Scope,
  filters: ProjectFilters,
  handlers: StreamHandlers,
  signal: AbortSignal,
): Promise<AskResponse> {
  const response = await send('/api/ask/stream', askBody(question, scope, filters), signal)
  if (!response.ok || !response.body) throw await errorFrom(response)

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    let chunk
    try {
      chunk = await reader.read()
    } catch (e) {
      if ((e as Error).name === 'AbortError') throw e
      throw unreachable() // connection lost halfway
    }
    if (chunk.done) break
    buffer += chunk.value

    // Events are separated by a blank line; keep any unfinished one in the buffer.
    const blocks = buffer.split('\n\n')
    buffer = blocks.pop() ?? ''
    for (const block of blocks) {
      const event = block.match(/^event: (.*)$/m)?.[1]
      const data = JSON.parse(block.match(/^data: (.*)$/m)?.[1] ?? 'null')
      if (event === 'sources') handlers.onSearch(data)
      else if (event === 'token') handlers.onToken(data.text)
      else if (event === 'done') return data as AskResponse
      else if (event === 'error') throw new FriendlyError(data.detail)
    }
  }
  throw unreachable() // stream ended without a "done" event
}

export async function getHealth(): Promise<Health | null> {
  try {
    const response = await fetch('/api/health')
    return response.ok ? await response.json() : null
  } catch {
    return null
  }
}

export async function getFilterChoices(): Promise<FilterChoices | null> {
  // Filters are optional: if this fails, the UI simply hides them.
  try {
    const response = await fetch('/api/projects/filters')
    return response.ok ? await response.json() : null
  } catch {
    return null
  }
}

export function rate(questionId: number, rating: -1 | 0 | 1): Promise<{ ok: boolean }> {
  return post(`/api/questions/${questionId}/rating`, { rating })
}
