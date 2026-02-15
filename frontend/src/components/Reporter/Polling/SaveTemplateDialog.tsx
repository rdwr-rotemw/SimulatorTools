/**
 * Save Template Dialog Component
 *
 * Dialog for saving current endpoint configuration as a reusable template.
 * Allows user to provide template name and optional description.
 */

import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Stack,
  Alert,
  CircularProgress,
} from '@mui/material';

import { EndpointConfig } from '../../../types/polling';

interface SaveTemplateDialogProps {
  open: boolean;
  endpoint: EndpointConfig;
  onClose: () => void;
  onSave: (name: string, description: string) => Promise<void>;
}

export const SaveTemplateDialog: React.FC<SaveTemplateDialogProps> = ({
  open,
  endpoint,
  onClose,
  onSave,
}) => {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /**
   * Handle template save
   */
  const handleSave = async () => {
    if (!name.trim()) {
      setError('Template name is required');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      await onSave(name.trim(), description.trim());
      // Reset form on success
      setName('');
      setDescription('');
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to save template');
    } finally {
      setLoading(false);
    }
  };

  /**
   * Handle dialog close
   */
  const handleClose = () => {
    if (!loading) {
      setName('');
      setDescription('');
      setError(null);
      onClose();
    }
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>Save Polling Template</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          {error && (
            <Alert severity="error" onClose={() => setError(null)}>
              {error}
            </Alert>
          )}

          <TextField
            autoFocus
            required
            fullWidth
            label="Template Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            disabled={loading}
            helperText="A descriptive name for this polling configuration"
          />

          <TextField
            fullWidth
            label="Description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            disabled={loading}
            multiline
            rows={3}
            helperText="Optional description of what this template does"
          />

          {endpoint.data_key && (
            <Alert severity="info">
              Saving configuration for: <strong>{endpoint.data_key}</strong>
            </Alert>
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} disabled={loading}>
          Cancel
        </Button>
        <Button
          onClick={handleSave}
          variant="contained"
          disabled={loading || !name.trim()}
          startIcon={loading ? <CircularProgress size={20} /> : null}
        >
          {loading ? 'Saving...' : 'Save'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};
