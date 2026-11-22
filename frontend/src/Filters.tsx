import type { FilterChoices, ProjectFilters } from './api'

type Props = {
  choices: FilterChoices
  filters: ProjectFilters
  onChange: (filters: ProjectFilters) => void
}

// Optional narrowing of past-project search: building type and year range.
export default function Filters({ choices, filters, onChange }: Props) {
  const years: number[] = []
  for (let y = choices.max_year; y >= choices.min_year; y--) years.push(y)

  const set = (key: keyof ProjectFilters) => (e: React.ChangeEvent<HTMLSelectElement>) =>
    onChange({ ...filters, [key]: e.target.value })

  const active = filters.projectType || filters.yearFrom || filters.yearTo

  return (
    <div className="filters">
      <label>
        Type
        <select value={filters.projectType} onChange={set('projectType')}>
          <option value="">All types</option>
          {choices.types.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </label>
      <label>
        From
        <select value={filters.yearFrom} onChange={set('yearFrom')}>
          <option value="">Any year</option>
          {years.map((y) => (
            <option key={y}>{y}</option>
          ))}
        </select>
      </label>
      <label>
        To
        <select value={filters.yearTo} onChange={set('yearTo')}>
          <option value="">Any year</option>
          {years.map((y) => (
            <option key={y}>{y}</option>
          ))}
        </select>
      </label>
      {active && (
        <button
          type="button"
          className="clear-filters"
          onClick={() => onChange({ projectType: '', yearFrom: '', yearTo: '' })}
        >
          Clear
        </button>
      )}
    </div>
  )
}
