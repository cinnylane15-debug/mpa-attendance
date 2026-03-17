import { useState, useEffect, useCallback } from 'react';
import { apiGet } from '../api';

function StatCard({ title, value, color, icon }) {
  const colorClasses = {
    blue: 'bg-blue-50 text-blue-700 border-blue-200',
    green: 'bg-green-50 text-green-700 border-green-200',
    red: 'bg-red-50 text-red-700 border-red-200',
    yellow: 'bg-yellow-50 text-yellow-700 border-yellow-200',
  };

  return (
    <div className={`rounded-lg border p-5 ${colorClasses[color]}`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium opacity-75">{title}</p>
          <p className="text-3xl font-bold mt-1">{value}</p>
        </div>
        <div className="text-3xl opacity-30">{icon}</div>
      </div>
    </div>
  );
}

function formatTime(dateStr) {
  if (!dateStr) return '--';
  const d = new Date(dateStr);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function statusBadge(status) {
  const classes = {
    present: 'bg-green-100 text-green-800',
    late: 'bg-yellow-100 text-yellow-800',
    half_day: 'bg-orange-100 text-orange-800',
    absent: 'bg-red-100 text-red-800',
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${classes[status] || 'bg-gray-100 text-gray-800'}`}>
      {status}
    </span>
  );
}

function methodBadge(method) {
  const classes = {
    face_recognition: 'bg-indigo-100 text-indigo-800',
    rtsp_auto: 'bg-purple-100 text-purple-800',
    manual: 'bg-gray-100 text-gray-800',
  };
  const labels = {
    face_recognition: 'Face',
    rtsp_auto: 'RTSP Auto',
    manual: 'Manual',
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${classes[method] || 'bg-gray-100 text-gray-800'}`}>
      {labels[method] || method}
    </span>
  );
}

function Dashboard() {
  const [stats, setStats] = useState(null);
  const [cameras, setCameras] = useState([]);
  const [error, setError] = useState('');
  const [lastRefresh, setLastRefresh] = useState(new Date());

  const fetchStats = useCallback(async () => {
    try {
      const data = await apiGet('/dashboard/stats');
      setStats(data);
      setLastRefresh(new Date());
      setError('');
    } catch (err) {
      setError('Failed to load dashboard data');
    }
  }, []);

  const fetchCameras = useCallback(async () => {
    try {
      const data = await apiGet('/cameras/');
      setCameras(data);
    } catch {
      // Camera endpoint may not exist yet
      setCameras([]);
    }
  }, []);

  useEffect(() => {
    fetchStats();
    fetchCameras();
    const interval = setInterval(fetchStats, 10000);
    return () => clearInterval(interval);
  }, [fetchStats, fetchCameras]);

  if (error && !stats) {
    return (
      <div className="text-center py-12">
        <p className="text-red-500">{error}</p>
        <button onClick={fetchStats} className="mt-4 text-indigo-600 hover:underline">
          Retry
        </button>
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="text-center py-12 text-gray-500">Loading dashboard...</div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <span className="text-xs text-gray-400">
          Last updated: {lastRefresh.toLocaleTimeString()}
        </span>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard title="Total Employees" value={stats.total_employees} color="blue" icon="👥" />
        <StatCard title="Present Today" value={stats.today_present} color="green" icon="✓" />
        <StatCard title="Absent Today" value={stats.today_absent} color="red" icon="✗" />
        <StatCard title="Late Today" value={stats.today_late} color="yellow" icon="⏰" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent activity */}
        <div className="lg:col-span-2 bg-white rounded-lg shadow-sm border border-gray-200">
          <div className="px-5 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-800">Recent Activity</h2>
          </div>
          <div className="overflow-x-auto">
            {stats.recent_activity.length === 0 ? (
              <div className="p-8 text-center text-gray-400">No recent activity</div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500 bg-gray-50">
                    <th className="px-5 py-3 font-medium">Employee</th>
                    <th className="px-5 py-3 font-medium">Check In</th>
                    <th className="px-5 py-3 font-medium">Check Out</th>
                    <th className="px-5 py-3 font-medium">Status</th>
                    <th className="px-5 py-3 font-medium">Method</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {stats.recent_activity.map((record) => (
                    <tr key={record.id} className="hover:bg-gray-50">
                      <td className="px-5 py-3 font-medium text-gray-900">
                        {record.employee_name || `Employee #${record.employee_id}`}
                      </td>
                      <td className="px-5 py-3 text-gray-600">{formatTime(record.check_in)}</td>
                      <td className="px-5 py-3 text-gray-600">{formatTime(record.check_out)}</td>
                      <td className="px-5 py-3">{statusBadge(record.status)}</td>
                      <td className="px-5 py-3">{methodBadge(record.method)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Camera status */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200">
          <div className="px-5 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-800">Camera Status</h2>
          </div>
          <div className="p-5">
            {cameras.length === 0 ? (
              <div className="text-center text-gray-400 py-4">No cameras configured</div>
            ) : (
              <div className="space-y-3">
                {cameras.map((cam) => (
                  <div
                    key={cam.id}
                    className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                  >
                    <div>
                      <p className="font-medium text-gray-800 text-sm">{cam.name}</p>
                      <p className="text-xs text-gray-500">{cam.location || 'No location'}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span
                        className={`px-2 py-0.5 rounded text-xs font-medium ${
                          cam.direction === 'entry'
                            ? 'bg-blue-100 text-blue-700'
                            : 'bg-orange-100 text-orange-700'
                        }`}
                      >
                        {cam.direction}
                      </span>
                      <span
                        className={`w-2.5 h-2.5 rounded-full ${
                          cam.is_active ? 'bg-green-500' : 'bg-gray-400'
                        }`}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
