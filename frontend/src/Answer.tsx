import { useState } from 'react'
import { rate, type AskResponse } from './api'

// Splits "text [leave.md › Annual leave] more" so citations can be shown as small tags.
const CITATION = /(\[[^[\]]+ › [^[\]]+\])/
const IS_CITATION = /^\[[^[\]]+ › [^[\]]+\]$/

function AnswerText({ text }: { text: string }) {
  return (
    <p className="answer-text">
      {text.split(CITATION).map((part, i) =>
        IS_CITATION.test(part) ? (
          <span key={i} className="citation">
            {part.slice(1, -1)}
          </span>
        ) : (
          part
        ),
      )}
    </p>
  )
}

export default function Answer({ result }: { result: AskResponse }) {
  const [rating, setRating] = useState<-1 | 0 | 1>(0)
  const best = result.sources[0]

  function vote(value: -1 | 1) {
    const next = rating === value ? 0 : value // clicking again removes the vote
    setRating(next)
    rate(result.question_id, next).catch(() => setRating(rating))
  }

  return (
    <div className={`answer ${result.found ? '' : 'not-found'}`}>
      {result.found && (
        <span className={`badge ${result.mode}`}>
          {result.mode === 'ai' ? 'AI answer' : 'Search result (AI offline)'}
        </span>
      )}

      {result.found && result.mode === 'search' && best && (
        <p className="section-label">
          Relevant policy section: <strong>{best.doc} › {best.section}</strong>
        </p>
      )}

      <AnswerText text={result.answer} />

      {result.sources.length > 0 && (
        <details className="sources">
          <summary>Sources ({result.sources.length})</summary>
          <ul>
            {result.sources.map((s) => (
              <li key={`${s.doc}-${s.section}`}>
                <strong>
                  {s.doc} › {s.section}
                </strong>
                <p>{s.snippet}</p>
              </li>
            ))}
          </ul>
        </details>
      )}

      <div className="feedback">
        <span>Was this helpful?</span>
        <button
          type="button"
          className={rating === 1 ? 'selected' : ''}
          aria-pressed={rating === 1}
          aria-label="Helpful"
          onClick={() => vote(1)}
        >
          👍
        </button>
        <button
          type="button"
          className={rating === -1 ? 'selected' : ''}
          aria-pressed={rating === -1}
          aria-label="Not helpful"
          onClick={() => vote(-1)}
        >
          👎
        </button>
      </div>
    </div>
  )
}
