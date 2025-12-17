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
  IconButton,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import { useForm } from 'react-hook-form';
import { Simulator, SimulatorCreate, SimulatorUpdate } from '../../types/simulator.types';
import apiClient from '../../api/client';

interface SimulatorFormDialogProps {
  open: boolean;
  simulator: Simulator | null;
  onClose: () => void;
  onSubmit: (data: SimulatorCreate | SimulatorUpdate) => Promise<void>;
  // Optional list of existing simulators to extract unique map names from
  simulators?: Simulator[];
}

export const SimulatorFormDialog: React.FC<SimulatorFormDialogProps> = ({ open, simulator, onClose, onSubmit, simulators }) => {
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
  const [maps, setMaps] = useState<string[]>([]);
  const [addMapOpen, setAddMapOpen] = useState(false);
  const [newMapName, setNewMapName] = useState('');

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

  // derive unique maps from provided simulators prop when available
  useEffect(() => {
    if (simulators && simulators.length > 0) {
      const uniq = Array.from(new Set(simulators.map((s) => (s.map || '').trim()).filter(Boolean)));
      if (uniq.length > 0) setMaps((prev) => Array.from(new Set([...uniq, ...prev])));
    }
  }, [simulators]);

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

  const handleOpenAddMap = () => {
    setNewMapName('');
    setAddMapOpen(true);
  };
  const handleCloseAddMap = () => setAddMapOpen(false);
  const handleSubmitNewMap = () => {
    const name = (newMapName || '').trim();
    if (!name) {
      // minimal feedback for now
      console.warn('Map name is empty');
      return;
    }
    // Add to local maps list if not exists and select it
    setMaps((prev) => (prev.includes(name) ? prev : [name, ...prev]));
    setValue('map' as keyof (SimulatorCreate & SimulatorUpdate), name as any);
    console.log('New map submitted:', name); // placeholder for user implementation
    handleCloseAddMap();
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth PaperProps={{ sx: { margin: '32px' } }}>
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
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <TextField
                  label="Map"
                  fullWidth
                  select
                  defaultValue=""
                  {...register('map' as any, { required: 'Map is required' })}
                  error={!!(errors as any)?.map}
                  helperText={(errors as any)?.map?.message}
                  sx={{ flex: 1 }}
                >
                  {maps.map((m) => (
                    <MenuItem key={m} value={m}>{m}</MenuItem>
                  ))}
                </TextField>

                <IconButton size="small" onClick={handleOpenAddMap} aria-label="Add map">
                  <AddIcon />
                </IconButton>
              </Box>

              {/* Add Map Dialog */}
              <Dialog open={addMapOpen} onClose={handleCloseAddMap} maxWidth="xs" fullWidth>
                <DialogTitle>Add new map</DialogTitle>
                <DialogContent>
                  <TextField
                    autoFocus
                    margin="dense"
                    label="Map name"
                    fullWidth
                    value={newMapName}
                    onChange={(e) => setNewMapName(e.target.value)}
                  />
                </DialogContent>
                <DialogActions>
                  <Button onClick={handleCloseAddMap}>Cancel</Button>
                  <Button onClick={handleSubmitNewMap} variant="contained">Add</Button>
                </DialogActions>
              </Dialog>
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
