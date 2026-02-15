/**
 * Polling Configuration Page
 *
 * Complete polling endpoint configuration builder.
 * Consolidated single-file implementation matching SNMPPage.tsx pattern.
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Button,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Paper,
  Alert,
  Chip,
  CircularProgress,
  Checkbox,
  ListItemText,
  IconButton,
  Collapse,
  Typography,
} from '@mui/material';
import {
  Add as AddIcon,
  ExpandMore as ExpandIcon,
  ExpandLess as CollapseIcon,
  Save as SaveIcon,
  Download as DownloadIcon,
  Upload as UploadIcon,
  FolderOpen as LoadIcon,
  Input as ImportIcon,
  CloudUpload as SaveXmfIcon,
  Router as SetSimulatorIcon,
  Delete as DeleteIcon,
  UnfoldMore as UnfoldMoreIcon,
  UnfoldLess as UnfoldLessIcon,
} from '@mui/icons-material';

import Layout from '../components/common/Layout';
import useCCStore from '../store/ccStore';
import { EndpointConfig, PollingPayload, PollingTemplate, FieldType, FieldValue } from '../types/polling';
import {
  saveXmfToSimulator,
  setPollingConfig,
  createTemplate,
} from '../api/services/polling.service';
import { EndpointConfigPanel } from '../components/Reporter/Polling/EndpointConfigPanel';
import { SaveTemplateDialog } from '../components/Reporter/Polling/SaveTemplateDialog';
import { LoadTemplateDialog } from '../components/Reporter/Polling/LoadTemplateDialog';

export const PollingPage: React.FC = () => {
  const navigate = useNavigate();
  const currentCC = useCCStore((state) => state.currentCC);
  const devices = useCCStore((state) => state.devices);
  const saproSimulators = useCCStore((state) => state.saproSimulators);

  // Filter devices: only show those that exist in Sapro
  const saproIPs = new Set(saproSimulators.map((sim) => sim.ip_address));
  const devicesList = devices.filter((device) => saproIPs.has(device.management_ip));

  // Authentication check
  useEffect(() => {
    if (!currentCC) {
      navigate('/cc/login');
    }
  }, [currentCC, navigate]);

  // State management
  const [endpoints, setEndpoints] = useState<EndpointConfig[]>([]);
  const [selectedSimulators, setSelectedSimulators] = useState<string[]>([]);
  const [xmfFilename, setXmfFilename] = useState<string>('');
  const [activeEndpointIndex, setActiveEndpointIndex] = useState<number>(0);
  const [expandAll, setExpandAll] = useState<boolean>(true);
  const [expandedEndpoints, setExpandedEndpoints] = useState<number[]>([0]);

  // Status/feedback state
  const [status, setStatus] = useState<{
    type: 'success' | 'error' | 'info' | 'warning' | null;
    message: string;
  }>({ type: null, message: '' });
  const [loading, setLoading] = useState<boolean>(false);

  // Template dialog state
  const [saveTemplateDialogOpen, setSaveTemplateDialogOpen] = useState(false);
  const [loadTemplateDialogOpen, setLoadTemplateDialogOpen] = useState(false);

  /**
   * Validate form inputs before operations
   */
  const validateInputs = (): string | null => {
    if (!xmfFilename || !xmfFilename.trim()) {
      return 'XMF filename is required';
    }
    if (selectedSimulators.length === 0) {
      return 'Please select at least one simulator';
    }
    if (endpoints.length === 0) {
      return 'Please add at least one endpoint configuration';
    }
    if (!endpoints[activeEndpointIndex]?.data_key) {
      return 'Please configure the data key for the endpoint';
    }
    return null;
  };

  /**
   * Get XMF filename with .xmf extension (adds extension if missing)
   */
  const getXmfFilename = (): string => {
    const trimmed = xmfFilename.trim();
    return trimmed.endsWith('.xmf') ? trimmed : `${trimmed}.xmf`;
  };

  /**
   * Recursively filter out empty arrays from data structure
   */
  const filterEmptyArrays = (structure: Record<string, FieldValue>): Record<string, FieldValue> => {
    const filtered: Record<string, FieldValue> = {};

    Object.keys(structure).forEach((key) => {
      const field = structure[key];

      // Skip arrays with repeat=0 (empty arrays)
      if (field.type === FieldType.ARRAY) {
        if (field.repeat === 0) {
          return; // Skip this field entirely
        }
        // If repeat_min exists and is 0, also skip
        if (field.repeat === undefined && field.repeat_min === 0 && field.repeat_max === 0) {
          return;
        }
      }

      // For objects, recursively filter nested properties
      if (field.type === FieldType.OBJECT && field.properties) {
        const filteredProps = filterEmptyArrays(field.properties);
        // Only include if there are non-empty properties
        if (Object.keys(filteredProps).length > 0) {
          filtered[key] = {
            ...field,
            properties: filteredProps,
          };
        }
        return;
      }

      // For arrays with object items, recursively filter item properties
      if (
        field.type === FieldType.ARRAY &&
        field.item?.type === FieldType.OBJECT &&
        field.item.properties
      ) {
        const filteredItemProps = filterEmptyArrays(field.item.properties);
        filtered[key] = {
          ...field,
          item: {
            ...field.item,
            properties: filteredItemProps,
          },
        };
        return;
      }

      // Include all other fields
      filtered[key] = field;
    });

    return filtered;
  };

  /**
   * Add a new empty endpoint configuration
   */
  const handleAddEndpoint = () => {
    const newEndpoint: EndpointConfig = {
      path: '',
      method: 'GET',
      data_key: '',
      polling_interval_seconds: 60,
      data_structure: {},
    };

    setEndpoints([...endpoints, newEndpoint]);
    setActiveEndpointIndex(endpoints.length);
    setExpandedEndpoints([...expandedEndpoints, endpoints.length]);
  };

  /**
   * Download current configuration as JSON file
   */
  const handleDownloadJson = () => {
    try {
      const config = {
        xmf_filename: xmfFilename,
        endpoints: endpoints,
      };

      const jsonString = JSON.stringify(config, null, 2);
      const blob = new Blob([jsonString], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = xmfFilename ? xmfFilename.replace('.xmf', '.json') : 'polling_config.json';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);

      setStatus({
        type: 'success',
        message: 'Configuration downloaded successfully',
      });
    } catch (error) {
      setStatus({
        type: 'error',
        message: `Failed to download configuration: ${error}`,
      });
    }
  };

  /**
   * Import configuration from JSON file
   */
  const handleImportJson = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';

    input.onchange = async (e: any) => {
      const file = e.target.files?.[0];
      if (!file) return;

      try {
        const text = await file.text();
        const config = JSON.parse(text);

        if (!config.endpoints || !Array.isArray(config.endpoints)) {
          throw new Error('Invalid JSON format: missing endpoints array');
        }

        setEndpoints(config.endpoints);
        if (config.xmf_filename) {
          setXmfFilename(config.xmf_filename);
        }
        setActiveEndpointIndex(0);
        setExpandedEndpoints(config.endpoints.map((_: any, i: number) => i));

        setStatus({
          type: 'success',
          message: `Configuration imported successfully from ${file.name}`,
        });
      } catch (error: any) {
        setStatus({
          type: 'error',
          message: `Failed to import JSON: ${error.message}`,
        });
      }
    };

    input.click();
  };

  /**
   * Save current configuration as a template
   */
  const handleSaveTemplate = () => {
    if (endpoints.length === 0) {
      setStatus({
        type: 'error',
        message: 'No endpoint configuration to save',
      });
      return;
    }

    if (!endpoints[0].data_key) {
      setStatus({
        type: 'error',
        message: 'Please configure the data key before saving template',
      });
      return;
    }

    setSaveTemplateDialogOpen(true);
  };

  /**
   * Handle template save confirmation
   */
  const handleSaveTemplateConfirm = async (name: string, description: string) => {
    try {
      await createTemplate(currentCC!, {
        name,
        description,
        endpoint: endpoints[0],
      });

      setStatus({
        type: 'success',
        message: `Template "${name}" saved successfully`,
      });
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || error.message || 'Failed to save template');
    }
  };

  /**
   * Open load template dialog
   */
  const handleLoadTemplate = () => {
    setLoadTemplateDialogOpen(true);
  };

  /**
   * Handle template load confirmation
   */
  const handleLoadTemplateConfirm = (template: PollingTemplate) => {
    setEndpoints([template.endpoint]);
    setActiveEndpointIndex(0);
    setExpandedEndpoints([0]);

    setStatus({
      type: 'success',
      message: `Template "${template.name}" loaded successfully`,
    });
  };

  /**
   * Import configuration from XMF file (placeholder for future)
   */
  const handleImportFromXmf = () => {
    setStatus({
      type: 'info',
      message:
        'Import from XMF feature will be implemented in a future update. This will allow you to load existing XMF files from the Sapro server.',
    });
  };

  /**
   * Clean up data structure for backend compatibility.
   * Transforms UI format (arrays with 'value' field containing configured items)
   * to backend format (arrays with 'repeat' and 'item' template).
   */
  const cleanStructureForBackend = (structure: Record<string, FieldValue>): Record<string, FieldValue> => {
    const cleaned: Record<string, FieldValue> = {};

    Object.keys(structure).forEach((key) => {
      const field = { ...structure[key] };

      // Handle ARRAY type with configured items in 'value'
      if (field.type === FieldType.ARRAY && Array.isArray(field.value)) {
        const configuredItems = field.value;

        // Set repeat to number of configured items
        field.repeat = configuredItems.length;

        // If we have configured items, update the item template with values from first item
        if (configuredItems.length > 0 && field.item?.type === FieldType.OBJECT && field.item.properties) {
          const firstItem = configuredItems[0];
          const updatedProperties: Record<string, FieldValue> = {};

          Object.keys(field.item.properties).forEach((propKey) => {
            const propTemplate = { ...field.item!.properties![propKey] };
            const configuredValue = firstItem[propKey];

            // Check if value is "empty" (empty string, 0, null, undefined)
            const isEmpty =
              configuredValue === undefined ||
              configuredValue === null ||
              configuredValue === '' ||
              configuredValue === 0;

            if (!isEmpty) {
              // Has a meaningful configured value - use it
              if (typeof configuredValue === 'object' && 'mode' in configuredValue) {
                // It's already in the right format (e.g., {mode: 'fixed', value: 'pol1'})
                updatedProperties[propKey] = { ...propTemplate, ...configuredValue };
              } else if (typeof configuredValue === 'object' && 'offset' in configuredValue) {
                // Timestamp with offset
                updatedProperties[propKey] = { ...propTemplate, offset: configuredValue.offset };
              } else {
                // Simple value - set mode to fixed
                updatedProperties[propKey] = { ...propTemplate, mode: 'fixed', value: configuredValue };
              }
            } else if (propTemplate.mode === 'random' || propTemplate.type === 'random_ipv4' || propTemplate.type === 'random_fqdn') {
              // Empty value but template is random - keep random mode
              updatedProperties[propKey] = propTemplate;
            } else {
              // Empty value and template is not random - keep as-is (will use default/empty)
              updatedProperties[propKey] = propTemplate;
            }
          });

          field.item = {
            ...field.item,
            properties: updatedProperties,
          };
        }

        // Remove the 'value' field (backend doesn't accept arrays in value)
        delete field.value;
      }

      // Recursively clean nested object properties
      if (field.type === FieldType.OBJECT && field.properties) {
        field.properties = cleanStructureForBackend(field.properties);
      }

      // Recursively clean array item properties
      if (field.type === FieldType.ARRAY && field.item?.type === FieldType.OBJECT && field.item.properties) {
        field.item.properties = cleanStructureForBackend(field.item.properties);
      }

      cleaned[key] = field;
    });

    return cleaned;
  };

  /**
   * Save XMF file to Sapro filesystem (does NOT load to simulator)
   * Only validates filename and endpoint, not simulator selection
   */
  const handleSaveToXmf = async () => {
    // Validate only filename and endpoint (not simulators)
    if (!xmfFilename || !xmfFilename.trim()) {
      setStatus({ type: 'error', message: 'XMF filename is required' });
      return;
    }
    if (endpoints.length === 0) {
      setStatus({ type: 'error', message: 'Please add at least one endpoint configuration' });
      return;
    }
    if (!endpoints[activeEndpointIndex]?.data_key) {
      setStatus({ type: 'error', message: 'Please configure the data key for the endpoint' });
      return;
    }

    setLoading(true);
    setStatus({ type: 'info', message: 'Saving XMF file...' });

    try {
      // Clean up structure for backend compatibility
      const cleanedEndpoint = {
        ...endpoints[activeEndpointIndex],
        data_structure: cleanStructureForBackend(endpoints[activeEndpointIndex].data_structure),
      };

      const payload: PollingPayload = {
        endpoint_config: cleanedEndpoint,
        xmf_filename: getXmfFilename(),
      };

      // Save once using currentCC as routing (no simulator selection needed)
      await saveXmfToSimulator(currentCC!, currentCC!, payload);

      setStatus({
        type: 'success',
        message: `XMF file "${getXmfFilename()}" saved successfully to Sapro`,
      });
    } catch (error: any) {
      setStatus({
        type: 'error',
        message: `Failed to save XMF: ${error.message || error}`,
      });
    } finally {
      setLoading(false);
    }
  };

  /**
   * Set polling configuration on simulator (saves XMF and loads to device)
   */
  const handleSetOnSimulator = async () => {
    const validationError = validateInputs();
    if (validationError) {
      setStatus({ type: 'error', message: validationError });
      return;
    }

    setLoading(true);
    setStatus({
      type: 'info',
      message: 'Setting polling configuration on simulator(s)...',
    });

    try {
      // Clean up structure for backend compatibility
      const cleanedEndpoint = {
        ...endpoints[activeEndpointIndex],
        data_structure: cleanStructureForBackend(endpoints[activeEndpointIndex].data_structure),
      };

      const payload: PollingPayload = {
        endpoint_config: cleanedEndpoint,
        xmf_filename: getXmfFilename(),
      };

      const results = await Promise.allSettled(
        selectedSimulators.map((simulatorIp) => setPollingConfig(currentCC!, simulatorIp, payload))
      );

      const successes = results.filter((r) => r.status === 'fulfilled').length;
      const failures = results.filter((r) => r.status === 'rejected').length;

      if (failures === 0) {
        setStatus({
          type: 'success',
          message: `Polling configuration set successfully on ${successes} simulator(s)`,
        });
      } else if (successes > 0) {
        setStatus({
          type: 'warning',
          message: `Configuration set on ${successes} simulator(s), failed for ${failures} simulator(s)`,
        });
      } else {
        setStatus({
          type: 'error',
          message: `Failed to set configuration on all simulators`,
        });
      }
    } catch (error: any) {
      setStatus({
        type: 'error',
        message: `Failed to set configuration: ${error.message || error}`,
      });
    } finally {
      setLoading(false);
    }
  };

  /**
   * Toggle specific endpoint expansion
   */
  const toggleEndpoint = (index: number) => {
    setExpandedEndpoints((prev) =>
      prev.includes(index) ? prev.filter((i) => i !== index) : [...prev, index]
    );
  };

  /**
   * Delete an endpoint
   */
  const deleteEndpoint = (index: number) => {
    const newEndpoints = endpoints.filter((_, i) => i !== index);
    setEndpoints(newEndpoints);
    if (activeEndpointIndex >= newEndpoints.length) {
      setActiveEndpointIndex(Math.max(0, newEndpoints.length - 1));
    }
    setExpandedEndpoints((prev) =>
      prev.filter((i) => i !== index).map((i) => (i > index ? i - 1 : i))
    );
  };

  /**
   * Update specific endpoint
   */
  const updateEndpoint = (index: number, updated: EndpointConfig) => {
    const newEndpoints = [...endpoints];
    newEndpoints[index] = updated;
    setEndpoints(newEndpoints);
  };

  return (
    <Layout>
      <Box sx={{ height: 'calc(100vh - 64px)', display: 'flex', flexDirection: 'column' }}>
        {/* FIXED HEADER */}
        <Box sx={{ padding: 3, borderBottom: '1px solid #E0E0E0' }}>
          <Typography variant="h4" sx={{ marginBottom: 1 }}>
            Polling Configuration
          </Typography>
          <Typography variant="body2" sx={{ color: '#666', marginBottom: 2 }}>
            Build and manage polling endpoint configurations for DefensePro simulators
          </Typography>

          {/* Target Simulators - Multi-select */}
          <FormControl fullWidth>
            <InputLabel id="target-simulator-label">Target Simulator</InputLabel>
            <Select
              labelId="target-simulator-label"
              multiple
              value={selectedSimulators}
              onChange={(e) => {
                const value = e.target.value;
                const newValue = typeof value === 'string' ? value.split(',') : value;
                if (newValue.includes('__SELECT_ALL__')) return;
                setSelectedSimulators(newValue);
              }}
              label="Target Simulator"
              renderValue={(selected) => (
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                  <Chip
                    label={`${(selected as string[]).length} simulator(s) selected`}
                    size="small"
                    sx={{ backgroundColor: 'primary.main', color: 'white' }}
                  />
                </Box>
              )}
            >
              {/* Select All Option */}
              <MenuItem
                value="__SELECT_ALL__"
                onClick={(e) => {
                  e.stopPropagation();
                  if (selectedSimulators.length === devicesList.length) {
                    setSelectedSimulators([]);
                  } else {
                    setSelectedSimulators(devicesList.map((d) => d.management_ip));
                  }
                }}
                sx={{ fontWeight: 'bold', borderBottom: '1px solid #e0e0e0' }}
              >
                <ListItemText
                  primary={
                    selectedSimulators.length === devicesList.length ? 'Deselect All' : 'Select All'
                  }
                />
              </MenuItem>

              {/* Simulator Options */}
              {devicesList.map((device) => (
                <MenuItem key={device.management_ip} value={device.management_ip}>
                  <Checkbox
                    checked={selectedSimulators.includes(device.management_ip)}
                    sx={{ marginRight: 1 }}
                  />
                  <ListItemText
                    primary={`${device.name || device.management_ip} (${device.management_ip})`}
                    secondary={device.map ? `Map: ${device.map}` : undefined}
                  />
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          {/* XMF Filename Input */}
          <TextField
            fullWidth
            label="XMF Filename *"
            value={xmfFilename}
            onChange={(e) => setXmfFilename(e.target.value)}
            placeholder="e.g., attack_data.xmf"
            required
            sx={{ marginTop: 2 }}
            helperText="User-defined XMF filename"
          />
        </Box>

        {/* Status Alert */}
        {status.type && (
          <Alert
            severity={status.type}
            sx={{ margin: 3, marginBottom: 0 }}
            onClose={() => setStatus({ type: null, message: '' })}
          >
            {status.message}
          </Alert>
        )}

        {/* SCROLLABLE CONTENT */}
        <Box sx={{ flex: 1, overflow: 'auto', padding: 3 }}>
          {endpoints.length === 0 ? (
            <Box sx={{ textAlign: 'center', padding: 4 }}>
              <Typography variant="body1" color="textSecondary" gutterBottom>
                No endpoint configurations yet.
              </Typography>
              <Button
                variant="contained"
                startIcon={<AddIcon />}
                onClick={handleAddEndpoint}
                sx={{ marginTop: 2 }}
              >
                Add Your First Endpoint
              </Button>
            </Box>
          ) : (
            endpoints.map((endpoint, index) => (
              <Paper key={index} sx={{ marginBottom: 2, padding: 2 }}>
                <Box
                  sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: 2,
                  }}
                >
                  <Typography variant="h6">{endpoint.data_key || `Endpoint ${index + 1}`}</Typography>
                  <Box>
                    <IconButton onClick={() => toggleEndpoint(index)}>
                      {expandedEndpoints.includes(index) ? <CollapseIcon /> : <ExpandIcon />}
                    </IconButton>
                    <IconButton onClick={() => deleteEndpoint(index)} color="error">
                      <DeleteIcon />
                    </IconButton>
                  </Box>
                </Box>

                <Collapse in={expandedEndpoints.includes(index)}>
                  <EndpointConfigPanel
                    endpoint={endpoint}
                    onChange={(updated) => updateEndpoint(index, updated)}
                    expanded={true}
                    ccIp={currentCC || 'localhost'}
                  />
                </Collapse>
              </Paper>
            ))
          )}
        </Box>

        {/* FIXED FOOTER */}
        <Box
          sx={{
            padding: 3,
            borderTop: '1px solid #E0E0E0',
            display: 'flex',
            gap: 2,
            flexWrap: 'wrap',
          }}
        >
          {/* Left side buttons */}
          <Button variant="outlined" startIcon={<AddIcon />} onClick={handleAddEndpoint}>
            Add Endpoint
          </Button>
          <Button
            variant="outlined"
            startIcon={expandAll ? <UnfoldLessIcon /> : <UnfoldMoreIcon />}
            onClick={() => {
              setExpandAll(!expandAll);
              if (!expandAll) {
                setExpandedEndpoints(endpoints.map((_, i) => i));
              } else {
                setExpandedEndpoints([]);
              }
            }}
          >
            {expandAll ? 'Collapse All' : 'Expand All'}
          </Button>
          <Button
            variant="outlined"
            startIcon={<SaveIcon />}
            onClick={handleSaveTemplate}
            disabled={loading || endpoints.length === 0}
          >
            Save Template
          </Button>
          <Button
            variant="outlined"
            startIcon={<DownloadIcon />}
            onClick={handleDownloadJson}
            disabled={loading || endpoints.length === 0}
          >
            Download JSON
          </Button>
          <Button variant="outlined" startIcon={<UploadIcon />} onClick={handleImportJson}>
            Import JSON
          </Button>
          <Button variant="outlined" startIcon={<LoadIcon />} onClick={handleLoadTemplate}>
            Load Template
          </Button>
          <Button variant="outlined" startIcon={<ImportIcon />} onClick={handleImportFromXmf}>
            Import from XMF
          </Button>

          <Box sx={{ flex: 1 }} />

          {/* Right side buttons */}
          <Button
            variant="contained"
            startIcon={<SaveXmfIcon />}
            onClick={handleSaveToXmf}
            disabled={loading || !xmfFilename || endpoints.length === 0}
          >
            Save to XMF
          </Button>
          <Button
            variant="contained"
            color="primary"
            startIcon={<SetSimulatorIcon />}
            onClick={handleSetOnSimulator}
            disabled={
              loading || !xmfFilename || selectedSimulators.length === 0 || endpoints.length === 0
            }
          >
            {loading ? <CircularProgress size={20} sx={{ mr: 1 }} /> : null}
            Set on Simulator
          </Button>
        </Box>

        {/* Template Dialogs */}
        <SaveTemplateDialog
          open={saveTemplateDialogOpen}
          endpoint={endpoints[activeEndpointIndex] || ({} as EndpointConfig)}
          onClose={() => setSaveTemplateDialogOpen(false)}
          onSave={handleSaveTemplateConfirm}
        />

        <LoadTemplateDialog
          open={loadTemplateDialogOpen}
          ccIp={currentCC!}
          onClose={() => setLoadTemplateDialogOpen(false)}
          onLoad={handleLoadTemplateConfirm}
        />
      </Box>
    </Layout>
  );
};
