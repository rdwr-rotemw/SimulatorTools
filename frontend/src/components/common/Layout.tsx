import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Box, AppBar, Toolbar, Typography, Button, IconButton, Snackbar, Alert } from '@mui/material';
import LogoutIcon from '@mui/icons-material/Logout';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useAuthStore } from '../../store/authStore';
import { useCCStore } from '../../store/ccStore';
import { CCLogoutWarningDialog } from '../cc/CCLogoutWarningDialog';

interface LayoutProps {
  children: React.ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuthStore();
  const { currentCC, logout: ccLogout, clearState } = useCCStore();

  const [snackbarOpen, setSnackbarOpen] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');
  const [snackbarSeverity, setSnackbarSeverity] = useState<'success' | 'error'>('success');
  const [showCCLogoutDialog, setShowCCLogoutDialog] = useState(false);

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const handleCCLogout = async () => {
    if (!currentCC) return;

    try {
      await ccLogout(currentCC);
      clearState();
      navigate('/cc/login');
      setSnackbarMessage('Successfully logged out from CC');
      setSnackbarSeverity('success');
      setSnackbarOpen(true);
    } catch (error) {
      console.error('Failed to logout from CC:', error);
      setSnackbarMessage('Failed to logout from CC');
      setSnackbarSeverity('error');
      setSnackbarOpen(true);
    }
  };

  const handleSnackbarClose = () => {
    setSnackbarOpen(false);
  };

  const handleLogoutAndLeave = async () => {
    if (currentCC) {
      await ccLogout(currentCC);
      clearState();
    }
    setShowCCLogoutDialog(false);
    navigate('/cc/login'); // Explicitly go to login after logout
  };

  // Browser back button listener - ONLY intercept from CC Dashboard
  useEffect(() => {
    const handlePopState = () => {
      const path = location.pathname;

      // ONLY intercept when on CC Dashboard with active session
      // Because back from dashboard goes to login screen
      if (path === '/cc/dashboard' && currentCC) {
        // Prevent navigation and show warning
        window.history.pushState(null, '', path);
        setShowCCLogoutDialog(true);
      }
    };

    // Push initial state only when on CC Dashboard
    if (location.pathname === '/cc/dashboard' && currentCC) {
      window.history.pushState(null, '', location.pathname);
    }

    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, [location.pathname, currentCC]);

  const pathname = location.pathname;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <AppBar position="sticky" sx={{ background: 'linear-gradient(135deg, #0052CC 0%, #0066FF 100%)', boxShadow: 'none' }}>
        <Toolbar sx={{ display: 'flex', justifyContent: 'space-between' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <img
              src="/assets/images/radware-logo.jpg"
              alt="Radware"
              style={{ height: '32px' }}
            />
            <Typography variant="h6" sx={{ color: 'white', fontWeight: 600 }}>
              Simulator Tools
            </Typography>
          </Box>

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <IconButton onClick={() => {
              // Special handling for CC login page - go back to main dashboard
              if (pathname === '/cc/login') {
                navigate('/dashboard');
              } else {
                navigate(-1);
              }
            }} sx={{ color: 'white' }}>
              <ArrowBackIcon />
            </IconButton>
            <Typography variant="body2" sx={{ color: 'white' }}>
              {`Welcome${user ? `, ${user.username}` : ''}`}
            </Typography>

            {/* CC Logout Button - only show on CC pages when logged into a CC */}
            {pathname.startsWith('/cc/') && currentCC && (
              <Button
                startIcon={<LogoutIcon />}
                variant="outlined"
                onClick={handleCCLogout}
                sx={{
                  color: 'white',
                  borderColor: 'white',
                  textTransform: 'none',
                  '&:hover': {
                    borderColor: 'rgba(255, 255, 255, 0.7)',
                    backgroundColor: 'rgba(255, 255, 255, 0.1)',
                  },
                }}
              >
                Logout from CC
              </Button>
            )}

            {/* Main App Logout Button */}
            <Button startIcon={<LogoutIcon />} onClick={handleLogout} sx={{ color: 'white', textTransform: 'none' }}>
              Logout
            </Button>
          </Box>
        </Toolbar>
      </AppBar>

      <Box component="main" sx={{ flex: 1, padding: 0 }}>
        {children}
      </Box>

      <Snackbar
        open={snackbarOpen}
        autoHideDuration={6000}
        onClose={handleSnackbarClose}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={handleSnackbarClose} severity={snackbarSeverity} sx={{ width: '100%' }}>
          {snackbarMessage}
        </Alert>
      </Snackbar>

      <CCLogoutWarningDialog
        open={showCCLogoutDialog}
        onClose={() => setShowCCLogoutDialog(false)}
        onLogoutAndLeave={handleLogoutAndLeave}
        ccIp={currentCC || ''}
      />
    </Box>
  );
};

export default Layout;
