import { useState, useEffect } from 'react'

const STATUS_STYLES = {
  submitted: 'bg-green-100 text-green-700',
  auto_approved: 'bg-blue-100 text-blue-700',
  approved: 'bg-teal-100 text-teal-700',
  skipped: 'bg-gray-100 text-gray-500',
}

function StatusBadge({ status }) {
  return (
    <span
      className={`text-xs px-2 py-0.5 rounded-full font-medium ${
        STATUS_STYLES[status] || 'bg-gray-100 text-gray-500'
      }`}
    >
      {status}
    </span>
  )
}

export default function Applications() {
  const [apps, setApps] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [sortBy, setSortBy] = useState('date')
  const [statusFilter, setStatusFilter] = useState('all')

  useEffect(() => {
    fetch('/api/applications')
      .then((r) => r.json())
      .then((data) => {
        setApps(data)
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [])

  const filtered = apps.filter((a) => {
    const matchesSearch =
      a.company_name?.toLowerCase().includes(search.toLowerCase()) ||
      a.job_title?.toLowerCase().includes(search.toLowerCase())
    const matchesStatus = statusFilter === 'all' || a.status === statusFilter
    return matchesSearch && matchesStatus
  })

  const sorted = [...filtered].sort((a, b) => {
    if (sortBy === 'score') return (b.match_score || 0) - (a.match_score || 0)
    if (sortBy === 'company') return (a.company_name || '').localeCompare(b.company_name || '')
    return (b.submitted_at || '').localeCompare(a.submitted_at || '')
  })

  // Status counts
  const statuses = [...new Set(apps.map((a) => a.status).filter(Boolean))]

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-gray-400 text-sm">Loading...</div>
      </div>
    )
  }

  return (
    <div className="p-8">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900">Applications</h2>
        <p className="text-gray-500 mt-1 text-sm">{apps.length} total applications on record</p>
      </div>

      {/* Controls */}
      <div className="flex gap-3 mb-5">
        <div className="flex-1 relative">
          <svg
            className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
          <input
            type="text"
            placeholder="Search by company or role..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full border border-gray-200 rounded-lg pl-9 pr-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400"
          />
        </div>

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400"
        >
          <option value="all">All Statuses</option>
          {statuses.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>

        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400"
        >
          <option value="date">Sort by Date</option>
          <option value="score">Sort by Score</option>
          <option value="company">Sort by Company</option>
        </select>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        {sorted.length === 0 ? (
          <div className="px-6 py-12 text-center text-gray-400 text-sm">
            {apps.length === 0 ? 'No applications yet.' : 'No results match your search.'}
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="text-left text-xs font-semibold text-gray-400 uppercase tracking-wider bg-gray-50 border-b border-gray-100">
                <th className="px-6 py-3">Company</th>
                <th className="px-6 py-3">Role</th>
                <th className="px-6 py-3 text-center">Score</th>
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3">Date</th>
                <th className="px-6 py-3">Link</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {sorted.map((app) => (
                <tr key={app.job_id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-6 py-3.5 font-semibold text-gray-900 text-sm">
                    {app.company_name}
                  </td>
                  <td className="px-6 py-3.5 text-sm text-gray-600 max-w-xs truncate">
                    {app.job_title}
                  </td>
                  <td className="px-6 py-3.5 text-center">
                    {app.match_score != null ? (
                      <span
                        className={`text-sm font-bold ${
                          app.match_score >= 80
                            ? 'text-green-600'
                            : app.match_score >= 60
                            ? 'text-yellow-600'
                            : 'text-red-500'
                        }`}
                      >
                        {app.match_score}
                      </span>
                    ) : (
                      <span className="text-gray-300">—</span>
                    )}
                  </td>
                  <td className="px-6 py-3.5">
                    <StatusBadge status={app.status} />
                  </td>
                  <td className="px-6 py-3.5 text-sm text-gray-400">
                    {app.submitted_at
                      ? new Date(app.submitted_at).toLocaleDateString('en-US', {
                          month: 'short',
                          day: 'numeric',
                          year: 'numeric',
                        })
                      : '—'}
                  </td>
                  <td className="px-6 py-3.5">
                    {app.job_url ? (
                      <a
                        href={app.job_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-blue-500 hover:text-blue-700 hover:underline"
                      >
                        View →
                      </a>
                    ) : (
                      <span className="text-gray-300 text-xs">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {sorted.length > 0 && (
        <p className="text-xs text-gray-400 mt-3">
          Showing {sorted.length} of {apps.length} application{apps.length !== 1 ? 's' : ''}
        </p>
      )}
    </div>
  )
}
