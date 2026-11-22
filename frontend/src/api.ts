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
}

// Optional filters for past projects ('' = no filter).
export type ProjectFilters = { projectType: string; yearFrom: string; yearTo: string }

export type FilterChoices = { types: string[]; min_year: number; max_year: number }

// An error whose message can be shown to the user as-is.
export class FriendlyError extends Error {}

async function post<T>(url: string, body: unknown): Promise<T> {
  const unreachable = new FriendlyError(
    "Can't reach the Ask Corvalis server. Please try again in a moment.",
  )
  let response: Response
  try {
    response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch {
    throw unreachable
  }

  const data = await response.json().catch(() => null)
  // No JSON at all means the reply didn't come from our API (e.g. the dev proxy
  // answering because the backend is stopped).
  if (data === null) throw unreachable
  if (!response.ok) {
    // Our own validation messages are plain text; anything else gets a generic message.
    const detail = data?.detail
    throw new FriendlyError(typeof detail === 'string' ? detail : 'Something went wrong, try again.')
  }
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
    throw new FriendlyError("Can't reach the Ask Corvalis server. Please try again in a moment.")
  }
  const data = await response.json().catch(() => null)
  if (!response.ok || data === null) {
    throw new FriendlyError("Can't load the statistics right now. Please try again in a moment.")
  }
  return data as Stats
}

export function ask(question: string, scope: Scope, filters?: ProjectFilters): Promise<AskResponse> {
  const body: Record<string, unknown> = { question, scope }
  if (scope === 'projects' && filters) {
    body.project_type = filters.projectType || null
    body.year_from = filters.yearFrom ? Number(filters.yearFrom) : null
    body.year_to = filters.yearTo ? Number(filters.yearTo) : null
  }
  return post('/api/ask', body)
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
