import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { Box, TextField, Button, Typography, Paper, Alert, CircularProgress } from '@mui/material';
import { useAuthStore } from '../store/authStore';
import { LoginRequest } from '../types/auth';

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const { login, isLoading, error, isAuthenticated, clearError } = useAuthStore();

  const { register, handleSubmit, formState } = useForm<LoginRequest>();
  const { errors } = formState;

  useEffect(() => {
    if (isAuthenticated) {
      navigate('/dashboard');
    }
  }, [isAuthenticated, navigate]);

  useEffect(() => {
    return () => {
      clearError();
    };
  }, []);

  const onSubmit = async (data: LoginRequest) => {
    await login(data.username, data.password);
  };

  return (
    <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh">
      <Paper elevation={3} sx={{ p: 4, width: 360 }}>
        {/* Logo Box */}
        <Box
          sx={{
            width: '120px',
            height: '80px',
            margin: '0 auto 30px',
            background: 'linear-gradient(135deg, #0052CC 0%, #0066FF 100%)',
            borderRadius: '8px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'white',
            fontWeight: 'bold',
            fontSize: '14px',
          }}
        >
          RADWARE
        </Box>

        {/* Title */}
        <Typography
          variant="h1"
          sx={{
            fontSize: '42px',
            fontWeight: 700,
            color: '#0052CC',
            textAlign: 'center',
            marginBottom: '15px',
            letterSpacing: '-0.5px',
          }}
        >
          Radware Simulator Tools
        </Typography>

        {/* Subtitle */}
        <Typography sx={{ fontSize: '18px', color: '#666', textAlign: 'center', marginBottom: '40px' }}>
          Network Security Testing Platform
        </Typography>

        {/* Existing error Alert (kept) */}
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

        {/* Existing form (kept) */}
        <form onSubmit={handleSubmit(onSubmit)} noValidate>
          <TextField
            label="Username"
            fullWidth
            margin="normal"
            {...register('username', { required: 'Username is required' })}
            error={!!errors.username}
            helperText={errors.username?.message as string}
          />
          <TextField
            label="Password"
            type="password"
            fullWidth
            margin="normal"
            {...register('password', { required: 'Password is required' })}
            error={!!errors.password}
            helperText={errors.password?.message as string}
          />
          <Button
            type="submit"
            variant="contained"
            color="primary"
            fullWidth
            sx={{ mt: 2 }}
            disabled={isLoading}
          >
            {isLoading ? <CircularProgress size={20} /> : 'Login'}
          </Button>
        </form>

        {/* Footer */}
        <Typography sx={{ marginTop: '50px', paddingTop: '30px', borderTop: '1px solid #E8E8E8', textAlign: 'center', color: '#999', fontSize: '12px' }}>
          © 2025 Radware. All rights reserved.
        </Typography>
      </Paper>
    </Box>
  );
};
