import { useEffect, useRef, useState, type FormEvent } from 'react'
import Answer from './Answer'
import Filters from './Filters'
import {
  ask,
  FriendlyError,
  getFilterChoices,
  type AskResponse,
  type FilterChoices,
  type ProjectFilters,
  type Scope,
} from './api'

// One line of the conversation: the question, then either a result, an error, or "loading".
type Turn = {
  id: number
  question: string
  result?: AskResponse
  error?: string
}

// Each tab is its own conversation, with its own intro and examples.
const TABS: Record<Scope, { intro: string; placeholder: string; examples: string[] }> = {
  rules: {
    intro: 'Ask about leave, expenses, IT, purchasing or your first days at Corvalis.',
    placeholder: 'Type your question…',
    examples: [
      'How many days of annual leave do I get?',
      "What's the mileage rate?",
      'I lost my laptop, what do I do?',
      'Do I need a quote for a €3,000 purchase?',
    ],
  },
  projects: {
    intro: 'Find similar past Corvalis projects: by building type, material, city or technique.',
    placeholder: 'Describe the project you are looking for…',
    examples: [
      'Have we designed a timber footbridge before?',
      'Hospital extension in Liège',
      'CLT office building',
      'Post-tensioned car park',
    ],
  },
}

const MAX_LENGTH = 500

// "Looking it up…", then a reassurance if the AI is slow (it can take up to 30 s).
function Loading() {
  const [slow, setSlow] = useState(false)
  useEffect(() => {
    const timer = setTimeout(() => setSlow(true), 8000)
    return () => clearTimeout(timer)
  }, [])
  return (
    <div className="answer loading" aria-live="polite">
      {slow ? 'Still working, the AI is a bit slow right now' : 'Looking it up'}
      <span className="dots" />
    </div>
  )
}
const NO_FILTERS: ProjectFilters = { projectType: '', yearFrom: '', yearTo: '' }

export default function Chat() {
  const [scope, setScope] = useState<Scope>('rules')
  const [turns, setTurns] = useState<Record<Scope, Turn[]>>({ rules: [], projects: [] })
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [filters, setFilters] = useState<ProjectFilters>(NO_FILTERS)
  const [choices, setChoices] = useState<FilterChoices | null>(null)
  const lastTurnRef = useRef<HTMLLIElement>(null)

  const tab = TABS[scope]
  const current = turns[scope]

  // Show the newest question at the top, so a long answer is read from its start.
  useEffect(() => {
    lastTurnRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [current])

  // Load the filter options (types, years) once.
  useEffect(() => {
    getFilterChoices().then(setChoices)
  }, [])

  function updateTurn(id: number, change: Partial<Turn> | Turn) {
    setTurns((all) => ({
      ...all,
      [scope]: all[scope].map((turn) => (turn.id === id ? { ...turn, ...change } : turn)),
    }))
  }

  // Ask a new question, or (with retryId) ask a failed one again in place.
  async function send(question: string, retryId?: number) {
    question = question.trim()
    if (!question || loading) return

    const id = retryId ?? Date.now()
    if (retryId) {
      updateTurn(id, { error: undefined, result: undefined })
    } else {
      setTurns((all) => ({ ...all, [scope]: [...all[scope], { id, question }] }))
      setInput('')
    }
    setLoading(true)

    try {
      const result = await ask(question, scope, filters)
      updateTurn(id, { result })
    } catch (e) {
      const error = e instanceof FriendlyError ? e.message : 'Something went wrong, try again.'
      updateTurn(id, { error })
    } finally {
      setLoading(false)
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault() // the form also handles the Enter key
    send(input)
  }

  return (
    <>
      <main className="chat">
        <div className="scope-toggle" role="group" aria-label="What do you want to search?">
          <button
            type="button"
            className={scope === 'rules' ? 'active' : ''}
            aria-pressed={scope === 'rules'}
            disabled={loading}
            onClick={() => setScope('rules')}
          >
            Company rules
          </button>
          <button
            type="button"
            className={scope === 'projects' ? 'active' : ''}
            aria-pressed={scope === 'projects'}
            disabled={loading}
            onClick={() => setScope('projects')}
          >
            Past projects
          </button>
        </div>

        {scope === 'projects' && choices && (
          <Filters choices={choices} filters={filters} onChange={setFilters} />
        )}

        {current.length === 0 && (
          <section className="empty">
            <h1>What would you like to know?</h1>
            <p>{tab.intro}</p>
            <div className="examples">
              {tab.examples.map((q) => (
                <button key={q} type="button" onClick={() => send(q)}>
                  {q}
                </button>
              ))}
            </div>
          </section>
        )}

        <ol className="turns">
          {current.map((turn, i) => (
            <li key={turn.id} ref={i === current.length - 1 ? lastTurnRef : undefined}>
              <p className="question">{turn.question}</p>
              {turn.result && <Answer result={turn.result} />}
              {turn.error && (
                <div className="answer error" role="alert">
                  {turn.error}
                  <button type="button" onClick={() => send(turn.question, turn.id)}>
                    Try again
                  </button>
                </div>
              )}
              {!turn.result && !turn.error && <Loading />}
            </li>
          ))}
        </ol>
      </main>

      <form className="composer" onSubmit={onSubmit}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={tab.placeholder}
          aria-label="Your question"
          maxLength={MAX_LENGTH}
          autoFocus
        />
        <button type="submit" disabled={loading || !input.trim()}>
          Ask
        </button>
      </form>
    </>
  )
}
