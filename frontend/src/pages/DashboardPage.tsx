import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Box, Typography, Paper } from '@mui/material';
import ComputerIcon from '@mui/icons-material/Computer';
import SecurityIcon from '@mui/icons-material/Security';
import PeopleIcon from '@mui/icons-material/People';
import { useAuthStore } from '../store/authStore';
import { Layout } from '../components/common/Layout';

export const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuthStore();

  const isAdmin = user?.roles?.includes('admin');
  const isSaproAdmin = user?.roles?.includes('sapro_admin');
  const isCCAdmin = user?.roles?.includes('cc_admin');

  const canAccessSapro = !!(isAdmin || isSaproAdmin);
  const canAccessCC = !!(isAdmin || isCCAdmin);

  const cardSx = {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '40px 30px',
    borderRadius: '12px',
    cursor: 'pointer',
    transition: 'all 0.3s ease',
    border: '2px solid #E8E8E8',
    background: '#FAFBFC',
    '&:hover': {
      borderColor: '#0052CC',
      background: '#F0F4FF',
      transform: 'translateY(-4px)',
      boxShadow: '0 12px 24px rgba(0, 82, 204, 0.15)'
    }
  } as const;

  const iconSx = {
    fontSize: '36px',
    color: 'white',
    background: 'linear-gradient(135deg, #0052CC 0%, #0066FF 100%)',
    borderRadius: '12px',
    padding: '17px',
    marginBottom: '20px'
  } as const;

  return (
    <Layout>
      <Box sx={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', padding: '20px' }}>
        <Paper sx={{ maxWidth: '900px', width: '100%', padding: '60px 40px', borderRadius: '12px', boxShadow: '0 20px 60px rgba(0, 0, 0, 0.15)' }}>
          <Typography variant="h1" sx={{ fontSize: '42px', fontWeight: 700, color: '#0052CC', textAlign: 'center', marginBottom: '15px' }}>
            Welcome to Simulator Tools
          </Typography>

          <Typography sx={{ fontSize: '18px', color: '#666', textAlign: 'center', marginBottom: '50px' }}>
            Select a tool to get started
          </Typography>

          <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))', gap: '40px', justifyContent: 'center' }}>

            {/* Card 1 - Sapro Tools */}
            {canAccessSapro && (
              <Box sx={cardSx} onClick={() => navigate('/simulators')}>
                <ComputerIcon sx={iconSx} />
                <Typography sx={{ fontSize: '20px', fontWeight: 600, marginBottom: '10px' }}>Sapro Tools</Typography>
                <Typography sx={{ fontSize: '14px', color: '#666', textAlign: 'center' }}>Manage simulators and configurations</Typography>
              </Box>
            )}

            {/* Card 2 - CyberController */}
            {canAccessCC && (
              <Box sx={cardSx} onClick={() => navigate('/cybercontroller')}>
                <SecurityIcon sx={iconSx} />
                <Typography sx={{ fontSize: '20px', fontWeight: 600, marginBottom: '10px' }}>CyberController</Typography>
                <Typography sx={{ fontSize: '14px', color: '#666', textAlign: 'center' }}>Manage CyberController devices and operations</Typography>
              </Box>
            )}

            {/* Card 3 - User Management (admin only) */}
            {isAdmin && (
              <Box sx={{ ...cardSx, gridColumn: '1 / -1', maxWidth: '400px', margin: '0 auto' }} onClick={() => navigate('/users')}>
                <PeopleIcon sx={iconSx} />
                <Typography sx={{ fontSize: '20px', fontWeight: 600, marginBottom: '10px' }}>User Management</Typography>
                <Typography sx={{ fontSize: '14px', color: '#666', textAlign: 'center' }}>Manage users, roles and permissions</Typography>
              </Box>
            )}

          </Box>

        </Paper>
      </Box>
    </Layout>
  );
};
