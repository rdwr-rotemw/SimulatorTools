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
  Snackbar,
  Alert,
  Tooltip,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import { HelpOutline } from '@mui/icons-material';
import { useForm } from 'react-hook-form';
import { Simulator, SimulatorCreate, SimulatorUpdate } from '../../types/simulator.types';
import { DeviceTemplate, DeviceTemplateCreate, DeviceTemplateUpdate } from '../../types/template.types';
import apiClient from '../../api/client';
import TemplateDialog from './TemplateDialog';

interface SimulatorFormDialogProps {
  open: boolean;
  simulator: Simulator | null;
  onClose: () => void;
  onSubmit: (data: SimulatorCreate | SimulatorUpdate) => Promise<void>;
  // Optional list of existing simulators to extract unique map names from
  simulators?: Simulator[];
}

export const SimulatorFormDialog: React.FC<SimulatorFormDialogProps> = ({ open, simulator, onClose, onSubmit, simulators }) => {
  const { register, handleSubmit, formState, reset, setValue, watch } = useForm<SimulatorCreate | SimulatorUpdate>({
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
  const [maps, setMaps] = useState<Array<{ name: string; status: string }>>([]);
  const [templateDialogOpen, setTemplateDialogOpen] = useState(false);
  const [selectedTemplateForEdit, setSelectedTemplateForEdit] = useState<DeviceTemplate | null>(null);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [templateToDelete, setTemplateToDelete] = useState<{ _id: string; name: string } | null>(null);
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({
    open: false,
    message: '',
    severity: 'success'
  });

  const isEditMode = !!simulator;

  // Watch template_id to reactively enable/disable Edit and Delete buttons
  const currentTemplateId = watch('template_id' as any);

  // Validate that the selected template actually exists in the list
  const isValidTemplateSelected = currentTemplateId && templates.some(t => t._id === currentTemplateId);

  // Watch all form fields to enable/disable Create button
  const currentIpAddress = watch('ip_address' as any);
  const currentMap = watch('map' as any);

  // Check if all required fields are filled (for create mode and edit mode)
  const isFormValid = isEditMode
    ? currentMap && isValidTemplateSelected  // Edit mode: map and template required
    : currentIpAddress && currentMap && isValidTemplateSelected;  // Create mode: ip, map, template required

  // Reset form when dialog opens/closes
  useEffect(() => {
    if (open) {
      // Dialog opened
      if (simulator) {
        // Edit mode: populate form values
        setValue('ip_address' as keyof (SimulatorCreate & SimulatorUpdate), simulator.ip_address as any);
        setValue('map' as keyof (SimulatorCreate & SimulatorUpdate), (simulator.map || '') as any);
        if ((simulator as any).template_id) {
          setValue('template_id' as keyof (SimulatorCreate & SimulatorUpdate), (simulator as any).template_id as any);
        }
      } else {
        // Create mode: reset form completely
        reset({
          ip_address: '',
          map: '',
          template_id: '',
        });
      }
    } else {
      // Dialog closed: reset form to clear any state
      reset({
        ip_address: '',
        map: '',
        template_id: '',
      });
    }
  }, [open, simulator, setValue, reset]);

  // Load all maps from API when dialog opens (both running and stopped)
  useEffect(() => {
    if (!open) return; // Only load when dialog is open

    let cancelled = false;
    const loadMaps = async () => {
      try {
        const resp = await apiClient.get('/maps');
        // Expect an array of {name, status}
        const data = resp.data as Array<{ name: string; status: string }>;
        if (!cancelled) {
          setMaps(data);
        }
      } catch (err) {
        console.error('Failed to load maps', err);
        if (!cancelled) setMaps([]);
      }
    };

    loadMaps();
    return () => {
      cancelled = true;
    };
  }, [open]); // Runs whenever dialog opens

  // Fetch templates when dialog opens
  useEffect(() => {
    if (!open) return; // Only load when dialog is open

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
  }, [open]); // Runs whenever dialog opens

  const handleFormSubmit = async (data: SimulatorCreate | SimulatorUpdate) => {
    setIsLoading(true);
    try {
      // Ensure we send only the expected shape
      const payload: any = {};
      if (isEditMode) {
        // Edit mode: only map and template_id are editable
        if ((data as any).map !== undefined) payload.map = (data as any).map;
        if ((data as any).template_id !== undefined) payload.template_id = (data as any).template_id;
      } else {
        // Create mode: required fields
        payload.ip_address = (data as any).ip_address;
        payload.map = (data as any).map;
        payload.template_id = (data as any).template_id;
      }
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

  const loadTemplates = async () => {
    setIsTemplatesLoading(true);
    try {
      const resp = await apiClient.get('/device-templates');
      const data = resp.data as Array<any>;
      setTemplates(data.map((t) => ({ _id: t._id, name: t.name })));
    } catch (err) {
      console.error('Failed to load device templates', err);
      setTemplates([]);
    } finally {
      setIsTemplatesLoading(false);
    }
  };

  const handleCreateTemplate = () => {
    setSelectedTemplateForEdit(null);
    setTemplateDialogOpen(true);
  };

  const handleEditTemplate = async () => {
    if (!currentTemplateId) {
      setSnackbar({ open: true, message: 'No template selected to edit', severity: 'error' });
      return;
    }

    try {
      const resp = await apiClient.get(`/device-templates/${currentTemplateId}`);

      // Validate response has expected structure
      if (!resp.data || typeof resp.data !== 'object' || !resp.data._id) {
        throw new Error('Invalid template data received');
      }

      setSelectedTemplateForEdit(resp.data as DeviceTemplate);
      setTemplateDialogOpen(true);
    } catch (err: any) {
      console.error('Failed to load template for editing', err);
      const errorMsg = err?.response?.data?.detail || err?.message || 'Failed to load template';
      setSnackbar({ open: true, message: errorMsg, severity: 'error' });
    }
  };

  const handleDeleteTemplate = () => {
    if (!currentTemplateId) {
      setSnackbar({ open: true, message: 'No template selected to delete', severity: 'error' });
      return;
    }

    // Find the template to show name in confirmation
    const template = templates.find(t => t._id === currentTemplateId);
    if (template) {
      setTemplateToDelete(template);
      setDeleteConfirmOpen(true);
    }
  };

  const handleDeleteCancel = () => {
    setDeleteConfirmOpen(false);
    setTemplateToDelete(null);
  };

  const handleDeleteConfirm = async () => {
    if (!templateToDelete) return;

    setDeleteLoading(true);
    try {
      await apiClient.delete(`/device-templates/${templateToDelete._id}`);

      console.log('Template deleted successfully:', templateToDelete.name);

      // Close confirmation dialog
      setDeleteConfirmOpen(false);

      // Clear the selected template in the form
      // This will trigger the Edit/Delete buttons to become disabled
      setValue('template_id' as any, '');

      // Refresh template list to remove deleted template from dropdown
      await loadTemplates();

      // Show success message with helpful hint
      setSnackbar({
        open: true,
        message: `Template "${templateToDelete.name}" deleted. Please select another template.`,
        severity: 'success'
      });

      setTemplateToDelete(null);
    } catch (err: any) {
      console.error('Template delete failed', err);

      // Extract meaningful error message
      let errorMsg = 'Failed to delete template';
      if (err?.response?.status === 422 && err?.response?.data?.detail) {
        const details = err.response.data.detail;
        if (Array.isArray(details) && details.length > 0) {
          errorMsg = `${details[0].loc[1]}: ${details[0].msg}`;
        } else if (typeof details === 'string') {
          errorMsg = details;
        }
      } else if (err?.message) {
        errorMsg = err.message;
      }

      setSnackbar({ open: true, message: errorMsg, severity: 'error' });
    } finally {
      setDeleteLoading(false);
    }
  };

  const handleTemplateDialogClose = () => {
    setTemplateDialogOpen(false);
    setSelectedTemplateForEdit(null);
  };

  const handleTemplateSubmit = async (data: DeviceTemplateCreate | DeviceTemplateUpdate) => {
    try {
      if (selectedTemplateForEdit) {
        // Update existing template
        await apiClient.put(`/device-templates/${selectedTemplateForEdit._id}`, data);
        setSnackbar({ open: true, message: 'Template updated successfully', severity: 'success' });
        // Refresh template list
        await loadTemplates();
      } else {
        // Create new template
        const resp = await apiClient.post('/device-templates', data);
        const newTemplateId = resp.data._id;
        setSnackbar({ open: true, message: 'Template created successfully', severity: 'success' });

        // Refresh templates list first to include the new template
        await loadTemplates();

        // Then select the newly created template in the dropdown
        setValue('template_id' as keyof (SimulatorCreate & SimulatorUpdate), newTemplateId as any);
      }

      handleTemplateDialogClose();
    } catch (err: any) {
      console.error('Template operation failed', err);
      setSnackbar({
        open: true,
        message: err?.response?.data?.detail || 'Template operation failed',
        severity: 'error'
      });
      throw err;
    }
  };

  const handleSnackbarClose = () => {
    setSnackbar((prev) => ({ ...prev, open: false }));
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth PaperProps={{ sx: { margin: '32px' } }}>
      <DialogTitle>{isEditMode ? 'Edit Simulator' : 'Create Simulator'}</DialogTitle>
      <DialogContent sx={{ paddingTop: '24px !important', paddingBottom: '24px' }}>
        <form id="simulator-form" onSubmit={handleSubmit(handleFormSubmit)}>
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 0.5 }}>
              <TextField
                label="IP Address"
                fullWidth
                disabled={isEditMode}
                placeholder="Single IP or Range (e.g., 192.168.1.1-192.168.1.25)"
                {...register('ip_address' as any, {
                  required: !isEditMode ? 'IP Address is required' : false,
                  validate: (value) => {
                    if (isEditMode) return true; // Skip validation in edit mode

                    const trimmedValue = value?.trim();
                    if (!trimmedValue) return 'IP Address is required';

                    // IPv4 single: 192.168.1.1
                    const ipv4Single = /^(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)){3}$/;

                    // IPv4 range: 192.168.1.1-192.168.1.25 (allows spaces around dash)
                    const ipv4Range = /^(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)){3}\s*-\s*(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)){3}$/;

                    if (ipv4Single.test(trimmedValue) || ipv4Range.test(trimmedValue)) {
                      return true;
                    }

                    return 'Enter a valid IP address or range (e.g., 192.168.1.1 or 192.168.1.1-192.168.1.25)';
                  },
                })}
                error={!!(errors as any)?.ip_address}
                helperText={(errors as any)?.ip_address?.message}
                sx={{ flex: 1 }}
              />
              {!isEditMode && (
                <Tooltip
                  title={
                    <Box sx={{ whiteSpace: 'pre-line', fontSize: '12px', p: 0.5 }}>
                      {'Supported formats:\n\n• Single IP: 192.168.1.1\n• IP Range: 192.168.1.1-192.168.1.25\n\nFor ranges:\nSimulators will be created with IPs incrementing within the range.\nExample: 192.168.1.1, 192.168.1.2, 192.168.1.3, ...'}
                    </Box>
                  }
                  placement="right"
                  arrow
                >
                  <HelpOutline
                    sx={{
                      fontSize: 18,
                      color: 'text.secondary',
                      cursor: 'help',
                      flexShrink: 0,
                      mt: 2
                    }}
                  />
                </Tooltip>
              )}
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
                sx={{ flex: 1 }}
              >
                {maps.map((m) => (
                  <MenuItem key={m.name} value={m.name}>
                    {m.name} {m.status === 'running' ? '(Running)' : '(Stopped)'}
                  </MenuItem>
                ))}
              </TextField>
            </Box>

            <Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <TextField
                  label="Template"
                  fullWidth
                  select
                  value={currentTemplateId || ''}
                  onChange={(e) => setValue('template_id' as any, e.target.value)}
                  error={!!(errors as any)?.template_id}
                  helperText={(errors as any)?.template_id?.message}
                  sx={{ flex: 1 }}
                >
                  {isTemplatesLoading ? (
                    <MenuItem value=""><em>Loading...</em></MenuItem>
                  ) : (
                    templates.length ? templates.map((t) => (
                      <MenuItem key={t._id} value={t._id}>{t.name}</MenuItem>
                    )) : <MenuItem value=""><em>No templates</em></MenuItem>
                  )}
                </TextField>

                <IconButton
                  size="small"
                  onClick={handleCreateTemplate}
                  aria-label="Create new template"
                  title="Create new template"
                >
                  <AddIcon />
                </IconButton>

                <IconButton
                  size="small"
                  onClick={handleEditTemplate}
                  aria-label="Edit selected template"
                  title="Edit selected template"
                  disabled={!isValidTemplateSelected}
                >
                  <EditIcon />
                </IconButton>

                <IconButton
                  size="small"
                  onClick={handleDeleteTemplate}
                  aria-label="Delete selected template"
                  title="Delete selected template"
                  disabled={!isValidTemplateSelected}
                  sx={{ color: 'error.main' }}
                >
                  <DeleteIcon />
                </IconButton>
              </Box>
            </Box>


          </Box>

          {/* Map Start Warning */}
          {!isEditMode && currentMap && maps.find(m => m.name === currentMap)?.status !== 'running' && (
            <Alert severity="info" sx={{ marginTop: 2 }}>
              <Typography variant="body2">
                <strong>Note:</strong> Creating a device requires the map to be running.
                Map "{currentMap}" will be automatically started when you create the simulator.
              </Typography>
            </Alert>
          )}
        </form>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={isLoading}>Cancel</Button>
        <Button
          type="submit"
          form="simulator-form"
          variant="contained"
          disabled={isLoading || !isFormValid}
        >
          {isLoading ? <CircularProgress size={20} /> : (isEditMode ? 'Save' : 'Create')}
        </Button>
      </DialogActions>

      {/* Template Dialog */}
      <TemplateDialog
        open={templateDialogOpen}
        template={selectedTemplateForEdit}
        onClose={handleTemplateDialogClose}
        onSubmit={handleTemplateSubmit}
      />

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={deleteConfirmOpen}
        onClose={handleDeleteCancel}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>Delete Template</DialogTitle>
        <DialogContent sx={{ paddingTop: '20px !important' }}>
          <Box>
            Are you sure you want to delete the template <strong>"{templateToDelete?.name}"</strong>?
          </Box>
          <Box sx={{ mt: 1, color: 'text.secondary', fontSize: '0.875rem' }}>
            This action cannot be undone.
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleDeleteCancel} disabled={deleteLoading}>
            Cancel
          </Button>
          <Button
            onClick={handleDeleteConfirm}
            color="error"
            variant="contained"
            disabled={deleteLoading}
          >
            {deleteLoading ? <CircularProgress size={20} /> : 'Delete'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Snackbar for feedback */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={handleSnackbarClose}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
      >
        <Alert onClose={handleSnackbarClose} severity={snackbar.severity} sx={{ width: '100%' }}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Dialog>
  );
};

export default SimulatorFormDialog;
