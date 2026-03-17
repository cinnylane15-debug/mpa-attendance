import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';

function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col">
        {/* Top bar */}
        <header className="bg-white shadow-sm border-b border-gray-200 px-6 py-4 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-800">
              Face Recognition Attendance System
            </h2>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-600">
              {user?.username}
              <span className="ml-2 px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded text-xs font-medium">
                {user?.role}
              </span>
            </span>
            <button
              onClick={handleLogout}
              className="text-sm text-gray-500 hover:text-red-600 transition-colors font-medium"
            >
              Logout
            </button>
          </div>
        </header>
        {/* Main content */}
        <main className="flex-1 p-6 bg-gray-50 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export default Layout;
