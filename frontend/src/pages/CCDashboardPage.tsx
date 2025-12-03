import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Box, Typography } from '@mui/material';
import ComputerIcon from '@mui/icons-material/Computer';
import BarChartIcon from '@mui/icons-material/BarChart';
import Layout from '../components/common/Layout';
import useCCStore from '../store/ccStore';

export const CCDashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const currentCC = useCCStore((state) => state.currentCC);

  useEffect(() => {
    if (!currentCC) {
      navigate('/cc/login');
    }
  }, [currentCC, navigate]);

  const cardSx = {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    p: '50px 40px',
    borderRadius: '12px',
    cursor: 'pointer',
    transition: 'all 0.3s ease',
    border: '2px solid #E8E8E8',
    background: '#FAFBFC',
    '&:hover': {
      borderColor: '#0052CC',
      background: '#F0F4FF',
      transform: 'translateY(-4px)',
      boxShadow: '0 12px 24px rgba(0,82,204,0.15)',
    },
  } as const;

  const iconSx = {
    fontSize: '48px',
    color: 'white',
    background: 'linear-gradient(135deg, #0052CC 0%, #0066FF 100%)',
    borderRadius: '12px',
    p: '20px',
    mb: '20px',
  } as const;

  return (
    <Layout>
      <Box sx={{ p: 4 }}>
        <Typography variant="h4" sx={{ mb: 1 }}>
          CyberController Dashboard
        </Typography>

        <Typography variant="body2" sx={{ color: '#666', mb: 5 }}>
          Connected to CyberController at {currentCC}
        </Typography>

        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: 4,
            maxWidth: '1000px',
            margin: '0 auto',
          }}
        >
          <Box role="button" onClick={() => navigate('/cc/manage')} sx={cardSx}>
            <ComputerIcon sx={iconSx} />
            <Typography sx={{ fontSize: '24px', fontWeight: 600, mb: '10px' }}>Simulators Devices</Typography>
            <Typography sx={{ fontSize: '14px', color: '#666', textAlign: 'center' }}>
              Manage simulator devices and configurations.
            </Typography>
          </Box>

          <Box role="button" onClick={() => navigate('/cc/reporting')} sx={cardSx}>
            <BarChartIcon sx={iconSx} />
            <Typography sx={{ fontSize: '24px', fontWeight: 600, mb: '10px' }}>Reporting</Typography>
            <Typography sx={{ fontSize: '14px', color: '#666', textAlign: 'center' }}>
              SNMP traps, IRP messages, and polling.
            </Typography>
          </Box>
        </Box>
      </Box>
    </Layout>
  );
};
