import { useRef, useState } from 'react'
import type { Project } from './api'

// Copy to the clipboard. Some browsers/company setups block the modern API,
// so fall back to selecting the text and the older copy command.
async function copyText(text: string, element: HTMLElement | null): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    if (!element) return false
    const range = document.createRange()
    range.selectNodeContents(element)
    const selection = window.getSelection()
    selection?.removeAllRanges()
    selection?.addRange(range)
    try {
      return document.execCommand('copy') // deprecated, but still the only fallback
    } catch {
      return false
    }
  }
}

const euros = new Intl.NumberFormat('en-BE', {
  style: 'currency',
  currency: 'EUR',
  notation: 'compact',
  maximumFractionDigits: 1,
})

export default function ProjectCard({ project: p }: { project: Project }) {
  const [copyLabel, setCopyLabel] = useState('Copy path')
  const pathRef = useRef<HTMLElement>(null)

  async function copyPath() {
    if (await copyText(p.folder_path, pathRef.current)) {
      setCopyLabel('Copied ✓')
    } else {
      setCopyLabel('Press Ctrl+C') // path is selected, user copies it
    }
    setTimeout(() => setCopyLabel('Copy path'), 2500)
  }

  return (
    <article className="project-card">
      <header>
        <span className="project-number">{p.number}</span>
        <h3>{p.title}</h3>
      </header>

      <dl className="project-facts">
        <div>
          <dt>Year</dt>
          <dd>{p.year}</dd>
        </div>
        <div>
          <dt>City</dt>
          <dd>{p.city}</dd>
        </div>
        <div>
          <dt>Project manager</dt>
          <dd>{p.project_manager}</dd>
        </div>
        <div>
          <dt>Materials</dt>
          <dd>{p.materials}</dd>
        </div>
      </dl>

      <p className="project-meta">
        {p.type} · {p.discipline} · {p.client} · {euros.format(p.budget_eur)}
      </p>

      <p className="project-summary">{p.summary}</p>

      <div className="folder">
        <code ref={pathRef}>{p.folder_path}</code>
        <button type="button" onClick={copyPath} aria-label={`Copy folder path for ${p.number}`}>
          {copyLabel}
        </button>
      </div>
    </article>
  )
}
