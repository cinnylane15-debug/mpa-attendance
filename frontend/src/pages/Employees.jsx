import { useState, useEffect, useCallback } from 'react';
import { apiGet, apiPost, apiPut, apiDelete, apiPostFile } from '../api';

function Employees() {
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [editingEmployee, setEditingEmployee] = useState(null);
  const [formData, setFormData] = useState({ employee_id: '', name: '', department: '' });
  const [formError, setFormError] = useState('');
  const [formLoading, setFormLoading] = useState(false);
  const [uploadingFor, setUploadingFor] = useState(null);
  const [uploadError, setUploadError] = useState('');

  const fetchEmployees = useCallback(async () => {
    try {
      setLoading(true);
      const data = await apiGet('/employees/');
      setEmployees(data);
      setError('');
    } catch (err) {
      setError('Failed to load employees');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchEmployees();
  }, [fetchEmployees]);

  const resetForm = () => {
    setFormData({ employee_id: '', name: '', department: '' });
    setEditingEmployee(null);
    setShowForm(false);
    setFormError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError('');
    setFormLoading(true);
    try {
      if (editingEmployee) {
        await apiPut(`/employees/${editingEmployee.employee_id}`, {
          name: formData.name,
          department: formData.department || null,
        });
      } else {
        await apiPost('/employees/', {
          employee_id: formData.employee_id,
          name: formData.name,
          department: formData.department || null,
        });
      }
      resetForm();
      fetchEmployees();
    } catch (err) {
      setFormError(err.message);
    } finally {
      setFormLoading(false);
    }
  };

  const handleEdit = (emp) => {
    setEditingEmployee(emp);
    setFormData({
      employee_id: emp.employee_id,
      name: emp.name,
      department: emp.department || '',
    });
    setShowForm(true);
    setFormError('');
  };

  const handleDelete = async (emp) => {
    if (!confirm(`Are you sure you want to delete ${emp.name}?`)) return;
    try {
      await apiDelete(`/employees/${emp.employee_id}`);
      fetchEmployees();
    } catch (err) {
      alert(err.message);
    }
  };

  const handleToggleActive = async (emp) => {
    try {
      await apiPut(`/employees/${emp.employee_id}`, { is_active: !emp.is_active });
      fetchEmployees();
    } catch (err) {
      alert(err.message);
    }
  };

  const handlePhotoUpload = async (emp, file) => {
    setUploadingFor(emp.employee_id);
    setUploadError('');
    try {
      const formData = new FormData();
      formData.append('file', file);
      await apiPostFile(`/employees/${emp.employee_id}/photo`, formData);
      fetchEmployees();
    } catch (err) {
      setUploadError(err.message);
    } finally {
      setUploadingFor(null);
    }
  };

  if (loading) {
    return <div className="text-center py-12 text-gray-500">Loading employees...</div>;
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Employees</h1>
        <button
          onClick={() => {
            resetForm();
            setShowForm(!showForm);
          }}
          className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors"
        >
          {showForm ? 'Cancel' : 'Add Employee'}
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* Add/Edit form */}
      {showForm && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">
            {editingEmployee ? 'Edit Employee' : 'Add New Employee'}
          </h2>
          {formError && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
              {formError}
            </div>
          )}
          <form onSubmit={handleSubmit} className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Employee ID</label>
              <input
                type="text"
                value={formData.employee_id}
                onChange={(e) => setFormData({ ...formData, employee_id: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none text-sm disabled:bg-gray-100"
                placeholder="e.g. EMP001"
                required
                disabled={!!editingEmployee}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none text-sm"
                placeholder="Enter full name"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Department</label>
              <input
                type="text"
                value={formData.department}
                onChange={(e) => setFormData({ ...formData, department: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none text-sm"
                placeholder="e.g. Engineering"
              />
            </div>
            <div className="md:col-span-3">
              <button
                type="submit"
                disabled={formLoading}
                className="px-6 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors disabled:opacity-50"
              >
                {formLoading
                  ? 'Saving...'
                  : editingEmployee
                  ? 'Update Employee'
                  : 'Add Employee'}
              </button>
            </div>
          </form>
        </div>
      )}

      {uploadError && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
          Photo upload error: {uploadError}
        </div>
      )}

      {/* Employees table */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
        <div className="overflow-x-auto">
          {employees.length === 0 ? (
            <div className="p-8 text-center text-gray-400">No employees found</div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-500 bg-gray-50 border-b border-gray-200">
                  <th className="px-5 py-3 font-medium">Employee ID</th>
                  <th className="px-5 py-3 font-medium">Name</th>
                  <th className="px-5 py-3 font-medium">Department</th>
                  <th className="px-5 py-3 font-medium">Face</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {employees.map((emp) => (
                  <tr key={emp.id} className="hover:bg-gray-50">
                    <td className="px-5 py-3 font-mono text-gray-700">{emp.employee_id}</td>
                    <td className="px-5 py-3 font-medium text-gray-900">{emp.name}</td>
                    <td className="px-5 py-3 text-gray-600">{emp.department || '--'}</td>
                    <td className="px-5 py-3">
                      {emp.has_face_encoding ? (
                        <span className="px-2 py-0.5 bg-green-100 text-green-800 rounded text-xs font-medium">
                          Registered
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs font-medium">
                          Not set
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-3">
                      <button
                        onClick={() => handleToggleActive(emp)}
                        className={`px-2 py-0.5 rounded text-xs font-medium cursor-pointer ${
                          emp.is_active
                            ? 'bg-green-100 text-green-800'
                            : 'bg-red-100 text-red-800'
                        }`}
                      >
                        {emp.is_active ? 'Active' : 'Inactive'}
                      </button>
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-2">
                        <label className="text-indigo-600 hover:text-indigo-800 cursor-pointer text-xs font-medium">
                          {uploadingFor === emp.employee_id ? (
                            'Uploading...'
                          ) : (
                            <>
                              Upload Photo
                              <input
                                type="file"
                                accept="image/jpeg,image/png"
                                className="hidden"
                                onChange={(e) => {
                                  if (e.target.files[0]) {
                                    handlePhotoUpload(emp, e.target.files[0]);
                                  }
                                }}
                              />
                            </>
                          )}
                        </label>
                        <button
                          onClick={() => handleEdit(emp)}
                          className="text-gray-500 hover:text-indigo-600 text-xs font-medium"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => handleDelete(emp)}
                          className="text-gray-500 hover:text-red-600 text-xs font-medium"
                        >
                          Delete
                        </button>
                      </div>
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

export default Employees;
