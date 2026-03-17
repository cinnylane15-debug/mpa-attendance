import { useState, useEffect } from 'react';
import { apiGet, apiPost, apiDelete } from '../api';

export default function Cameras() {
  const [cameras, setCameras] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: '', location: '', rtsp_url: '', direction: 'entry' });
  const [testing, setTesting] = useState(null);

  useEffect(() => { loadCameras(); }, []);

  async function loadCameras() {
    try {
      const data = await apiGet('/cameras/');
      setCameras(data);
    } catch (err) {
      console.error(err);
    }
    setLoading(false);
  }

  async function handleAdd(e) {
    e.preventDefault();
    try {
      await apiPost('/cameras/', form);
      setForm({ name: '', location: '', rtsp_url: '', direction: 'entry' });
      setShowForm(false);
      loadCameras();
    } catch (err) {
      alert(err.message);
    }
  }

  async function handleDelete(id) {
    if (!confirm('Delete this camera?')) return;
    try {
      await apiDelete(`/cameras/${id}`);
      loadCameras();
    } catch (err) {
      alert(err.message);
    }
  }

  async function handleTest(id) {
    setTesting(id);
    try {
      const result = await apiPost(`/cameras/${id}/test`);
      alert(result.connected ? 'Connection successful!' : `Connection failed: ${result.error || 'Unknown error'}`);
    } catch (err) {
      alert(`Test failed: ${err.message}`);
    }
    setTesting(null);
  }

  async function toggleActive(id, currentActive) {
    try {
      const endpoint = currentActive ? `/cameras/${id}/stop` : `/cameras/${id}/start`;
      await apiPost(endpoint);
      loadCameras();
    } catch (err) {
      alert(err.message);
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-800">Cameras</h1>
        <button
          onClick={() => setShowForm(!showForm)}
          className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700"
        >
          {showForm ? 'Cancel' : '+ Add Camera'}
        </button>
      </div>

      {showForm && (
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">Add Camera</h2>
          <form onSubmit={handleAdd} className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
              <input
                type="text" required value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="w-full border rounded px-3 py-2 text-sm"
                placeholder="Main Entrance Camera"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Location</label>
              <input
                type="text" required value={form.location}
                onChange={(e) => setForm({ ...form, location: e.target.value })}
                className="w-full border rounded px-3 py-2 text-sm"
                placeholder="Building A - Front Gate"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">RTSP URL</label>
              <input
                type="text" required value={form.rtsp_url}
                onChange={(e) => setForm({ ...form, rtsp_url: e.target.value })}
                className="w-full border rounded px-3 py-2 text-sm font-mono"
                placeholder="rtsp://admin:password@192.168.1.100:554/cam/realmonitor?channel=1&subtype=1"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Direction</label>
              <select
                value={form.direction}
                onChange={(e) => setForm({ ...form, direction: e.target.value })}
                className="w-full border rounded px-3 py-2 text-sm"
              >
                <option value="entry">Entry (Check-in)</option>
                <option value="exit">Exit (Check-out)</option>
              </select>
            </div>
            <div className="md:col-span-2">
              <button type="submit" className="bg-indigo-600 text-white px-6 py-2 rounded text-sm font-medium hover:bg-indigo-700">
                Add Camera
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Location</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Direction</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {loading ? (
              <tr><td colSpan="5" className="px-6 py-8 text-center text-gray-500">Loading...</td></tr>
            ) : cameras.length === 0 ? (
              <tr><td colSpan="5" className="px-6 py-8 text-center text-gray-500">No cameras configured</td></tr>
            ) : cameras.map((cam) => (
              <tr key={cam.id} className="hover:bg-gray-50">
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{cam.name}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{cam.location}</td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className={`px-2 py-0.5 text-xs rounded-full ${cam.direction === 'entry' ? 'bg-green-100 text-green-700' : 'bg-orange-100 text-orange-700'}`}>
                    {cam.direction === 'entry' ? 'Entry' : 'Exit'}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className={`px-2 py-0.5 text-xs rounded-full ${cam.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                    {cam.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm space-x-2">
                  <button
                    onClick={() => toggleActive(cam.id, cam.is_active)}
                    className={`px-3 py-1 rounded text-xs font-medium ${cam.is_active ? 'bg-red-100 text-red-700 hover:bg-red-200' : 'bg-green-100 text-green-700 hover:bg-green-200'}`}
                  >
                    {cam.is_active ? 'Stop' : 'Start'}
                  </button>
                  <button
                    onClick={() => handleTest(cam.id)}
                    disabled={testing === cam.id}
                    className="px-3 py-1 rounded text-xs font-medium bg-blue-100 text-blue-700 hover:bg-blue-200 disabled:opacity-50"
                  >
                    {testing === cam.id ? 'Testing...' : 'Test'}
                  </button>
                  <button
                    onClick={() => handleDelete(cam.id)}
                    className="px-3 py-1 rounded text-xs font-medium bg-red-100 text-red-700 hover:bg-red-200"
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-4 p-4 bg-gray-50 rounded-lg">
        <h3 className="text-sm font-semibold text-gray-600 mb-2">Dahua RTSP URL Format</h3>
        <code className="text-xs text-gray-500">rtsp://username:password@camera-ip:554/cam/realmonitor?channel=1&subtype=1</code>
        <p className="text-xs text-gray-400 mt-1">Use subtype=1 for sub-stream (lower bandwidth), subtype=0 for main stream</p>
      </div>
    </div>
  );
}
