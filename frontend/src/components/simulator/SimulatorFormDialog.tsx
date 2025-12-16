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
import apiClient from '../../api/client';

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
      map: '',
      template_id: '',
    } as SimulatorCreate,
  });

  const { errors } = formState;
  const [isLoading, setIsLoading] = useState(false);
  const [templates, setTemplates] = useState<Array<{ _id: string; name: string }>>([]);
  const [isTemplatesLoading, setIsTemplatesLoading] = useState(false);

  const isEditMode = !!simulator;

  useEffect(() => {
    // Populate form values when editing
    if (simulator) {
      setValue('ip_address' as keyof (SimulatorCreate & SimulatorUpdate), simulator.ip_address as any);
      setValue('map' as keyof (SimulatorCreate & SimulatorUpdate), (simulator.map || '') as any);
      // If simulator includes template_id or template, try to set it
      if ((simulator as any).template_id) {
        setValue('template_id' as keyof (SimulatorCreate & SimulatorUpdate), (simulator as any).template_id as any);
      }
    } else {
      reset();
    }
  }, [simulator, setValue, reset]);

  useEffect(() => {
    // Fetch templates on mount
    let cancelled = false;
    const loadTemplates = async () => {
      setIsTemplatesLoading(true);
      try {
        const resp = await apiClient.get('/device-templates');
        // Expect an array of {_id, name, description, created_at}
        const data = resp.data as Array<any>;
        if (!cancelled) {
          setTemplates(data.map((t) => ({ _id: t._id, name: t.name })));
        }
      } catch (err) {
        console.error('Failed to load device templates', err);
        if (!cancelled) setTemplates([]);
      } finally {
        if (!cancelled) setIsTemplatesLoading(false);
      }
    };

    loadTemplates();
    return () => {
      cancelled = true;
    };
  }, []);

  const ipPattern = /^((25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(25[0-5]|2[0-4]\d|[01]?\d\d?)$/;

  const handleFormSubmit = async (data: SimulatorCreate | SimulatorUpdate) => {
    setIsLoading(true);
    try {
      // Ensure we send only the expected shape
      const payload: any = {
        ip_address: (data as any).ip_address,
        map: (data as any).map,
        template_id: (data as any).template_id,
      };
      await onSubmit(payload as SimulatorCreate | SimulatorUpdate);
      reset();
      onClose();
    } catch (err) {
      console.error('Simulator submit failed', err);
      throw err;
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
                label="Template"
                fullWidth
                select
                defaultValue=""
                {...register('template_id' as any, { required: 'Template is required' })}
                error={!!(errors as any)?.template_id}
                helperText={(errors as any)?.template_id?.message}
              >
                {isTemplatesLoading ? (
                  <MenuItem value=""><em>Loading...</em></MenuItem>
                ) : (
                  templates.length ? templates.map((t) => (
                    <MenuItem key={t._id} value={t._id}>{t.name}</MenuItem>
                  )) : <MenuItem value=""><em>No templates</em></MenuItem>
                )}
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
