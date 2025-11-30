import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  MenuItem,
  Alert,
  CircularProgress,
  Box,
} from '@mui/material';
import { useForm } from 'react-hook-form';
import { CCAddDeviceRequest } from '../../types/cc.types';

interface CCAddDeviceDialogProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: CCAddDeviceRequest) => Promise<void>;
}

export const CCAddDeviceDialog: React.FC<CCAddDeviceDialogProps> = ({ open, onClose, onSubmit }) => {
  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm<CCAddDeviceRequest>({
    defaultValues: {
      username: '',
      password: '',
      name: '',
      management_ip: '',
      device_type: '',
      device_user: '',
      device_password: '',
    },
  });

  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      reset();
    }
  }, [open, reset]);

  const ipv4Pattern = /^(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)){3}$/;

  const handleFormSubmit = handleSubmit(async (data: CCAddDeviceRequest) => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      await onSubmit(data);
      onClose();
      reset();
    } catch (err: any) {
      const message = err?.response?.data?.detail || err?.message || 'An error occurred';
      setErrorMessage(message);
    } finally {
      setIsLoading(false);
    }
  });

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      scroll="body"
      sx={{ m: '32px' }}
    >
      <DialogTitle>Add Device to CyberController</DialogTitle>

      <DialogContent sx={{ pt: '24px', pb: '24px' }}>
        {errorMessage && (
          <Box mb={2}>
            <Alert severity="error">{errorMessage}</Alert>
          </Box>
        )}

        <form id="cc-add-device-form" onSubmit={handleFormSubmit}>
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: 'repeat(2, 1fr)',
              gap: 2,
            }}
          >
            <TextField
              label="Username"
              fullWidth
              size="small"
              {...register('username', { required: 'Username is required' })}
              error={!!errors.username}
              helperText={errors.username?.message}
            />

            <TextField
              label="Password"
              type="password"
              fullWidth
              size="small"
              {...register('password', { required: 'Password is required' })}
              error={!!errors.password}
              helperText={errors.password?.message}
            />

            <TextField
              label="Device Name"
              fullWidth
              size="small"
              {...register('name', { required: 'Device name is required' })}
              error={!!errors.name}
              helperText={errors.name?.message}
            />

            <TextField
              label="Management IP"
              fullWidth
              size="small"
              {...register('management_ip', {
                required: 'Management IP is required',
                pattern: { value: ipv4Pattern, message: 'Enter a valid IPv4 address' },
              })}
              error={!!errors.management_ip}
              helperText={errors.management_ip?.message}
            />

            <TextField
              label="Device Type"
              select
              fullWidth
              size="small"
              defaultValue=""
              {...register('device_type', { required: 'Device type is required' })}
              error={!!errors.device_type}
              helperText={errors.device_type?.message}
            >
              <MenuItem value="DefensePro">DefensePro</MenuItem>
              <MenuItem value="Alteon">Alteon</MenuItem>
              <MenuItem value="AppWall">AppWall</MenuItem>
            </TextField>

            <TextField
              label="Device User"
              fullWidth
              size="small"
              {...register('device_user', { required: 'Device user is required' })}
              error={!!errors.device_user}
              helperText={errors.device_user?.message}
            />

            <TextField
              label="Device Password"
              type="password"
              fullWidth
              size="small"
              {...register('device_password', { required: 'Device password is required' })}
              error={!!errors.device_password}
              helperText={errors.device_password?.message}
            />

            {/* If you need to add parent_orm in the future, add another field here */}
          </Box>
        </form>
      </DialogContent>

      <DialogActions>
        <Button
          onClick={() => {
            reset();
            onClose();
          }}
          disabled={isLoading}
        >
          Cancel
        </Button>

        <Button type="submit" form="cc-add-device-form" variant="contained" disabled={isLoading}>
          {isLoading ? <CircularProgress size={20} color="inherit" /> : 'Add Device'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};
