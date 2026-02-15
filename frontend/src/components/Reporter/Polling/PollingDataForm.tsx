/**
 * Polling Data Form Component
 *
 * IRP-style accordion form for configuring polling data structures.
 * Shows iterations clearly with smart context-aware "Add" buttons.
 */

import React from 'react';
import {
  Box,
  Typography,
  Button,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Stack,
  IconButton,
  Tooltip,
  InputAdornment,
  Checkbox,
  FormControlLabel,
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  Delete as DeleteIcon,
  HelpOutline as HelpOutlineIcon,
} from '@mui/icons-material';

import { FieldValue, FieldType } from '../../../types/polling';

interface PollingDataFormProps {
  dataStructure: Record<string, FieldValue>;
  onChange: (updated: Record<string, FieldValue>) => void;
}

export const PollingDataForm: React.FC<PollingDataFormProps> = ({
  dataStructure,
  onChange,
}) => {
  /**
   * Update a field value by path
   */
  const updateFieldByPath = (path: string[], value: any) => {
    const newStructure = JSON.parse(JSON.stringify(dataStructure));
    let current: any = newStructure;

    for (let i = 0; i < path.length - 1; i++) {
      const segment = path[i];
      // For numeric segments (array indices), don't initialize, parent should have array
      if (/^\d+$/.test(segment)) {
        // Skip numeric indices - assume parent is already an array
        current = current[segment];
      } else {
        // For string keys, initialize as object if missing
        if (!current[segment]) {
          current[segment] = {};
        }
        current = current[segment];
      }
    }

    current[path[path.length - 1]] = value;
    onChange(newStructure);
  };

  /**
   * Get value by path
   */
  const getValueByPath = (path: string[]): any => {
    let current: any = dataStructure;
    for (const segment of path) {
      if (!current || !current[segment]) return undefined;
      current = current[segment];
    }
    return current;
  };

  /**
   * Get smart button label based on field name
   */
  const getArrayButtonLabel = (fieldName: string): string => {
    const lowerName = fieldName.toLowerCase();

    // Policy arrays
    if (
      lowerName.includes('ertfeed') ||
      lowerName.includes('bdos') ||
      lowerName.includes('tls-fingerprint') ||
      lowerName.includes('dns-protection') ||
      lowerName.includes('web-ddos')
    ) {
      return 'Add Policy';
    }

    // Data arrays
    if (lowerName === 'data') {
      return 'Add Data Entry';
    }

    // Default
    return 'Add Item';
  };


  /**
   * Render a nested field within an array item
   * This handles updating individual properties without path navigation
   */
  const renderNestedField = (
    fieldName: string,
    fieldTemplate: FieldValue,
    currentValue: any,
    onUpdate: (value: any) => void,
    disabled: boolean = false
  ): React.ReactNode => {
    const key = `nested-${fieldName}`;

    // STRING
    if (fieldTemplate.type === FieldType.STRING) {
      // Check if it has options (enum/dropdown)
      if (fieldTemplate.options && fieldTemplate.options.length > 0) {
        return (
          <Box key={key}>
            <FormControl
              fullWidth
              margin="normal"
              size="small"
              disabled={disabled}
              sx={{
                '& .MuiInputBase-root': {
                  backgroundColor: disabled ? 'action.disabledBackground' : 'inherit',
                  opacity: disabled ? 0.6 : 1,
                },
              }}
            >
              <InputLabel>{fieldName}</InputLabel>
              <Select
                value={currentValue?.value || fieldTemplate.value || ''}
                onChange={(e) => onUpdate({ mode: 'fixed', value: e.target.value })}
                label={fieldName}
                disabled={disabled}
              >
                {fieldTemplate.options.map((opt) => (
                  <MenuItem key={opt} value={opt}>
                    {opt}
                  </MenuItem>
                ))}
              </Select>
              {disabled && fieldName === 'tcp-flag' && (
                <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5 }}>
                  Only available when protocol is TCP
                </Typography>
              )}
            </FormControl>
          </Box>
        );
      }

      // Regular string with random checkbox
      const currentMode = currentValue?.mode || fieldTemplate.mode || 'fixed';
      const isRandom = currentMode === 'random';

      return (
        <Box key={key} sx={{ mt: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <Typography variant="body2" sx={{ flexGrow: 1 }}>
              {fieldName}
            </Typography>
            <FormControlLabel
              control={
                <Checkbox
                  size="small"
                  checked={isRandom}
                  onChange={(e) => {
                    if (e.target.checked) {
                      // Switch to random
                      onUpdate({ mode: 'random' });
                    } else {
                      // Switch to fixed
                      onUpdate({ mode: 'fixed', value: fieldTemplate.value || '' });
                    }
                  }}
                />
              }
              label="Random"
            />
          </Box>
          {isRandom ? (
            <Typography variant="body2" color="text.secondary" sx={{ p: 1, bgcolor: 'grey.100', borderRadius: 1 }}>
              Auto-generated
            </Typography>
          ) : (
            <TextField
              fullWidth
              value={currentValue?.value || fieldTemplate.value || ''}
              onChange={(e) => onUpdate({ mode: 'fixed', value: e.target.value })}
              size="small"
            />
          )}
        </Box>
      );
    }

    // NUMBER
    if (fieldTemplate.type === FieldType.NUMBER) {
      const currentMode = currentValue?.mode || fieldTemplate.mode || 'fixed';
      const isRandom = currentMode === 'random';

      return (
        <Box key={key} sx={{ mt: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <Typography variant="body2" sx={{ flexGrow: 1 }}>
              {fieldName}
            </Typography>
            <FormControlLabel
              control={
                <Checkbox
                  size="small"
                  checked={isRandom}
                  onChange={(e) => {
                    if (e.target.checked) {
                      // Switch to random
                      onUpdate({
                        mode: 'random',
                        min: fieldTemplate.min || 0,
                        max: fieldTemplate.max || 100,
                      });
                    } else {
                      // Switch to fixed
                      onUpdate({ mode: 'fixed', value: fieldTemplate.value || 0 });
                    }
                  }}
                />
              }
              label="Random"
            />
          </Box>
          {isRandom ? (
            <Stack direction="row" spacing={1}>
              <TextField
                fullWidth
                type="number"
                label="Min"
                value={currentValue?.min ?? fieldTemplate.min ?? 0}
                onChange={(e) =>
                  onUpdate({
                    mode: 'random',
                    min: parseInt(e.target.value, 10),
                    max: currentValue?.max ?? fieldTemplate.max ?? 100,
                  })
                }
                size="small"
              />
              <TextField
                fullWidth
                type="number"
                label="Max"
                value={currentValue?.max ?? fieldTemplate.max ?? 100}
                onChange={(e) =>
                  onUpdate({
                    mode: 'random',
                    min: currentValue?.min ?? fieldTemplate.min ?? 0,
                    max: parseInt(e.target.value, 10),
                  })
                }
                size="small"
              />
            </Stack>
          ) : (
            <TextField
              fullWidth
              type="number"
              value={currentValue?.value ?? fieldTemplate.value ?? 0}
              onChange={(e) => onUpdate({ mode: 'fixed', value: parseFloat(e.target.value) })}
              size="small"
              inputProps={{ step: 'any' }}
            />
          )}
        </Box>
      );
    }

    // BOOLEAN
    if (fieldTemplate.type === FieldType.BOOLEAN) {
      return (
        <FormControl key={key} fullWidth margin="normal" size="small">
          <InputLabel>{fieldName}</InputLabel>
          <Select
            value={String(currentValue?.value ?? fieldTemplate.value ?? false)}
            onChange={(e) => onUpdate({ mode: 'fixed', value: e.target.value === 'true' })}
            label={fieldName}
          >
            <MenuItem value="true">True</MenuItem>
            <MenuItem value="false">False</MenuItem>
          </Select>
        </FormControl>
      );
    }

    // TEMPLATE
    if (fieldTemplate.type === FieldType.TEMPLATE) {
      return (
        <Box key={key} sx={{ mt: 2 }}>
          <TextField
            fullWidth
            label={fieldName}
            value={currentValue || fieldTemplate.value || ''}
            onChange={(e) => onUpdate(e.target.value)}
            size="small"
            helperText="Use {{INDEX}} for iteration number (e.g., pol{{INDEX}} → pol0, pol1, pol2...)"
          />
        </Box>
      );
    }

    // RANDOM_COMPOSITE
    if (fieldTemplate.type === FieldType.RANDOM_COMPOSITE) {
      const parts = currentValue?.parts || fieldTemplate.parts || [];

      return (
        <Box key={key} sx={{ mt: 2, border: '1px solid #e0e0e0', p: 2, borderRadius: 1 }}>
          <Typography variant="subtitle2" fontWeight="bold" gutterBottom>
            {fieldName} (Random Composite)
          </Typography>
          <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 2 }}>
            Build composite values from random numbers and literal strings
          </Typography>

          {/* Parts List */}
          {parts.map((part: any, index: number) => (
            <Box
              key={`${key}-part-${index}`}
              sx={{ mb: 2, p: 1.5, border: '1px solid #ddd', borderRadius: 1 }}
            >
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                <Typography variant="caption" fontWeight="bold">
                  Part {index + 1}
                </Typography>
                <IconButton
                  size="small"
                  onClick={() => {
                    const newParts = parts.filter((_: any, i: number) => i !== index);
                    onUpdate({ parts: newParts });
                  }}
                >
                  <DeleteIcon fontSize="small" />
                </IconButton>
              </Box>

              {/* Type Selector */}
              <FormControl fullWidth size="small" sx={{ mb: 1 }}>
                <InputLabel>Type</InputLabel>
                <Select
                  value={part.type || 'literal'}
                  onChange={(e) => {
                    const newParts = [...parts];
                    if (e.target.value === 'random') {
                      newParts[index] = { type: 'random', min: 0, max: 100 };
                    } else {
                      newParts[index] = { type: 'literal', value: '' };
                    }
                    onUpdate({ parts: newParts });
                  }}
                  label="Type"
                >
                  <MenuItem value="random">Random Number</MenuItem>
                  <MenuItem value="literal">Literal Text</MenuItem>
                </Select>
              </FormControl>

              {/* Random Number Fields */}
              {part.type === 'random' && (
                <Stack direction="row" spacing={1}>
                  <TextField
                    fullWidth
                    type="number"
                    label="Min"
                    value={part.min || 0}
                    onChange={(e) => {
                      const newParts = [...parts];
                      newParts[index] = { ...part, min: parseInt(e.target.value, 10) };
                      onUpdate({ parts: newParts });
                    }}
                    size="small"
                  />
                  <TextField
                    fullWidth
                    type="number"
                    label="Max"
                    value={part.max || 100}
                    onChange={(e) => {
                      const newParts = [...parts];
                      newParts[index] = { ...part, max: parseInt(e.target.value, 10) };
                      onUpdate({ parts: newParts });
                    }}
                    size="small"
                  />
                </Stack>
              )}

              {/* Literal Text Field */}
              {part.type === 'literal' && (
                <TextField
                  fullWidth
                  label="Value"
                  value={part.value || ''}
                  onChange={(e) => {
                    const newParts = [...parts];
                    newParts[index] = { ...part, value: e.target.value };
                    onUpdate({ parts: newParts });
                  }}
                  size="small"
                />
              )}
            </Box>
          ))}

          {/* Add Part Button */}
          <Button
            variant="outlined"
            size="small"
            startIcon={<span>+</span>}
            onClick={() => {
              const newParts = [...parts, { type: 'literal', value: '' }];
              onUpdate({ parts: newParts });
            }}
          >
            Add Part
          </Button>

          {/* Preview */}
          {parts.length > 0 && (
            <Box sx={{ mt: 2, p: 1, bgcolor: 'grey.50', borderRadius: 1 }}>
              <Typography variant="caption" color="text.secondary">
                Example:{' '}
                {parts
                  .map((p: any) => (p.type === 'random' ? `[${p.min}-${p.max}]` : p.value))
                  .join('')}
              </Typography>
            </Box>
          )}
        </Box>
      );
    }

    // TIMESTAMP - always has offset
    if (fieldTemplate.type === FieldType.TIMESTAMP) {
      return (
        <TextField
          key={key}
          fullWidth
          type="number"
          label={fieldName}
          value={currentValue?.offset ?? fieldTemplate.offset ?? 0}
          onChange={(e) => onUpdate({ offset: parseInt(e.target.value, 10) })}
          margin="normal"
          size="small"
          helperText="Offset in seconds from current time"
          inputProps={{ min: 0 }}
          InputProps={{
            endAdornment: (
              <InputAdornment position="end">
                <Tooltip
                  title="Enter positive number for seconds in the past (e.g., 120 = 2 minutes ago, 0 = current time)"
                  arrow
                >
                  <IconButton size="small" edge="end">
                    <HelpOutlineIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              </InputAdornment>
            ),
          }}
        />
      );
    }


    // RANDOM
    if (fieldTemplate.type === FieldType.RANDOM) {
      const val = currentValue || { min: fieldTemplate.min || 0, max: fieldTemplate.max || 100 };
      return (
        <Stack key={key} direction="row" spacing={1} sx={{ mt: 2 }}>
          <TextField
            fullWidth
            type="number"
            label={`${fieldName} (Min)`}
            value={val.min || 0}
            onChange={(e) => onUpdate({ ...val, min: parseInt(e.target.value, 10) })}
            size="small"
          />
          <TextField
            fullWidth
            type="number"
            label={`${fieldName} (Max)`}
            value={val.max || 100}
            onChange={(e) => onUpdate({ ...val, max: parseInt(e.target.value, 10) })}
            size="small"
          />
        </Stack>
      );
    }

    // RANDOM_IPV4
    if (fieldTemplate.type === FieldType.RANDOM_IPV4) {
      return (
        <Typography key={key} variant="body2" color="text.secondary" sx={{ mt: 2 }}>
          {fieldName}: Random IPv4 (auto-generated)
        </Typography>
      );
    }

    // RANDOM_FQDN
    if (fieldTemplate.type === FieldType.RANDOM_FQDN) {
      const val = currentValue || { suffix: fieldTemplate.suffix || '.com' };
      return (
        <TextField
          key={key}
          fullWidth
          label={`${fieldName} (Suffix)`}
          value={val.suffix || '.com'}
          onChange={(e) => onUpdate({ suffix: e.target.value })}
          margin="normal"
          size="small"
          helperText="Domain suffix (e.g., .com, .net)"
        />
      );
    }

    // ARRAY (nested)
    if (fieldTemplate.type === FieldType.ARRAY) {
      const arrayVal = currentValue || [];
      const itemTemplate = fieldTemplate.item || { type: FieldType.STRING, value: '' };

      /**
       * Initialize a new nested item from template
       */
      const initializeNestedItem = (template: FieldValue): any => {
        if (template.type === FieldType.OBJECT && template.properties) {
          const newItem: any = {};
          Object.keys(template.properties).forEach((propKey) => {
            const prop = template.properties![propKey];
            if (prop.type === FieldType.STRING) {
              newItem[propKey] = prop.value || '';
            } else if (prop.type === FieldType.NUMBER) {
              newItem[propKey] = prop.value || 0;
            } else if (prop.type === FieldType.BOOLEAN) {
              newItem[propKey] = prop.value || false;
            } else if (prop.type === FieldType.TIMESTAMP) {
              newItem[propKey] = prop.offset || 0;
            } else if (prop.type === FieldType.TEMPLATE) {
              newItem[propKey] = prop.value || '';
            } else if (prop.type === FieldType.RANDOM_COMPOSITE) {
              newItem[propKey] = { parts: prop.parts || [] };
            } else if (prop.type === FieldType.ARRAY) {
              newItem[propKey] = [];
            } else if (prop.type === FieldType.RANDOM) {
              newItem[propKey] = { min: prop.min || 0, max: prop.max || 100 };
            } else if (prop.type === FieldType.RANDOM_FQDN) {
              newItem[propKey] = { suffix: prop.suffix || '.com' };
            } else if (prop.type === FieldType.RANDOM_IPV4) {
              newItem[propKey] = null;
            } else {
              newItem[propKey] = prop.value || '';
            }
          });
          return newItem;
        } else {
          return template.value || '';
        }
      };

      return (
        <Box key={key} sx={{ mt: 2, border: '1px solid #ddd', p: 2, borderRadius: 1 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
            <Typography variant="subtitle2" fontWeight="bold">
              {fieldName} ({arrayVal.length} item{arrayVal.length !== 1 ? 's' : ''})
            </Typography>
            <Button
              size="small"
              variant="outlined"
              onClick={() => {
                const newItem = initializeNestedItem(itemTemplate);
                onUpdate([...arrayVal, newItem]);
              }}
              startIcon={<span>+</span>}
            >
              Add Data Entry
            </Button>
          </Box>

          {arrayVal.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No items yet
            </Typography>
          ) : (
            arrayVal.map((item: any, index: number) => (
              <Accordion key={`${key}-item-${index}`} sx={{ mb: 1 }}>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography variant="body2">Item {index + 1}</Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Box sx={{ pl: 2 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 1 }}>
                      <Button
                        size="small"
                        color="error"
                        onClick={() => {
                          const newArray = arrayVal.filter((_: any, i: number) => i !== index);
                          onUpdate(newArray);
                        }}
                        startIcon={<DeleteIcon />}
                      >
                        Remove
                      </Button>
                    </Box>

                    {/* Render nested item fields */}
                    {itemTemplate.type === FieldType.OBJECT && itemTemplate.properties ? (
                      Object.keys(itemTemplate.properties).map((propKey) => {
                        const propTemplate = itemTemplate.properties![propKey];
                        return renderNestedField(
                          propKey,
                          propTemplate,
                          item[propKey],
                          (updatedValue) => {
                            const newArray = [...arrayVal];
                            newArray[index] = {
                              ...newArray[index],
                              [propKey]: updatedValue,
                            };
                            onUpdate(newArray);
                          }
                        );
                      })
                    ) : (
                      <TextField
                        fullWidth
                        label={`Value ${index + 1}`}
                        value={item || ''}
                        onChange={(e) => {
                          const newArray = [...arrayVal];
                          newArray[index] = e.target.value;
                          onUpdate(newArray);
                        }}
                        size="small"
                      />
                    )}
                  </Box>
                </AccordionDetails>
              </Accordion>
            ))
          )}
        </Box>
      );
    }

    // Default
    return (
      <TextField
        key={key}
        fullWidth
        label={fieldName}
        value={currentValue || ''}
        onChange={(e) => onUpdate(e.target.value)}
        margin="normal"
        size="small"
      />
    );
  };

  /**
   * Render field based on type
   */
  const renderField = (
    fieldName: string,
    fieldValue: FieldValue,
    path: string[] = []
  ): React.ReactNode => {
    const currentPath = [...path, fieldName];
    const pathString = currentPath.join('.');
    const value = getValueByPath(currentPath);

    // STRING
    if (fieldValue.type === FieldType.STRING) {
      const mode = fieldValue.mode || 'fixed';
      const isRandom = mode === 'random';
      // Don't show mode checkbox for enum fields (with options)
      const hasOptions = fieldValue.options && fieldValue.options.length > 0;

      if (hasOptions && fieldValue.options) {
        // ENUM field - dropdown only, no checkbox
        return (
          <FormControl key={pathString} fullWidth margin="normal" size="small">
            <InputLabel>{fieldName}</InputLabel>
            <Select
              value={(value as string) || fieldValue.value || ''}
              onChange={(e) => updateFieldByPath(currentPath, e.target.value)}
              label={fieldName}
            >
              {fieldValue.options.map((option) => (
                <MenuItem key={option} value={option}>
                  {option}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        );
      }

      // Regular STRING field with mode toggle
      return (
        <Box key={pathString} sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
          <TextField
            fullWidth
            label={fieldName}
            value={isRandom ? '(auto-generated)' : ((value as string) || fieldValue.value || '')}
            onChange={(e) => {
              updateFieldByPath(currentPath, {
                ...fieldValue,
                value: e.target.value,
              });
            }}
            size="small"
            disabled={isRandom}
            placeholder={isRandom ? 'Random value will be generated' : 'Enter value'}
          />
          <FormControlLabel
            control={
              <Checkbox
                checked={isRandom}
                onChange={(e) => {
                  updateFieldByPath(currentPath, {
                    ...fieldValue,
                    mode: e.target.checked ? 'random' : 'fixed',
                    value: e.target.checked ? '' : fieldValue.value,
                  });
                }}
                size="small"
              />
            }
            label="Random"
          />
        </Box>
      );
    }

    // NUMBER
    if (fieldValue.type === FieldType.NUMBER) {
      const mode = fieldValue.mode || 'fixed';
      const isRandom = mode === 'random';

      return (
        <Box key={pathString} sx={{ mt: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {isRandom ? (
              <>
                <TextField
                  label={`${fieldName} (Min)`}
                  type="number"
                  value={fieldValue.min ?? 0}
                  onChange={(e) => {
                    updateFieldByPath(currentPath, {
                      ...fieldValue,
                      min: parseInt(e.target.value, 10),
                    });
                  }}
                  size="small"
                  sx={{ flex: 1 }}
                />
                <TextField
                  label={`${fieldName} (Max)`}
                  type="number"
                  value={fieldValue.max ?? 100}
                  onChange={(e) => {
                    updateFieldByPath(currentPath, {
                      ...fieldValue,
                      max: parseInt(e.target.value, 10),
                    });
                  }}
                  size="small"
                  sx={{ flex: 1 }}
                />
              </>
            ) : (
              <TextField
                fullWidth
                type="number"
                label={fieldName}
                value={(value as number) || fieldValue.value || 0}
                onChange={(e) =>
                  updateFieldByPath(currentPath, {
                    ...fieldValue,
                    value: parseFloat(e.target.value),
                  })
                }
                size="small"
              />
            )}
            <FormControlLabel
              control={
                <Checkbox
                  checked={isRandom}
                  onChange={(e) => {
                    updateFieldByPath(currentPath, {
                      ...fieldValue,
                      mode: e.target.checked ? 'random' : 'fixed',
                      min: fieldValue.min ?? 0,
                      max: fieldValue.max ?? 100,
                      value: e.target.checked ? undefined : (fieldValue.value ?? 0),
                    });
                  }}
                  size="small"
                />
              }
              label="Random"
            />
          </Box>
        </Box>
      );
    }

    // BOOLEAN
    if (fieldValue.type === FieldType.BOOLEAN) {
      return (
        <FormControl key={pathString} fullWidth margin="normal" size="small">
          <InputLabel>{fieldName}</InputLabel>
          <Select
            value={String(value !== undefined ? value : fieldValue.value || false)}
            onChange={(e) => updateFieldByPath(currentPath, e.target.value === 'true')}
            label={fieldName}
          >
            <MenuItem value="true">True</MenuItem>
            <MenuItem value="false">False</MenuItem>
          </Select>
        </FormControl>
      );
    }

    // TIMESTAMP
    if (fieldValue.type === FieldType.TIMESTAMP) {
      return (
        <TextField
          key={pathString}
          fullWidth
          type="number"
          label={fieldName}
          value={(value as number) || fieldValue.offset || 0}
          onChange={(e) => {
            const newFieldValue = { ...fieldValue, offset: parseInt(e.target.value, 10) };
            updateFieldByPath(currentPath, newFieldValue);
          }}
          margin="normal"
          size="small"
          helperText="Offset in seconds from current time"
          inputProps={{ min: 0 }}
          InputProps={{
            endAdornment: (
              <InputAdornment position="end">
                <Tooltip
                  title="Enter positive number for seconds in the past (e.g., 120 = 2 minutes ago, 0 = current time)"
                  arrow
                >
                  <IconButton size="small" edge="end">
                    <HelpOutlineIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              </InputAdornment>
            ),
          }}
        />
      );
    }

    // TEMPLATE
    if (fieldValue.type === FieldType.TEMPLATE) {
      return (
        <TextField
          key={pathString}
          fullWidth
          label={fieldName}
          value={(value as string) || fieldValue.value || ''}
          onChange={(e) => updateFieldByPath(currentPath, e.target.value)}
          margin="normal"
          size="small"
          helperText="Use {{INDEX}} for array index substitution"
        />
      );
    }

    // RANDOM
    if (fieldValue.type === FieldType.RANDOM) {
      return (
        <Stack key={pathString} direction="row" spacing={1} sx={{ mt: 2 }}>
          <TextField
            fullWidth
            type="number"
            label={`${fieldName} (Min)`}
            value={(value?.min as number) || fieldValue.min || 0}
            onChange={(e) => {
              const newValue = { ...value, min: parseInt(e.target.value, 10) };
              updateFieldByPath(currentPath, newValue);
            }}
            size="small"
          />
          <TextField
            fullWidth
            type="number"
            label={`${fieldName} (Max)`}
            value={(value?.max as number) || fieldValue.max || 100}
            onChange={(e) => {
              const newValue = { ...value, max: parseInt(e.target.value, 10) };
              updateFieldByPath(currentPath, newValue);
            }}
            size="small"
          />
        </Stack>
      );
    }

    // RANDOM_IPV4
    if (fieldValue.type === FieldType.RANDOM_IPV4) {
      return (
        <Typography key={pathString} variant="body2" color="text.secondary" sx={{ mt: 2 }}>
          {fieldName}: Random IPv4 (auto-generated)
        </Typography>
      );
    }

    // RANDOM_FQDN
    if (fieldValue.type === FieldType.RANDOM_FQDN) {
      return (
        <TextField
          key={pathString}
          fullWidth
          label={`${fieldName} (Suffix)`}
          value={(value?.suffix as string) || fieldValue.suffix || '.com'}
          onChange={(e) => {
            const newValue = { ...value, suffix: e.target.value };
            updateFieldByPath(currentPath, newValue);
          }}
          margin="normal"
          size="small"
          helperText="Domain suffix (e.g., .com, .net)"
        />
      );
    }

    // NULL
    if (fieldValue.type === FieldType.NULL) {
      return (
        <Box key={pathString} sx={{ mt: 2, p: 1, bgcolor: 'grey.100', borderRadius: 1 }}>
          <Typography variant="body2" color="text.secondary">
            {fieldName}: null (no configuration needed)
          </Typography>
        </Box>
      );
    }

    // RANDOM_COMPOSITE
    if (fieldValue.type === FieldType.RANDOM_COMPOSITE) {
      const parts = (value?.parts as any[]) || fieldValue.parts || [];

      return (
        <Box key={pathString} sx={{ mt: 2, border: '1px solid #e0e0e0', p: 2, borderRadius: 1 }}>
          <Typography variant="subtitle2" fontWeight="bold" gutterBottom>
            {fieldName} (Random Composite)
          </Typography>
          <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 2 }}>
            Build composite values from random numbers and literal strings
          </Typography>

          {/* Parts List */}
          {parts.map((part: any, index: number) => (
            <Box
              key={`${pathString}-part-${index}`}
              sx={{ mb: 2, p: 1.5, border: '1px solid #ddd', borderRadius: 1 }}
            >
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                <Typography variant="caption" fontWeight="bold">
                  Part {index + 1}
                </Typography>
                <IconButton
                  size="small"
                  onClick={() => {
                    const newParts = parts.filter((_: any, i: number) => i !== index);
                    updateFieldByPath(currentPath, { ...value, parts: newParts });
                  }}
                >
                  <DeleteIcon fontSize="small" />
                </IconButton>
              </Box>

              {/* Type Selector */}
              <FormControl fullWidth size="small" sx={{ mb: 1 }}>
                <InputLabel>Type</InputLabel>
                <Select
                  value={part.type || 'literal'}
                  onChange={(e) => {
                    const newParts = [...parts];
                    if (e.target.value === 'random') {
                      newParts[index] = { type: 'random', min: 0, max: 100 };
                    } else {
                      newParts[index] = { type: 'literal', value: '' };
                    }
                    updateFieldByPath(currentPath, { ...value, parts: newParts });
                  }}
                  label="Type"
                >
                  <MenuItem value="random">Random Number</MenuItem>
                  <MenuItem value="literal">Literal Text</MenuItem>
                </Select>
              </FormControl>

              {/* Random Number Fields */}
              {part.type === 'random' && (
                <Stack direction="row" spacing={1}>
                  <TextField
                    fullWidth
                    type="number"
                    label="Min"
                    value={part.min || 0}
                    onChange={(e) => {
                      const newParts = [...parts];
                      newParts[index] = { ...part, min: parseInt(e.target.value, 10) };
                      updateFieldByPath(currentPath, { ...value, parts: newParts });
                    }}
                    size="small"
                  />
                  <TextField
                    fullWidth
                    type="number"
                    label="Max"
                    value={part.max || 100}
                    onChange={(e) => {
                      const newParts = [...parts];
                      newParts[index] = { ...part, max: parseInt(e.target.value, 10) };
                      updateFieldByPath(currentPath, { ...value, parts: newParts });
                    }}
                    size="small"
                  />
                </Stack>
              )}

              {/* Literal Text Field */}
              {part.type === 'literal' && (
                <TextField
                  fullWidth
                  label="Value"
                  value={part.value || ''}
                  onChange={(e) => {
                    const newParts = [...parts];
                    newParts[index] = { ...part, value: e.target.value };
                    updateFieldByPath(currentPath, { ...value, parts: newParts });
                  }}
                  size="small"
                />
              )}
            </Box>
          ))}

          {/* Add Part Button */}
          <Button
            variant="outlined"
            size="small"
            startIcon={<span>+</span>}
            onClick={() => {
              const newParts = [...parts, { type: 'literal', value: '' }];
              updateFieldByPath(currentPath, { ...value, parts: newParts });
            }}
          >
            Add Part
          </Button>

          {/* Preview */}
          {parts.length > 0 && (
            <Box sx={{ mt: 2, p: 1, bgcolor: 'grey.50', borderRadius: 1 }}>
              <Typography variant="caption" color="text.secondary">
                Example:{' '}
                {parts
                  .map((p: any) => (p.type === 'random' ? `[${p.min}-${p.max}]` : p.value))
                  .join('')}
              </Typography>
            </Box>
          )}
        </Box>
      );
    }

    // OBJECT
    if (fieldValue.type === FieldType.OBJECT) {
      const props = fieldValue.properties || {};
      return (
        <Accordion key={pathString} sx={{ mt: 1 }}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="subtitle2" fontWeight="bold">
              {fieldName}
            </Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Box sx={{ pl: 2 }}>
              {Object.keys(props).map((propKey) =>
                renderField(propKey, props[propKey], currentPath)
              )}
            </Box>
          </AccordionDetails>
        </Accordion>
      );
    }

    // ARRAY
    if (fieldValue.type === FieldType.ARRAY || fieldValue.type === 'array' || fieldValue.type === 'ARRAY') {
      const itemTemplate = fieldValue.item || { type: FieldType.STRING, value: '' };
      const buttonLabel = getArrayButtonLabel(fieldName);

      /**
       * Initialize a new item from template
       */
      const initializeItemFromTemplate = (template: FieldValue): any => {
        if (template.type === FieldType.OBJECT && template.properties) {
          const newItem: any = {};
          Object.keys(template.properties).forEach((key) => {
            const prop = template.properties![key];
            if (prop.type === FieldType.STRING) {
              newItem[key] = prop.value || '';
            } else if (prop.type === FieldType.NUMBER) {
              newItem[key] = prop.value || 0;
            } else if (prop.type === FieldType.BOOLEAN) {
              newItem[key] = prop.value || false;
            } else if (prop.type === FieldType.TIMESTAMP) {
              newItem[key] = prop.offset || 0;
            } else if (prop.type === FieldType.TEMPLATE) {
              newItem[key] = prop.value || '';
            } else if (prop.type === FieldType.RANDOM_COMPOSITE) {
              newItem[key] = { parts: prop.parts || [] };
            } else if (prop.type === FieldType.ARRAY) {
              newItem[key] = [];
            } else if (prop.type === FieldType.RANDOM) {
              newItem[key] = { min: prop.min || 0, max: prop.max || 100 };
            } else if (prop.type === FieldType.RANDOM_FQDN) {
              newItem[key] = { suffix: prop.suffix || '.com' };
            } else if (prop.type === FieldType.RANDOM_IPV4) {
              // No value needed, will be generated
              newItem[key] = null;
            } else {
              newItem[key] = prop.value || '';
            }
          });
          return newItem;
        } else {
          return template.value || '';
        }
      };

      // Get actual array data from fieldValue.value (NOT from getValueByPath)
      let arrayValue: any[] = Array.isArray(fieldValue.value) ? fieldValue.value : [];

      const handleAddIteration = () => {
        const newItem = initializeItemFromTemplate(itemTemplate);
        const newArray = [...arrayValue, newItem];

        // Update the FieldValue.value property, preserving the structure
        const updatedFieldValue = {
          ...fieldValue,
          value: newArray,
        };

        updateFieldByPath(currentPath, updatedFieldValue);
      };

      const handleRemoveIteration = (index: number) => {
        const newArray = arrayValue.filter((_: any, i: number) => i !== index);

        // Update the FieldValue.value property, preserving the structure
        const updatedFieldValue = {
          ...fieldValue,
          value: newArray,
        };

        updateFieldByPath(currentPath, updatedFieldValue);
      };

      return (
        <Box key={pathString} sx={{ mt: 2, border: '1px solid #e0e0e0', p: 2, borderRadius: 1 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
            <Typography variant="subtitle2" fontWeight="bold">
              {fieldName} ({arrayValue.length} iteration{arrayValue.length !== 1 ? 's' : ''})
            </Typography>
            <Button
              size="small"
              variant="outlined"
              onClick={handleAddIteration}
              startIcon={<span>+</span>}
            >
              {buttonLabel}
            </Button>
          </Box>

          {arrayValue.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No iterations yet
            </Typography>
          ) : (
            arrayValue.map((item: any, index: number) => (
              <Accordion key={`${pathString}-${index}`} sx={{ mb: 1 }}>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography variant="body2">Iteration {index + 1}</Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Box sx={{ pl: 2 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 1 }}>
                      <Button
                        size="small"
                        color="error"
                        onClick={() => handleRemoveIteration(index)}
                        startIcon={<DeleteIcon />}
                      >
                        Remove
                      </Button>
                    </Box>

                    {/* Render item fields */}
                    {itemTemplate.type === FieldType.OBJECT && itemTemplate.properties ? (
                      Object.keys(itemTemplate.properties).map((propKey) => {
                        // For nested fields, we need to handle updates differently
                        const propTemplate = itemTemplate.properties![propKey];

                        // Check if tcp-flag should be disabled (when protocol is not TCP)
                        let isDisabled = false;
                        if (propKey === 'tcp-flag') {
                          const protocolValue = item['protocol'];

                          console.log('TCP-flag check:', { propKey, protocolValue, item });

                          // Check if protocol is TCP
                          let isTcp = false;
                          if (!protocolValue) {
                            // No protocol set yet - disable tcp-flag
                            isTcp = false;
                          } else if (typeof protocolValue === 'object' && protocolValue?.value) {
                            isTcp = protocolValue.value === 'tcp' || protocolValue.value === '6';
                          } else if (typeof protocolValue === 'string') {
                            isTcp = protocolValue === 'tcp' || protocolValue === '6';
                          }

                          isDisabled = !isTcp;
                          console.log('TCP-flag disabled:', isDisabled, 'isTcp:', isTcp);
                        }

                        return renderNestedField(
                          propKey,
                          propTemplate,
                          item[propKey],
                          (updatedValue) => {
                            // Update this specific item in the array
                            const newArray = [...arrayValue];
                            newArray[index] = {
                              ...newArray[index],
                              [propKey]: updatedValue,
                            };

                            const updatedFieldValue = {
                              ...fieldValue,
                              value: newArray,
                            };

                            updateFieldByPath(currentPath, updatedFieldValue);
                          },
                          isDisabled
                        );
                      })
                    ) : (
                      <TextField
                        fullWidth
                        label={`Value ${index + 1}`}
                        value={item || ''}
                        onChange={(e) => {
                          const newArray = [...arrayValue];
                          newArray[index] = e.target.value;

                          const updatedFieldValue = {
                            ...fieldValue,
                            value: newArray,
                          };

                          updateFieldByPath(currentPath, updatedFieldValue);
                        }}
                        size="small"
                      />
                    )}
                  </Box>
                </AccordionDetails>
              </Accordion>
            ))
          )}
        </Box>
      );
    }

    // Default
    return (
      <Typography key={pathString} variant="body2" color="text.secondary" sx={{ mt: 2 }}>
        {fieldName}: {fieldValue.type} (not yet implemented)
      </Typography>
    );
  };

  return (
    <Box>
      {Object.keys(dataStructure).length === 0 ? (
        <Box sx={{ textAlign: 'center', py: 4, color: 'text.secondary' }}>
          <Typography>No fields configured yet.</Typography>
        </Box>
      ) : (
        Object.keys(dataStructure).map((key) => renderField(key, dataStructure[key], []))
      )}
    </Box>
  );
};
