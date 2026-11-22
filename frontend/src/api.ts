// Small wrapper around the backend API. All calls go to /api (proxied to FastAPI in dev).

export type Scope = 'rules' | 'projects'

export type Source = { doc: string; section: string; snippet: string }

export type AskResponse = {
  question_id: number
  answer: string
  sources: Source[]
  mode: 'ai' | 'search'
  found: boolean
}

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

export function ask(question: string, scope: Scope): Promise<AskResponse> {
  return post('/api/ask', { question, scope })
}

export function rate(questionId: number, rating: -1 | 0 | 1): Promise<{ ok: boolean }> {
  return post(`/api/questions/${questionId}/rating`, { rating })
}
