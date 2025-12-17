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
import useCCStore from '../../store/ccStore';

interface CCAddDeviceDialogProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: CCAddDeviceRequest) => Promise<void>;
  ccIp: string;
}

export const CCAddDeviceDialog: React.FC<CCAddDeviceDialogProps> = ({ open, onClose, onSubmit, ccIp }) => {
  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm<CCAddDeviceRequest>({
    defaultValues: {
      name: '',
      type: '',
      cli_username: 'radware',
      cli_password: 'radware1',
      http_username: 'radware',
      https_password: 'radware1',
      management_ip: '',
      vision_mgt_port: '',
      register_device_events: false,
    },
  });

  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Get management ports from Zustand store
  const managementPorts = useCCStore((state) => state.managementPorts);

  useEffect(() => {
    if (!open) {
      reset();
      setErrorMessage(null);
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

      <DialogContent sx={{ pt: '32px', pb: '24px' }}>
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
              rowGap: 3,
              mt: 3,
            }}
          >
            {/* Device Name */}
            <TextField
              label="Device Name"
              fullWidth
              size="small"
              {...register('name', { required: 'Device name is required' })}
              error={!!errors.name}
              helperText={errors.name?.message}
              sx={{ '& label': { fontSize: '14px' } }}
            />

            {/* Device Type */}
            <TextField
              label="Device Type"
              select
              fullWidth
              size="small"
              defaultValue=""
              {...register('type', { required: 'Device type is required' })}
              error={!!errors.type}
              helperText={errors.type?.message}
              sx={{ '& label': { fontSize: '14px' } }}
            >
              <MenuItem value="DefensePro">DefensePro</MenuItem>
              <MenuItem value="Alteon">Alteon</MenuItem>
            </TextField>

            {/* Management IP */}
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
              sx={{ '& label': { fontSize: '14px' } }}
            />

            {/* Vision Management Port */}
            <TextField
              label="Vision Management Port"
              select
              fullWidth
              size="small"
              defaultValue=""
              {...register('vision_mgt_port', { required: 'Vision management port is required' })}
              error={!!errors.vision_mgt_port}
              helperText={errors.vision_mgt_port?.message}
              disabled={managementPorts.length === 0}
              sx={{ '& label': { fontSize: '14px' } }}
            >
              {managementPorts.length > 0 ? (
                managementPorts.map((port) => (
                  <MenuItem key={port.interface} value={port.interface}>
                    {port.interface} ({port.address})
                  </MenuItem>
                ))
              ) : (
                <MenuItem value="">No ports available</MenuItem>
              )}
            </TextField>

            {/* CLI Username */}
            <TextField
              label="CLI Username"
              fullWidth
              size="small"
              {...register('cli_username', { required: 'CLI username is required' })}
              error={!!errors.cli_username}
              helperText={errors.cli_username?.message}
              sx={{ '& label': { fontSize: '14px' } }}
            />

            {/* CLI Password */}
            <TextField
              label="CLI Password"
              type="password"
              fullWidth
              size="small"
              {...register('cli_password', { required: 'CLI password is required' })}
              error={!!errors.cli_password}
              helperText={errors.cli_password?.message}
              sx={{ '& label': { fontSize: '14px' } }}
            />

            {/* HTTP Username */}
            <TextField
              label="HTTP Username"
              fullWidth
              size="small"
              {...register('http_username', { required: 'HTTP username is required' })}
              error={!!errors.http_username}
              helperText={errors.http_username?.message}
              sx={{ '& label': { fontSize: '14px' } }}
            />

            {/* HTTPS Password */}
            <TextField
              label="HTTPS Password"
              type="password"
              fullWidth
              size="small"
              {...register('https_password', { required: 'HTTPS password is required' })}
              error={!!errors.https_password}
              helperText={errors.https_password?.message}
              sx={{ '& label': { fontSize: '14px' } }}
            />

            {/* Register Device Events */}
            <TextField
              label="Register Device Events"
              select
              fullWidth
              size="small"
              defaultValue={false}
              {...register('register_device_events')}
              sx={{ '& label': { fontSize: '14px' } }}
            >
              <MenuItem value={false as any}>False</MenuItem>
              <MenuItem value={true as any}>True</MenuItem>
            </TextField>
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
