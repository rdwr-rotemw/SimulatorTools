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
  Tooltip,
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
  Fullscreen as FullscreenIcon,
  FullscreenExit as FullscreenExitIcon,
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
  const [isFullscreen, setIsFullscreen] = useState(false);

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
      // Clean the data structure for backend compatibility for ALL endpoints
      const cleanedEndpoints = endpoints.map((endpoint) => ({
        ...endpoint,
        data_structure: cleanStructureForBackend(endpoint.data_structure),
      }));

      await createTemplate(currentCC!, {
        name,
        description,
        endpoints: cleanedEndpoints,
      });

      setStatus({
        type: 'success',
        message: `Template "${name}" saved successfully with ${endpoints.length} endpoint(s)`,
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
  /**
   * Restore data structure from backend format to UI format.
   * Transforms backend format (arrays with 'repeat' and 'item' template)
   * to UI format (arrays with 'value' field containing configured items).
   */
  const restoreStructureFromBackend = (structure: Record<string, FieldValue>): Record<string, FieldValue> => {
    const restored: Record<string, FieldValue> = {};

    Object.keys(structure).forEach((key) => {
      const field = { ...structure[key] };

      // Recursively restore nested object properties FIRST
      if (field.type === FieldType.OBJECT && field.properties) {
        field.properties = restoreStructureFromBackend(field.properties);
      }

      // Recursively restore array item properties FIRST (before generating items)
      if (field.type === FieldType.ARRAY && field.item) {
        if (field.item.type === FieldType.OBJECT && field.item.properties) {
          field.item = {
            ...field.item,
            properties: restoreStructureFromBackend(field.item.properties),
          };
        }
      }

      // Handle ARRAY type with repeat count - generate items for UI
      if (field.type === FieldType.ARRAY && field.repeat && field.item) {
        const items: any[] = [];

        // Generate 'repeat' number of items based on the item template
        for (let i = 0; i < field.repeat; i++) {
          if (field.item.type === FieldType.OBJECT && field.item.properties) {
            const item: any = {};

            Object.keys(field.item.properties).forEach((propKey) => {
              const propField = field.item!.properties![propKey];

              // Extract the configured value from the template
              if (propField.type === FieldType.ARRAY && Array.isArray(propField.value)) {
                // Nested array already restored - copy its value array
                item[propKey] = propField.value;
              } else if (propField.value !== undefined && propField.value !== null && propField.value !== '') {
                // Has a configured value
                item[propKey] = propField.value;
              } else if (propField.mode === 'fixed' && propField.value !== undefined) {
                item[propKey] = propField.value;
              } else if (propField.type === FieldType.TIMESTAMP && propField.offset !== undefined) {
                item[propKey] = { offset: propField.offset };
              } else if (propField.mode === 'random' || propField.type === 'random_ipv4' || propField.type === 'random_fqdn') {
                // Keep random fields as-is (for UI to handle)
                item[propKey] = propField;
              } else if (propField.options && propField.options.length > 0) {
                // Enum field - use value or first option
                item[propKey] = propField.value || propField.options[0];
              } else {
                // Default empty value
                item[propKey] = '';
              }
            });

            items.push(item);
          }
        }

        // Set the value array with generated items
        // TypeScript: value field is used for arrays in UI format, though type definition doesn't reflect this
        (field as any).value = items;
      }

      restored[key] = field;
    });

    return restored;
  };

  const handleLoadTemplateConfirm = (template: PollingTemplate) => {
    // Restore ALL endpoints' data structures from backend format to UI format
    const restoredEndpoints = template.endpoints.map((endpoint) => ({
      ...endpoint,
      data_structure: restoreStructureFromBackend(endpoint.data_structure),
    }));

    setEndpoints(restoredEndpoints);
    setActiveEndpointIndex(0);
    // Expand all loaded endpoints
    setExpandedEndpoints(restoredEndpoints.map((_, index) => index));

    setStatus({
      type: 'success',
      message: `Template "${template.name}" loaded successfully with ${restoredEndpoints.length} endpoint(s)`,
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
  /**
   * Internal helper to save XMF with optional overwrite
   */
  const saveXmfInternal = async (overwrite: boolean = false) => {
    setLoading(true);
    setStatus({ type: 'info', message: 'Saving XMF file...' });

    try {
      // Clean up structure for ALL endpoints for backend compatibility
      const cleanedEndpoints = endpoints.map((endpoint) => ({
        ...endpoint,
        data_structure: cleanStructureForBackend(endpoint.data_structure),
      }));

      const payload: PollingPayload = {
        endpoints: cleanedEndpoints,  // Send all configured endpoints
        xmf_filename: getXmfFilename(),
        overwrite,
      };

      // Save XMF to Sapro filesystem (no simulator parameter needed)
      await saveXmfToSimulator(currentCC!, payload);

      setStatus({
        type: 'success',
        message: `XMF file "${getXmfFilename()}" saved successfully to Sapro`,
      });
    } catch (error: any) {
      // Check if file exists (409 Conflict)
      if (error.response?.status === 409 && error.response?.data?.detail?.startsWith('FILE_EXISTS:')) {
        setLoading(false);
        const confirmed = window.confirm(
          `File "${getXmfFilename()}" already exists. Do you want to overwrite it?`
        );
        if (confirmed) {
          // Retry with overwrite=true
          await saveXmfInternal(true);
        } else {
          setStatus({ type: 'info', message: 'Save cancelled by user' });
        }
        return;
      }

      setStatus({
        type: 'error',
        message: `Failed to save XMF: ${error.message || error}`,
      });
    } finally {
      setLoading(false);
    }
  };

  /**
   * Save XMF file to Sapro filesystem (does NOT load to simulator)
   * Only validates filename and endpoint, not simulator selection
   */
  const handleSaveToXmf = async () => {
    // Validate only filename and endpoints (not simulators)
    if (!xmfFilename || !xmfFilename.trim()) {
      setStatus({ type: 'error', message: 'XMF filename is required' });
      return;
    }
    if (endpoints.length === 0) {
      setStatus({ type: 'error', message: 'Please add at least one endpoint configuration' });
      return;
    }

    // Validate that all endpoints have data_key configured
    const unconfiguredEndpoints = endpoints
      .map((ep, idx) => ({ ep, idx }))
      .filter(({ ep }) => !ep.data_key);

    if (unconfiguredEndpoints.length > 0) {
      const indices = unconfiguredEndpoints.map(({ idx }) => idx + 1).join(', ');
      setStatus({
        type: 'error',
        message: `Please configure the endpoint name for endpoint(s): ${indices}`
      });
      return;
    }

    await saveXmfInternal(false);
  };

  /**
   * Internal helper to set polling config with optional overwrite
   */
  const setOnSimulatorInternal = async (overwrite: boolean = false) => {
    setLoading(true);
    setStatus({
      type: 'info',
      message: 'Setting polling configuration on simulator(s)...',
    });

    try {
      // Clean up structure for ALL endpoints for backend compatibility
      const cleanedEndpoints = endpoints.map((endpoint) => ({
        ...endpoint,
        data_structure: cleanStructureForBackend(endpoint.data_structure),
      }));

      // Build map dict for all simulators (matches SNMP pattern)
      const mapDict: Record<string, string> = {};
      for (const simulatorIp of selectedSimulators) {
        const saproSim = saproSimulators.find((sim) => sim.ip_address === simulatorIp);
        if (!saproSim || !saproSim.map) {
          setStatus({
            type: 'error',
            message: `No map found for simulator ${simulatorIp}`,
          });
          return;
        }
        mapDict[simulatorIp] = saproSim.map;
      }

      // Call API once with comma-separated simulator IPs (same pattern as SNMP)
      const simulatorIpsString = selectedSimulators.join(',');
      const payload: PollingPayload = {
        endpoints: cleanedEndpoints,
        xmf_filename: getXmfFilename(),
        map: mapDict,  // Dict mapping all simulator IPs to their maps
        overwrite,
      };

      await setPollingConfig(currentCC!, simulatorIpsString, payload);

      setStatus({
        type: 'success',
        message: `Polling configuration set successfully on ${selectedSimulators.length} simulator(s)`,
      });
    } catch (error: any) {
      // Check if file exists (409 Conflict)
      if (error.response?.status === 409 && error.response?.data?.detail?.startsWith('FILE_EXISTS:')) {
        setLoading(false);
        const confirmed = window.confirm(
          `File "${getXmfFilename()}" already exists. Do you want to overwrite it?`
        );
        if (confirmed) {
          // Retry with overwrite=true
          await setOnSimulatorInternal(true);
        } else {
          setStatus({ type: 'info', message: 'Operation cancelled by user' });
        }
        return;
      }

      setStatus({
        type: 'error',
        message: `Failed to set configuration: ${error.message || error}`,
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

    await setOnSimulatorInternal(false);
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
      <Box sx={{
          ...(isFullscreen ? {
            position: 'fixed',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            zIndex: 1200,
            bgcolor: 'background.paper',
          } : {
            height: 'calc(100vh - 64px)',
          }),
          display: 'flex',
          flexDirection: 'column',
        }}>
        {/* FIXED HEADER — hidden in fullscreen mode */}
        {!isFullscreen && <Box sx={{ padding: 3, borderBottom: '1px solid #E0E0E0' }}>
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
        </Box>}

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

        {/* Endpoint list toolbar with fullscreen toggle */}
        <Box sx={{ display: 'flex', justifyContent: 'flex-end', px: 2, pt: 1 }}>
          <Tooltip title={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}>
            <IconButton size="small" onClick={() => setIsFullscreen(f => !f)}>
              {isFullscreen ? <FullscreenExitIcon/> : <FullscreenIcon/>}
            </IconButton>
          </Tooltip>
        </Box>

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
