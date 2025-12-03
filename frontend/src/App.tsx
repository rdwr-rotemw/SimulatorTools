import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import GlobalStyles from './components/GlobalStyles';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { ProtectedRoute } from './components/auth/ProtectedRoute';
import { useAuthStore } from './store/authStore';
import { SimulatorsPage } from './pages/SimulatorsPage';
import { UsersPage } from './pages/UsersPage';
import { CCLoginPage } from './pages/CCLoginPage';
import CCManagementPage from './pages/CCManagementPage';
import { CCDashboardPage } from './pages/CCDashboardPage';
import { ReportingPage } from './pages/ReportingPage';
import { SNMPPage } from './pages/SNMPPage';
import { IRPManagerPage } from './pages/IRPManagerPage';
import { IRPSenderPage } from './pages/IRPSenderPage';

function App() {
  const checkAuth = useAuthStore(state => state.checkAuth);

  useEffect(() => {
    checkAuth();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <>
      <GlobalStyles />
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Navigate to="/login" replace />} />
          <Route path="/login" element={<LoginPage />} />

          {/* Protected dashboard route */}
          <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />

          {/* Placeholder protected routes for future pages */}
          <Route
            path="/simulators"
            element={
              <ProtectedRoute requiredRoles={["admin", "sapro_admin"]}>
                <SimulatorsPage />
              </ProtectedRoute>
            }
          />

          <Route path="/cybercontroller" element={<Navigate to="/cc/login" replace />} />

          <Route path="/cc/login" element={<CCLoginPage />} />
          <Route
            path="/cc/dashboard"
            element={
              <ProtectedRoute requiredRoles={["admin", "cc_admin"]}>
                <CCDashboardPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/cc/manage"
            element={
              <ProtectedRoute requiredRoles={["admin", "cc_admin"]}>
                <CCManagementPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/cc/reporting"
            element={
              <ProtectedRoute requiredRoles={["admin", "cc_admin"]}>
                <ReportingPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/cc/reporting/snmp"
            element={
              <ProtectedRoute requiredRoles={["admin", "cc_admin"]}>
                <SNMPPage />
              </ProtectedRoute>
            }
          />

          <Route path="/cc/reporting/irp/send" element={<ProtectedRoute requiredRoles={["admin", "cc_admin"]}><IRPSenderPage /></ProtectedRoute>} />
          <Route path="/cc/reporting/irp" element={<ProtectedRoute requiredRoles={["admin", "cc_admin"]}><IRPManagerPage /></ProtectedRoute>} />

          <Route
            path="/users"
            element={
              <ProtectedRoute requiredRoles={["admin"]}>
                <UsersPage />
              </ProtectedRoute>
            }
          />

        </Routes>
      </BrowserRouter>
    </>
  );
}

export default App;
