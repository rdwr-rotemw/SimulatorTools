/**
 * Endpoint Configuration Panel Component
 *
 * Displays endpoint settings (data key, intervals, path) and provides
 * a form for building the data structure.
 *
 * Fetches structure templates from backend and parses them into UI format.
 */

import React, { useEffect, useState, useCallback } from 'react';
import {
  Box,
  Paper,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Typography,
  Divider,
  Collapse,
  CircularProgress,
  Alert,
} from '@mui/material';

import {
  EndpointConfig,
  DATA_KEY_OPTIONS,
  FieldValue,
  FieldType,
} from '../../../types/polling';
import { PollingDataForm } from './PollingDataForm';
import { fetchStructureTemplate } from '../../../api/services/polling.service';
import { parseStructureTemplate } from '../../../utils/structureParser';

interface EndpointConfigPanelProps {
  endpoint: EndpointConfig;
  onChange: (updated: EndpointConfig) => void;
  expanded: boolean;
  ccIp?: string; // CyberController IP for API calls
}

export const EndpointConfigPanel: React.FC<EndpointConfigPanelProps> = ({
  endpoint,
  onChange,
  expanded,
  ccIp = 'localhost', // Default fallback
}) => {
  const [isLoadingStructure, setIsLoadingStructure] = useState(false);
  const [structureError, setStructureError] = useState<string | null>(null);

  /**
   * Initialize mode for all applicable fields (STRING non-enum and NUMBER)
   */
  const initializeFieldModes = useCallback((fieldValue: FieldValue): FieldValue => {
    const initialized = { ...fieldValue };

    // Set default mode='random' for applicable types
    if (
      (initialized.type === FieldType.STRING && !initialized.options) ||
      initialized.type === FieldType.NUMBER
    ) {
      initialized.mode = initialized.mode || 'random'; // Default to random if not set
    }

    // Recursively initialize nested fields
    if (initialized.properties) {
      initialized.properties = Object.keys(initialized.properties).reduce(
        (acc, key) => {
          acc[key] = initializeFieldModes(initialized.properties![key]);
          return acc;
        },
        {} as Record<string, FieldValue>
      );
    }

    if (initialized.item) {
      initialized.item = initializeFieldModes(initialized.item);
    }

    return initialized;
  }, []);

  /**
   * Fetch and parse structure when data_key changes
   * Use ref to track if we've already loaded this data_key to prevent infinite loops
   */
  const [loadedDataKey, setLoadedDataKey] = useState<string | null>(null);

  useEffect(() => {
    // Only load if data_key changed and we haven't loaded it yet
    if (!endpoint.data_key) {
      setLoadedDataKey(null);
      return;
    }

    // Prevent infinite retry loop - only load if data_key actually changed
    if (loadedDataKey === endpoint.data_key) {
      return;
    }

    // Check if data_structure already has configured data (from template load)
    // If it does, skip the fetch to avoid overwriting restored data
    const hasConfiguredData = Object.values(endpoint.data_structure || {}).some((field: any) => {
      // Check if it's an array with repeat > 0 (indicates configured items)
      if (field.type === 'array' && field.repeat && field.repeat > 0) {
        return true;
      }
      // Check if it's an object with nested configured arrays
      if (field.type === 'object' && field.properties) {
        return Object.values(field.properties).some((prop: any) =>
          prop.type === 'array' && prop.repeat && prop.repeat > 0
        );
      }
      return false;
    });

    if (hasConfiguredData) {
      // Mark as loaded to prevent future fetches
      setLoadedDataKey(endpoint.data_key);
      return;
    }

    const loadStructure = async () => {
      setIsLoadingStructure(true);
      setStructureError(null);

      try {
        // Fetch structure from backend
        const mongoStructure = await fetchStructureTemplate(ccIp, endpoint.data_key);

        // Extract main structure (could be nested)
        // MongoDB returns: {data_structure: {attack_data: {_type: "object", _properties: {...}}}}
        const dataStructure = mongoStructure.data_structure || mongoStructure;

        // Extract the actual structure object (unwrap the data_key wrapper)
        // If dataStructure has a key matching endpoint.data_key, use that value
        // Otherwise, use dataStructure directly
        let actualStructure = dataStructure;
        if (dataStructure[endpoint.data_key]) {
          actualStructure = dataStructure[endpoint.data_key];
        }

        // Parse into FieldValue format
        const parsedStructure = parseStructureTemplate(actualStructure);

        // Initialize mode for all fields (defaults to random for applicable types)
        const initializedStructure = initializeFieldModes(parsedStructure);

        // Get selected option for path
        const selectedOption = DATA_KEY_OPTIONS.find((opt) => opt.value === endpoint.data_key);

        // Update endpoint with parsed & initialized structure and auto-filled path
        // If parsed structure is an object with properties, use those properties directly
        // Otherwise, wrap it with the data_key
        const finalDataStructure = initializedStructure.properties || { [endpoint.data_key]: initializedStructure };

        onChange({
          ...endpoint,
          path: selectedOption?.endpoint || endpoint.path,
          data_structure: finalDataStructure,
        });

        // Mark this data_key as loaded to prevent retry
        setLoadedDataKey(endpoint.data_key);
      } catch (error: any) {
        console.error('=== Structure Loading Error ===');
        console.error('Error:', error);
        console.error('Error message:', error.message);
        console.error('Error stack:', error.stack);
        setStructureError(`Failed to load structure: ${error.message}`);

        // Still update path even if structure fails
        const selectedOption = DATA_KEY_OPTIONS.find((opt) => opt.value === endpoint.data_key);
        onChange({
          ...endpoint,
          path: selectedOption?.endpoint || endpoint.path,
          data_structure: {},
        });

        // Mark as loaded even on error to prevent infinite retry
        setLoadedDataKey(endpoint.data_key);
      } finally {
        setIsLoadingStructure(false);
      }
    };

    loadStructure();
  }, [endpoint.data_key, ccIp, loadedDataKey]);

  /**
   * Handle polling interval changes
   */
  const handleIntervalChange = (
    field: 'polling_interval_seconds',
    value: number
  ) => {
    onChange({
      ...endpoint,
      [field]: value,
    });
  };

  // Get selected data key option for description display
  const selectedDataKeyOption = DATA_KEY_OPTIONS.find(
    (opt) => opt.value === endpoint.data_key
  );

  return (
    <Box>
      <Collapse in={expanded}>
        {/* Endpoint Settings Section */}
        <Paper elevation={2} sx={{ p: 2, mb: 2 }}>
          <Typography variant="h6" gutterBottom>
            Endpoint Settings
          </Typography>
          <Divider sx={{ mb: 2 }} />

          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 2 }}>
            {/* Endpoint Name Selector */}
            <Box>
              <FormControl fullWidth required>
                <InputLabel>Endpoint Name</InputLabel>
                <Select
                  value={endpoint.data_key}
                  onChange={(e) => {
                    // Clear structure while loading
                    onChange({
                      ...endpoint,
                      data_key: e.target.value,
                      data_structure: {},
                    });
                  }}
                  label="Endpoint Name"
                >
                  <MenuItem value="">
                    <em>Select an endpoint...</em>
                  </MenuItem>
                  {DATA_KEY_OPTIONS.map((option) => (
                    <MenuItem key={option.value} value={option.value}>
                      {option.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              {selectedDataKeyOption && (
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ mt: 0.5, display: 'block' }}
                >
                  {selectedDataKeyOption.description}
                </Typography>
              )}
            </Box>

            {/* Endpoint Path (read-only, auto-filled) */}
            <Box>
              <TextField
                fullWidth
                label="Endpoint Path"
                value={endpoint.path}
                disabled
                helperText="Auto-filled based on data key selection"
              />
            </Box>

            {/* Polling Interval */}
            <Box>
              <TextField
                fullWidth
                type="number"
                label="Polling Interval (seconds)"
                value={endpoint.polling_interval_seconds || 60}
                onChange={(e) =>
                  handleIntervalChange('polling_interval_seconds', parseInt(e.target.value, 10))
                }
                helperText="Controls next_request_time in transaction"
                inputProps={{ min: 1 }}
              />
            </Box>
          </Box>
        </Paper>

        {/* Data Structure Form Section */}
        <Paper elevation={2} sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>
            Data Structure
          </Typography>
          <Divider sx={{ mb: 2 }} />

          {isLoadingStructure ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', p: 3 }}>
              <CircularProgress size={24} sx={{ mr: 2 }} />
              <Typography>Loading structure template...</Typography>
            </Box>
          ) : structureError ? (
            <Alert severity="error">{structureError}</Alert>
          ) : Object.keys(endpoint.data_structure).length === 0 ? (
            <Typography variant="body2" color="textSecondary">
              Select a data key above to load the structure template.
            </Typography>
          ) : (
            <PollingDataForm
              dataStructure={endpoint.data_structure}
              onChange={(updated) => {
                onChange({
                  ...endpoint,
                  data_structure: updated,
                });
              }}
            />
          )}
        </Paper>
      </Collapse>
    </Box>
  );
};
