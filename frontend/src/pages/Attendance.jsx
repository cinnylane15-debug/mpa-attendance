import { useState, useEffect, useCallback } from 'react';
import { apiGet } from '../api';

function formatTime(dateStr) {
  if (!dateStr) return '--';
  const d = new Date(dateStr);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function formatDate(dateStr) {
  if (!dateStr) return '--';
  return new Date(dateStr).toLocaleDateString();
}

function Attendance() {
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [viewMode, setViewMode] = useState('today'); // 'today' or 'history'
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [filterEmployeeId, setFilterEmployeeId] = useState('');

  const fetchToday = useCallback(async () => {
    try {
      setLoading(true);
      const data = await apiGet('/attendance/today');
      setRecords(data);
      setError('');
    } catch (err) {
      setError('Failed to load attendance records');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchHistory = useCallback(async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (startDate) params.set('start_date', startDate);
      if (endDate) params.set('end_date', endDate);
      if (filterEmployeeId) params.set('employee_id', filterEmployeeId);
      params.set('limit', '100');
      const query = params.toString();
      const data = await apiGet(`/attendance/records?${query}`);
      setRecords(data);
      setError('');
    } catch (err) {
      setError('Failed to load attendance records');
    } finally {
      setLoading(false);
    }
  }, [startDate, endDate, filterEmployeeId]);

  useEffect(() => {
    if (viewMode === 'today') {
      fetchToday();
    } else {
      fetchHistory();
    }
  }, [viewMode, fetchToday, fetchHistory]);

  const handleExportCSV = () => {
    if (records.length === 0) return;
    const headers = ['Employee', 'Date', 'Check In', 'Check Out', 'Status', 'Method', 'Confidence'];
    const rows = records.map((r) => [
      r.employee_name || `Employee #${r.employee_id}`,
      r.date,
      r.check_in ? new Date(r.check_in).toLocaleString() : '',
      r.check_out ? new Date(r.check_out).toLocaleString() : '',
      r.status,
      r.method,
      r.confidence != null ? r.confidence.toFixed(4) : '',
    ]);
    const csv = [headers, ...rows].map((row) => row.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `attendance_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const statusBadge = (status) => {
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
  };

  const methodBadge = (method) => {
    const classes = {
      face_recognition: 'bg-indigo-100 text-indigo-800',
      rtsp_auto: 'bg-purple-100 text-purple-800',
      manual: 'bg-gray-100 text-gray-800',
    };
    const labels = {
      face_recognition: 'Face Recognition',
      rtsp_auto: 'RTSP Auto',
      manual: 'Manual',
    };
    return (
      <span className={`px-2 py-0.5 rounded text-xs font-medium ${classes[method] || 'bg-gray-100 text-gray-800'}`}>
        {labels[method] || method}
      </span>
    );
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Attendance</h1>
        <div className="flex items-center gap-2">
          <button
            onClick={handleExportCSV}
            disabled={records.length === 0}
            className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-200 transition-colors disabled:opacity-50"
          >
            Export CSV
          </button>
        </div>
      </div>

      {/* View mode toggle */}
      <div className="flex items-center gap-4 mb-4">
        <div className="inline-flex bg-gray-100 rounded-lg p-1">
          <button
            onClick={() => setViewMode('today')}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
              viewMode === 'today'
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            Today
          </button>
          <button
            onClick={() => setViewMode('history')}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
              viewMode === 'history'
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            History
          </button>
        </div>
      </div>

      {/* Filters for history mode */}
      {viewMode === 'history' && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Start Date</label>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">End Date</label>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Employee ID</label>
              <input
                type="text"
                value={filterEmployeeId}
                onChange={(e) => setFilterEmployeeId(e.target.value)}
                placeholder="e.g. EMP001"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
              />
            </div>
            <div>
              <button
                onClick={fetchHistory}
                className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors"
              >
                Search
              </button>
            </div>
          </div>
        </div>
      )}

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* Attendance table */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
        <div className="overflow-x-auto">
          {loading ? (
            <div className="p-8 text-center text-gray-400">Loading...</div>
          ) : records.length === 0 ? (
            <div className="p-8 text-center text-gray-400">No attendance records found</div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-500 bg-gray-50 border-b border-gray-200">
                  <th className="px-5 py-3 font-medium">Employee</th>
                  <th className="px-5 py-3 font-medium">Date</th>
                  <th className="px-5 py-3 font-medium">Check In</th>
                  <th className="px-5 py-3 font-medium">Check Out</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Method</th>
                  <th className="px-5 py-3 font-medium">Confidence</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {records.map((record) => (
                  <tr key={record.id} className="hover:bg-gray-50">
                    <td className="px-5 py-3 font-medium text-gray-900">
                      {record.employee_name || `Employee #${record.employee_id}`}
                    </td>
                    <td className="px-5 py-3 text-gray-600">{formatDate(record.date)}</td>
                    <td className="px-5 py-3 text-gray-600">{formatTime(record.check_in)}</td>
                    <td className="px-5 py-3 text-gray-600">{formatTime(record.check_out)}</td>
                    <td className="px-5 py-3">{statusBadge(record.status)}</td>
                    <td className="px-5 py-3">{methodBadge(record.method)}</td>
                    <td className="px-5 py-3 text-gray-600">
                      {record.confidence != null
                        ? `${(record.confidence * 100).toFixed(1)}%`
                        : '--'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

export default Attendance;
