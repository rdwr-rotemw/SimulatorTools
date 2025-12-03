import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Box, Typography } from '@mui/material';
import NotificationsActiveIcon from '@mui/icons-material/NotificationsActive';
import MessageIcon from '@mui/icons-material/Message';
import PollIcon from '@mui/icons-material/Poll';
import Layout from '../components/common/Layout';
import useCCStore from '../store/ccStore';

export const ReportingPage: React.FC = () => {
  const navigate = useNavigate();
  const currentCC = useCCStore((state) => state.currentCC);

  useEffect(() => {
    if (!currentCC) {
      navigate('/cc/login');
    }
  }, [currentCC, navigate]);

  return (
    <Layout>
      <Box sx={{ p: 4 }}>
        <Typography variant="h4" sx={{ mb: 1 }}>
          Reporting Dashboard
        </Typography>
        <Typography variant="body2" sx={{ color: '#666', mb: 5 }}>
          {`Send traps, messages, and configure polling for CyberController at ${currentCC ?? ''}`}
        </Typography>

        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: 4,
            maxWidth: '1200px',
            margin: '0 auto',
          }}
        >
          {/* SNMP Traps Card */}
          <Box
            onClick={() => navigate('/cc/reporting/snmp')}
            role="button"
            tabIndex={0}
            sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '50px 40px',
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
            }}
          >
            <NotificationsActiveIcon
              sx={{
                fontSize: 48,
                color: 'white',
                backgroundImage: 'linear-gradient(135deg, #FF6B6B 0%, #FF8E53 100%)',
                borderRadius: '12px',
                padding: '20px',
                mb: 2,
              }}
            />
            <Typography sx={{ fontSize: 24, fontWeight: 600, mb: 1 }}>SNMP Traps</Typography>
            <Typography sx={{ fontSize: 14, color: '#666', textAlign: 'center' }}>
              Send attack traps to simulators.
            </Typography>
          </Box>

          {/* IRP Messages Card */}
          <Box
            onClick={() => navigate('/cc/reporting/irp')}
            role="button"
            tabIndex={0}
            sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '50px 40px',
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
            }}
          >
            <MessageIcon
              sx={{
                fontSize: 48,
                color: 'white',
                backgroundImage: 'linear-gradient(135deg, #4CAF50 0%, #81C784 100%)',
                borderRadius: '12px',
                padding: '20px',
                mb: 2,
              }}
            />
            <Typography sx={{ fontSize: 24, fontWeight: 600, mb: 1 }}>IRP Messages</Typography>
            <Typography sx={{ fontSize: 14, color: '#666', textAlign: 'center' }}>
              Build and send IRP messages.
            </Typography>
          </Box>

          {/* Polling Card */}
          <Box
            onClick={() => navigate('/cc/reporting/polling')}
            role="button"
            tabIndex={0}
            sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '50px 40px',
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
            }}
          >
            <PollIcon
              sx={{
                fontSize: 48,
                color: 'white',
                backgroundImage: 'linear-gradient(135deg, #2196F3 0%, #64B5F6 100%)',
                borderRadius: '12px',
                padding: '20px',
                mb: 2,
              }}
            />
            <Typography sx={{ fontSize: 24, fontWeight: 600, mb: 1 }}>Polling</Typography>
            <Typography sx={{ fontSize: 14, color: '#666', textAlign: 'center' }}>
              Configure polling pages data.
            </Typography>
          </Box>
        </Box>
      </Box>
    </Layout>
  );
};
