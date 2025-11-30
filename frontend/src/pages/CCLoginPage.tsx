import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Box, TextField, Button, Typography, Paper, Alert, CircularProgress } from '@mui/material';
import { useForm } from 'react-hook-form';
import { useCCStore } from '../store/ccStore';
import { Layout } from '../components/common/Layout';

interface FormValues {
  cc_ip: string;
  username: string;
  password: string;
}

export const CCLoginPage: React.FC = () => {
  const navigate = useNavigate();
  const { login, isLoading, error, clearError } = useCCStore();

  const { register, handleSubmit } = useForm<FormValues>({
    defaultValues: { cc_ip: '', username: '', password: '' },
  });

  useEffect(() => {
    return () => {
      clearError();
    };
  }, [clearError]);

  const onSubmit = async (data: FormValues) => {
    try {
      await login(data.cc_ip, data.username, data.password);
      navigate('/cc/dashboard');
    } catch (err) {
      // store sets error; keep dialog open and show Alert via `error`
      // no additional handling here
    }
  };

  return (
    <Layout>
      <Box sx={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', padding: '20px', background: 'linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)' }}>
        <Paper sx={{ maxWidth: '500px', width: '100%', padding: '60px 40px', borderRadius: '12px', boxShadow: '0 20px 60px rgba(0,0,0,0.15)' }}>
          <Box sx={{ width: '120px', height: '80px', margin: '0 auto 30px', background: 'linear-gradient(135deg, #0052CC 0%, #0066FF 100%)', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontWeight: 'bold', fontSize: '14px' }}>RADWARE</Box>

          <Typography variant="h1" sx={{ fontSize: '42px', fontWeight: 700, color: '#0052CC', textAlign: 'center', marginBottom: '15px', letterSpacing: '-0.5px' }}>CyberController Login</Typography>

          <Typography sx={{ fontSize: '18px', color: '#666', textAlign: 'center', marginBottom: '40px' }}>Connect to CyberController</Typography>

          {error && (
            <Alert severity="error" sx={{ marginBottom: 2 }}>{error}</Alert>
          )}

          <form onSubmit={handleSubmit(onSubmit)}>
            <Box sx={{ display: 'grid', gap: 2 }}>
              <TextField label="CC IP Address" fullWidth required {...register('cc_ip', { required: true })} />
              <TextField label="Username" fullWidth required {...register('username', { required: true })} />
              <TextField label="Password" fullWidth type="password" required {...register('password', { required: true })} />

              <Button type="submit" fullWidth sx={{ background: '#0052CC', color: 'white', '&:hover': { background: '#0047b3' } }} disabled={isLoading}>
                {isLoading ? <CircularProgress size={20} color="inherit" /> : 'LOGIN'}
              </Button>
            </Box>
          </form>
        </Paper>
      </Box>
    </Layout>
  );
};
