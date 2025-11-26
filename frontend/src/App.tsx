import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import GlobalStyles from './components/GlobalStyles';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { ProtectedRoute } from './components/auth/ProtectedRoute';
import { useAuthStore } from './store/authStore';
import { Layout } from './components/common/Layout';

function App() {
  const checkAuth = useAuthStore(state => state.checkAuth);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

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
                <Layout>
                  <div>Simulators Page (Coming Soon)</div>
                </Layout>
              </ProtectedRoute>
            }
          />

          <Route
            path="/cybercontroller"
            element={
              <ProtectedRoute requiredRoles={["admin", "cc_admin"]}>
                <Layout>
                  <div>CyberController Page (Coming Soon)</div>
                </Layout>
              </ProtectedRoute>
            }
          />

          <Route
            path="/users"
            element={
              <ProtectedRoute requiredRoles={["admin"]}>
                <Layout>
                  <div>User Management (Coming Soon)</div>
                </Layout>
              </ProtectedRoute>
            }
          />

        </Routes>
      </BrowserRouter>
    </>
  );
}

export default App;
