import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

function StatCard({ label, value, color, sub }) {
  return (
    <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100">
      <p className="text-sm text-gray-500 font-medium">{label}</p>
      <p className={`text-3xl font-bold mt-1 ${color}`}>{value ?? 0}</p>
      {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
    </div>
  )
}

const STATUS_STYLES = {
  submitted: 'bg-green-100 text-green-700',
  auto_approved: 'bg-blue-100 text-blue-700',
  approved: 'bg-teal-100 text-teal-700',
  skipped: 'bg-gray-100 text-gray-500',
}

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [recent, setRecent] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      fetch('/api/stats').then((r) => r.json()),
      fetch('/api/applications/recent').then((r) => r.json()),
    ])
      .then(([s, r]) => {
        setStats(s)
        setRecent(r)
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-gray-400 text-sm">Loading...</div>
      </div>
    )
  }

  return (
    <div className="p-8 max-w-6xl">
      <div className="mb-7">
        <h2 className="text-2xl font-bold text-gray-900">Dashboard</h2>
        <p className="text-gray-500 mt-1 text-sm">
          Overview of your YC job application activity
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4 mb-7">
        <StatCard label="Total Applications" value={stats?.total_applications} color="text-blue-600" />
        <StatCard label="Submitted" value={stats?.submitted} color="text-green-600" />
        <StatCard
          label="Pending Review"
          value={stats?.pending_review}
          color="text-yellow-600"
          sub="Awaiting your review"
        />
        <StatCard label="This Week" value={stats?.this_week} color="text-purple-600" />
      </div>

      {/* Quick Actions */}
      <div className="flex gap-3 mb-7">
        <Link
          to="/pipeline"
          className="bg-orange-500 hover:bg-orange-600 text-white px-5 py-2.5 rounded-lg font-medium text-sm transition-colors"
        >
          Run Pipeline
        </Link>
        <Link
          to="/review"
          className="bg-white hover:bg-gray-50 text-gray-700 border border-gray-200 px-5 py-2.5 rounded-lg font-medium text-sm transition-colors flex items-center gap-2"
        >
          Review Drafts
          {stats?.pending_review > 0 && (
            <span className="bg-yellow-100 text-yellow-700 text-xs px-1.5 py-0.5 rounded-full font-semibold">
              {stats.pending_review}
            </span>
          )}
        </Link>
        <Link
          to="/applications"
          className="bg-white hover:bg-gray-50 text-gray-700 border border-gray-200 px-5 py-2.5 rounded-lg font-medium text-sm transition-colors"
        >
          All Applications
        </Link>
      </div>

      {/* Recent Applications */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h3 className="font-semibold text-gray-900">Recent Applications</h3>
          <Link to="/applications" className="text-xs text-orange-500 hover:underline">
            View all →
          </Link>
        </div>

        {recent.length === 0 ? (
          <div className="px-6 py-12 text-center">
            <p className="text-gray-400 text-sm">No applications yet.</p>
            <p className="text-gray-400 text-sm mt-1">
              <Link to="/pipeline" className="text-orange-500 hover:underline">
                Run the pipeline
              </Link>{' '}
              to get started.
            </p>
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="text-left text-xs font-medium text-gray-400 uppercase tracking-wider border-b border-gray-100">
                <th className="px-6 py-3">Company</th>
                <th className="px-6 py-3">Role</th>
                <th className="px-6 py-3">Score</th>
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {recent.map((app) => (
                <tr key={app.job_id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-6 py-3.5 font-medium text-gray-900 text-sm">
                    {app.company_name}
                  </td>
                  <td className="px-6 py-3.5 text-sm text-gray-600">{app.job_title}</td>
                  <td className="px-6 py-3.5">
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
                  </td>
                  <td className="px-6 py-3.5">
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                        STATUS_STYLES[app.status] || 'bg-gray-100 text-gray-500'
                      }`}
                    >
                      {app.status}
                    </span>
                  </td>
                  <td className="px-6 py-3.5 text-sm text-gray-400">
                    {app.submitted_at
                      ? new Date(app.submitted_at).toLocaleDateString()
                      : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
