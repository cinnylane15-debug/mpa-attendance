import { useState, useEffect, useCallback } from 'react';
import { apiGet, apiPost, apiPut, apiDelete } from '../api';

function Cameras() {
  const [cameras, setCameras] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    location: '',
    rtsp_url: '',
    direction: 'entry',
  });
  const [formError, setFormError] = useState('');
  const [formLoading, setFormLoading] = useState(false);
  const [testingCamera, setTestingCamera] = useState(null);
  const [testResult, setTestResult] = useState(null);

  const fetchCameras = useCallback(async () => {
    try {
      setLoading(true);
      const data = await apiGet('/cameras/');
      setCameras(data);
      setError('');
    } catch (err) {
      setError('Failed to load cameras. The camera API may not be configured yet.');
      setCameras([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCameras();
    const interval = setInterval(fetchCameras, 15000);
    return () => clearInterval(interval);
  }, [fetchCameras]);

  const resetForm = () => {
    setFormData({ name: '', location: '', rtsp_url: '', direction: 'entry' });
    setShowForm(false);
    setFormError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError('');
    setFormLoading(true);
    try {
      await apiPost('/cameras/', {
        name: formData.name,
        location: formData.location || null,
        rtsp_url: formData.rtsp_url,
        direction: formData.direction,
      });
      resetForm();
      fetchCameras();
    } catch (err) {
      setFormError(err.message);
    } finally {
      setFormLoading(false);
    }
  };

  const handleDelete = async (cam) => {
    if (!confirm(`Are you sure you want to delete camera "${cam.name}"?`)) return;
    try {
      await apiDelete(`/cameras/${cam.id}`);
      fetchCameras();
    } catch (err) {
      alert(err.message);
    }
  };

  const handleToggleActive = async (cam) => {
    try {
      await apiPut(`/cameras/${cam.id}`, { is_active: !cam.is_active });
      fetchCameras();
    } catch (err) {
      alert(err.message);
    }
  };

  const handleTestConnection = async (cam) => {
    setTestingCamera(cam.id);
    setTestResult(null);
    try {
      const result = await apiPost(`/cameras/${cam.id}/test`, {});
      setTestResult({
        id: cam.id,
        success: result.connected !== false,
        message: result.message || (result.connected ? 'Connection successful' : result.error || 'Connection failed'),
      });
    } catch (err) {
      setTestResult({ id: cam.id, success: false, message: err.message || 'Connection failed' });
    } finally {
      setTestingCamera(null);
    }
  };

  const handleToggleProcessing = async (cam) => {
    try {
      if (cam.is_active) {
        await apiPost(`/cameras/${cam.id}/stop`, {});
      } else {
        await apiPost(`/cameras/${cam.id}/start`, {});
      }
      fetchCameras();
    } catch (err) {
      alert(err.message);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Cameras</h1>
        <button
          onClick={() => {
            resetForm();
            setShowForm(!showForm);
          }}
          className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors"
        >
          {showForm ? 'Cancel' : 'Add Camera'}
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-yellow-50 border border-yellow-200 rounded text-yellow-700 text-sm">
          {error}
        </div>
      )}

      {/* Add camera form */}
      {showForm && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Add New Camera</h2>
          {formError && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
              {formError}
            </div>
          )}
          <form onSubmit={handleSubmit} className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Camera Name</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none text-sm"
                placeholder="e.g. Main Entrance Camera"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Location</label>
              <input
                type="text"
                value={formData.location}
                onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none text-sm"
                placeholder="e.g. Building A, Floor 1"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">RTSP URL</label>
              <input
                type="text"
                value={formData.rtsp_url}
                onChange={(e) => setFormData({ ...formData, rtsp_url: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none text-sm font-mono"
                placeholder="rtsp://admin:pass@192.168.1.100:554/cam/realmonitor?channel=1&subtype=1"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Direction</label>
              <select
                value={formData.direction}
                onChange={(e) => setFormData({ ...formData, direction: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none text-sm"
              >
                <option value="entry">Entry (Check-in)</option>
                <option value="exit">Exit (Check-out)</option>
              </select>
            </div>
            <div className="md:col-span-2">
              <button
                type="submit"
                disabled={formLoading}
                className="px-6 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors disabled:opacity-50"
              >
                {formLoading ? 'Adding...' : 'Add Camera'}
              </button>
            </div>
          </form>
          <div className="mt-4 p-3 bg-gray-50 rounded-lg">
            <p className="text-xs font-semibold text-gray-600 mb-1">Dahua RTSP URL Format</p>
            <code className="text-xs text-gray-500">rtsp://username:password@camera-ip:554/cam/realmonitor?channel=1&subtype=1</code>
            <p className="text-xs text-gray-400 mt-1">Use subtype=1 for sub-stream (lower bandwidth), subtype=0 for main stream</p>
          </div>
        </div>
      )}

      {/* Camera cards */}
      {loading ? (
        <div className="text-center py-12 text-gray-400">Loading cameras...</div>
      ) : cameras.length === 0 && !error ? (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-12 text-center">
          <svg className="w-16 h-16 text-gray-300 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
          </svg>
          <p className="text-gray-500">No cameras configured yet</p>
          <p className="text-gray-400 text-sm mt-1">Add a camera to start monitoring attendance</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {cameras.map((cam) => (
            <div
              key={cam.id}
              className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden"
            >
              <div className="p-5">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className="font-semibold text-gray-900">{cam.name}</h3>
                    <p className="text-sm text-gray-500 mt-0.5">{cam.location || 'No location set'}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className={`px-2 py-0.5 rounded text-xs font-medium ${
                        cam.direction === 'entry'
                          ? 'bg-blue-100 text-blue-700'
                          : 'bg-orange-100 text-orange-700'
                      }`}
                    >
                      {cam.direction === 'entry' ? 'Entry' : 'Exit'}
                    </span>
                    <span
                      className={`w-3 h-3 rounded-full ${
                        cam.is_active ? 'bg-green-500' : 'bg-gray-400'
                      }`}
                      title={cam.is_active ? 'Active' : 'Inactive'}
                    />
                  </div>
                </div>

                <div className="bg-gray-50 rounded p-2 mb-4">
                  <p className="text-xs font-mono text-gray-500 break-all">{cam.rtsp_url}</p>
                </div>

                {testResult && testResult.id === cam.id && (
                  <div
                    className={`mb-3 p-2 rounded text-xs ${
                      testResult.success
                        ? 'bg-green-50 text-green-700 border border-green-200'
                        : 'bg-red-50 text-red-700 border border-red-200'
                    }`}
                  >
                    {testResult.message}
                  </div>
                )}

                <div className="flex items-center gap-2 flex-wrap">
                  <button
                    onClick={() => handleTestConnection(cam)}
                    disabled={testingCamera === cam.id}
                    className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded text-xs font-medium hover:bg-gray-200 transition-colors disabled:opacity-50"
                  >
                    {testingCamera === cam.id ? 'Testing...' : 'Test Connection'}
                  </button>
                  <button
                    onClick={() => handleToggleProcessing(cam)}
                    className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                      cam.is_active
                        ? 'bg-red-100 text-red-700 hover:bg-red-200'
                        : 'bg-green-100 text-green-700 hover:bg-green-200'
                    }`}
                  >
                    {cam.is_active ? 'Stop' : 'Start'}
                  </button>
                  <button
                    onClick={() => handleDelete(cam)}
                    className="px-3 py-1.5 bg-red-50 text-red-600 rounded text-xs font-medium hover:bg-red-100 transition-colors"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default Cameras;
