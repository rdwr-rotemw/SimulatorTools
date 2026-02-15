/**
 * Load Template Dialog Component
 *
 * Dialog for loading saved polling templates.
 * Lists all saved templates with options to load or delete them.
 */

import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  List,
  ListItem,
  ListItemText,
  IconButton,
  Alert,
  CircularProgress,
  Box,
  Typography,
  Divider,
} from '@mui/material';
import { Delete as DeleteIcon, CloudDownload as LoadIcon } from '@mui/icons-material';

import {
  listTemplates,
  getTemplate,
  deleteTemplate,
} from '../../../api/services/polling.service';
import { PollingTemplate, PollingTemplateSummary } from '../../../types/polling';

interface LoadTemplateDialogProps {
  open: boolean;
  ccIp: string;
  onClose: () => void;
  onLoad: (template: PollingTemplate) => void;
}

export const LoadTemplateDialog: React.FC<LoadTemplateDialogProps> = ({
  open,
  ccIp,
  onClose,
  onLoad,
}) => {
  const [templates, setTemplates] = useState<PollingTemplateSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  /**
   * Fetch templates from API
   */
  const fetchTemplates = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await listTemplates(ccIp);
      setTemplates(response.templates);
    } catch (err: any) {
      setError(err.message || 'Failed to load templates');
    } finally {
      setLoading(false);
    }
  };

  /**
   * Fetch templates when dialog opens
   */
  useEffect(() => {
    if (open) {
      fetchTemplates();
    }
  }, [open, ccIp]);

  /**
   * Handle loading a template
   */
  const handleLoad = async (templateId: string) => {
    try {
      const response = await getTemplate(ccIp, templateId);
      onLoad(response.template);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to load template');
    }
  };

  /**
   * Handle deleting a template
   */
  const handleDelete = async (templateId: string, templateName: string) => {
    if (!window.confirm(`Delete template "${templateName}"?`)) {
      return;
    }

    setDeletingId(templateId);
    setError(null);

    try {
      await deleteTemplate(ccIp, templateId);
      // Refresh list
      await fetchTemplates();
    } catch (err: any) {
      setError(err.message || 'Failed to delete template');
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>Load Polling Template</DialogTitle>
      <DialogContent>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress />
          </Box>
        ) : templates.length === 0 ? (
          <Box sx={{ textAlign: 'center', py: 4 }}>
            <Typography color="text.secondary">
              No templates saved yet. Create a configuration and save it as a template.
            </Typography>
          </Box>
        ) : (
          <List>
            {templates.map((template, index) => (
              <React.Fragment key={template._id}>
                {index > 0 && <Divider />}
                <ListItem
                  secondaryAction={
                    <Box>
                      <Button
                        variant="contained"
                        size="small"
                        startIcon={<LoadIcon />}
                        onClick={() => handleLoad(template._id)}
                        sx={{ mr: 1 }}
                      >
                        Load
                      </Button>
                      <IconButton
                        edge="end"
                        onClick={() => handleDelete(template._id, template.name)}
                        disabled={deletingId === template._id}
                        color="error"
                      >
                        {deletingId === template._id ? (
                          <CircularProgress size={24} />
                        ) : (
                          <DeleteIcon />
                        )}
                      </IconButton>
                    </Box>
                  }
                >
                  <ListItemText
                    primary={template.name}
                    secondary={
                      <>
                        {template.description && (
                          <Typography variant="body2" color="text.secondary">
                            {template.description}
                          </Typography>
                        )}
                        {template.created_at && (
                          <Typography variant="caption" color="text.secondary">
                            Created:{' '}
                            {new Date(template.created_at).toLocaleString()}
                          </Typography>
                        )}
                      </>
                    }
                  />
                </ListItem>
              </React.Fragment>
            ))}
          </List>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
};
