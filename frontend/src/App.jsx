import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import AppLayout from './components/AppLayout';
import ProtectedRoute from './components/ProtectedRoute';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Students from './pages/Students';
import Classes from './pages/Classes';
import Attendance from './pages/Attendance';
import Cameras from './pages/Cameras';
import Schedules from './pages/Schedules';
import Holidays from './pages/Holidays';
import UnknownFaces from './pages/UnknownFaces';

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<Dashboard />} />
        <Route path="/students" element={<Students />} />
        <Route path="/classes" element={<Classes />} />
        <Route path="/attendance" element={<Attendance />} />
        <Route path="/cameras" element={<Cameras />} />
        <Route path="/schedules" element={<Schedules />} />
        <Route path="/holidays" element={<Holidays />} />
        <Route path="/unknown-faces" element={<UnknownFaces />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
