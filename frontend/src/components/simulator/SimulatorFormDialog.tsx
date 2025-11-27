import React, { useEffect, useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  MenuItem,
  CircularProgress,
  Box,
} from '@mui/material';
import { useForm } from 'react-hook-form';
import { Simulator, SimulatorCreate, SimulatorUpdate } from '../../types/simulator.types';

interface SimulatorFormDialogProps {
  open: boolean;
  simulator: Simulator | null;
  onClose: () => void;
  onSubmit: (data: SimulatorCreate | SimulatorUpdate) => Promise<void>;
}

export const SimulatorFormDialog: React.FC<SimulatorFormDialogProps> = ({ open, simulator, onClose, onSubmit }) => {
  const { register, handleSubmit, formState, reset, setValue } = useForm<SimulatorCreate | SimulatorUpdate>({
    defaultValues: {
      ip_address: '',
      type: '',
      version: '',
      map: '',
      status: '',
    } as SimulatorCreate,
  });

  const { errors } = formState;
  const [isLoading, setIsLoading] = useState(false);

  const isEditMode = !!simulator;

  useEffect(() => {
    if (simulator) {
      setValue('ip_address' as keyof (SimulatorCreate & SimulatorUpdate), simulator.ip_address as any);
      setValue('type' as keyof (SimulatorCreate & SimulatorUpdate), simulator.type as any);
      setValue('version' as keyof (SimulatorCreate & SimulatorUpdate), simulator.version as any);
      setValue('map' as keyof (SimulatorCreate & SimulatorUpdate), simulator.map as any);
      setValue('status' as keyof (SimulatorCreate & SimulatorUpdate), simulator.status as any);
    } else {
      reset();
    }
  }, [simulator, setValue, reset]);

  const ipPattern = /^((25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(25[0-5]|2[0-4]\d|[01]?\d\d?)$/;

  const handleFormSubmit = async (data: SimulatorCreate | SimulatorUpdate) => {
    setIsLoading(true);
    try {
      await onSubmit(data);
      reset();
      onClose();
    } catch (err) {
      // swallow here; the store/service should set global error if needed
      console.error('Simulator submit failed', err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth scroll="body" PaperProps={{ sx: { margin: '32px' } }}>
      <DialogTitle>{isEditMode ? 'Edit Simulator' : 'Create Simulator'}</DialogTitle>
      <DialogContent sx={{ paddingTop: '24px !important', paddingBottom: '24px' }}>
        <form id="simulator-form" onSubmit={handleSubmit(handleFormSubmit)}>
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 2 }}>
            <Box>
              <TextField
                label="IP Address"
                fullWidth
                disabled={isEditMode}
                {...register('ip_address' as any, {
                  required: 'IP Address is required',
                  pattern: { value: ipPattern, message: 'Invalid IP address' },
                })}
                error={!!(errors as any)?.ip_address}
                helperText={(errors as any)?.ip_address?.message}
              />
            </Box>

            <Box>
              <TextField
                label="Type"
                fullWidth
                select
                defaultValue=""
                {...register('type' as any, { required: 'Type is required' })}
                error={!!(errors as any)?.type}
                helperText={(errors as any)?.type?.message}
              >
                <MenuItem value="DefensePro">DefensePro</MenuItem>
                <MenuItem value="Alteon">Alteon</MenuItem>
                <MenuItem value="AppWall">AppWall</MenuItem>
              </TextField>
            </Box>

            <Box>
              <TextField
                label="Version"
                fullWidth
                {...register('version' as any, { required: 'Version is required' })}
                error={!!(errors as any)?.version}
                helperText={(errors as any)?.version?.message}
              />
            </Box>

            <Box>
              <TextField
                label="Map"
                fullWidth
                select
                defaultValue=""
                {...register('map' as any, { required: 'Map is required' })}
                error={!!(errors as any)?.map}
                helperText={(errors as any)?.map?.message}
              >
                <MenuItem value="prod">prod</MenuItem>
                <MenuItem value="qa">qa</MenuItem>
                <MenuItem value="dev">dev</MenuItem>
              </TextField>
            </Box>

            <Box>
              <TextField
                label="Status"
                fullWidth
                select
                defaultValue=""
                {...register('status' as any, { required: 'Status is required' })}
                error={!!(errors as any)?.status}
                helperText={(errors as any)?.status?.message}
              >
                <MenuItem value="Active">Active</MenuItem>
                <MenuItem value="Inactive">Inactive</MenuItem>
              </TextField>
            </Box>

          </Box>
        </form>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={isLoading}>Cancel</Button>
        <Button type="submit" form="simulator-form" variant="contained" disabled={isLoading}>
          {isLoading ? <CircularProgress size={20} /> : (isEditMode ? 'Save' : 'Create')}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default SimulatorFormDialog;
