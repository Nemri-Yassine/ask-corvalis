import { useState } from 'react'
import ProjectCard from './ProjectCard'
import { rate, type AskResponse, type Source } from './api'
import { copyText } from './clipboard'
import { CheckIcon, CopyIcon } from './icons'

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

// Source chips: click one to read the exact policy text it comes from.
function SourceChips({ sources }: { sources: Source[] }) {
  const [open, setOpen] = useState<number | null>(null)
  return (
    <div className="sources">
      <span className="sources-label">Sources</span>
      <div className="chips">
        {sources.map((s, i) => (
          <button
            key={`${s.doc}-${s.section}`}
            type="button"
            className="chip chip-small"
            aria-expanded={open === i}
            onClick={() => setOpen(open === i ? null : i)}
          >
            {s.doc} › {s.section}
          </button>
        ))}
      </div>
      {open !== null && <blockquote className="snippet">{sources[open].snippet}</blockquote>}
    </div>
  )
}

export default function Answer({ result }: { result: AskResponse }) {
  const [rating, setRating] = useState<-1 | 0 | 1>(0)
  const [copied, setCopied] = useState(false)
  const hasProjects = result.projects.length > 0

  function vote(value: -1 | 1) {
    const next = rating === value ? 0 : value // clicking again removes the vote
    setRating(next)
    rate(result.question_id, next).catch(() => setRating(rating))
  }

  async function copyAnswer() {
    if (await copyText(result.answer)) {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <div className="msg assistant">
      <span className="avatar" aria-hidden="true">C</span>
      <div className={`card answer ${result.found ? '' : 'not-found'}`}>
        {result.found && result.mode === 'search' && !hasProjects && (
          <p className="answer-label">Here is the part of the policy that answers this:</p>
        )}

        <AnswerText text={result.answer} />

        {hasProjects && (
          <div className="project-cards">
            {result.projects.map((p) => (
              <ProjectCard key={p.number} project={p} />
            ))}
          </div>
        )}

        {result.sources.length > 0 && !hasProjects && <SourceChips sources={result.sources} />}

        <div className="answer-footer">
          <span className={`badge ${result.mode}`}>
            {result.mode === 'ai' ? 'AI answer' : 'Search result'}
          </span>
          <div className="answer-actions">
            <button
              type="button"
              className="icon-btn"
              aria-label={copied ? 'Answer copied' : 'Copy answer'}
              title="Copy answer"
              onClick={copyAnswer}
            >
              {copied ? <CheckIcon size={16} /> : <CopyIcon size={16} />}
            </button>
            <button
              type="button"
              className="icon-btn vote"
              aria-pressed={rating === 1}
              aria-label="Helpful"
              title="Helpful"
              onClick={() => vote(1)}
            >
              👍
            </button>
            <button
              type="button"
              className="icon-btn vote"
              aria-pressed={rating === -1}
              aria-label="Not helpful"
              title="Not helpful"
              onClick={() => vote(-1)}
            >
              👎
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
