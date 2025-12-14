import React from 'react'
import {
  Box,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Switch,
  FormControlLabel,
  Typography,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Button,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  List,
  ListItemButton,
  ListItemText,
  InputAdornment,
  Tooltip,
} from '@mui/material'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import CasinoIcon from '@mui/icons-material/Casino'
import { generateAttackId } from '../../pages/IRPSenderPage'

interface IRPMessageFormProps {
  messageData: Record<string, any>
  schema: Record<string, any>
  onChange: (data: Record<string, any>) => void
}

const IRPMessageForm: React.FC<IRPMessageFormProps> = ({ messageData, schema, onChange }) => {
  const handleFieldChange = (path: string[], value: any) => {
    // Deep clone to avoid mutating props
    const newData: Record<string, any> = JSON.parse(JSON.stringify(messageData || {}))
    let current: any = newData

    // Navigate to nested field
    for (let i = 0; i < path.length - 1; i++) {
      if (!current[path[i]] || typeof current[path[i]] !== 'object') current[path[i]] = {}
      current = current[path[i]]
    }

    // Set the value
    current[path[path.length - 1]] = value
    onChange(newData)
  }

  // Footprint selection dialog state and pending path
  const [footprintTypeDialog, setFootprintTypeDialog] = React.useState(false)
  const [pendingFootprintPath, setPendingFootprintPath] = React.useState<string[] | null>(null)
  // Available options for discriminated union (switch) arrays
  const [availableSwitchOptions, setAvailableSwitchOptions] = React.useState<string[]>([])

  const footprintTypes = [
    'checksum', 'sequence-number', 'id-number', 'dns-id', 'dns-qname',
    'dns-subdomain', 'dns-qcount', 'source-port', 'source-ip',
    'fragment-offset', 'flow-label', 'tos', 'packet-size',
    'destination-port', 'destination-ip', 'fragment', 'message-type',
    'ttl', 'context-tag', 'dns-ancount', 'dns-flags'
  ]

  const getNestedValue = (obj: any, path: string[]): any => {
    let cur = obj
    for (const p of path) {
      if (!cur) return undefined
      cur = cur[p]
    }
    return cur
  }

  const renderField = (key: string, fieldSchema: any, value: any, path: string[] = []): React.ReactNode => {
    const currentPath = [...path, key]
    const pathString = currentPath.join('.')
    const fieldType = fieldSchema?.fieldType || 'string'

    // Handle null/undefined by using schema default when available
    if (value === null || value === undefined) {
      value = fieldSchema?.default ?? ''
    }

    // Common metadata keys to exclude from rendering when iterating schema.fields
    const metadataKeys = ['type', 'fieldType', 'default', 'min', 'max', 'required', 'itemType', 'itemSchema']

    // Boolean → Switch (with optional conditional fields)
    if (fieldType === 'boolean') {
      const hasConditionalFields = fieldSchema?.fields && Object.keys(fieldSchema.fields).length > 0
      const boolValue = Boolean(value)

      return (
        <Box key={pathString}>
          <FormControlLabel
            control={
              <Switch
                checked={boolValue}
                onChange={(e) => {
                  const newValue = e.target.checked
                  // When toggling to true and has fields, initialize with defaults from schema
                  if (newValue && hasConditionalFields) {
                    const initialValue: any = {}
                    // Initialize each nested field with its default value
                    Object.keys(fieldSchema.fields).forEach((nestedKey) => {
                      const nestedFieldSchema = fieldSchema.fields[nestedKey]
                      const nestedFieldType = nestedFieldSchema?.fieldType

                      // Initialize arrays as empty arrays
                      if (nestedFieldType === 'array' || nestedFieldType === 'fixed-array') {
                        initialValue[nestedKey] = []
                      } else if (nestedFieldSchema?.default !== undefined) {
                        initialValue[nestedKey] = nestedFieldSchema.default
                      }
                    })
                    handleFieldChange(currentPath, initialValue)
                  } else {
                    handleFieldChange(currentPath, newValue)
                  }
                }}
              />
            }
            label={key}
            sx={{ marginY: 1, display: 'block' }}
          />

          {/* Render conditional fields when boolean is true */}
          {hasConditionalFields && boolValue && typeof value === 'object' && (
            <Box sx={{ marginLeft: 4, marginTop: 1, marginBottom: 2, paddingLeft: 2, borderLeft: '2px solid #ddd' }}>
              {Object.keys(fieldSchema.fields).map((nestedKey) => {
                const nestedFieldSchema = fieldSchema.fields[nestedKey]
                const nestedValue = value[nestedKey]
                // Don't include nestedKey in path - renderField will add it
                return renderField(nestedKey, nestedFieldSchema, nestedValue, currentPath)
              })}
            </Box>
          )}
        </Box>
      )
    }

    // Enum → Select
    if (fieldType === 'enum' && Array.isArray(fieldSchema?.options)) {
      return (
        <FormControl key={pathString} fullWidth margin="normal" size="small">
          <InputLabel>{key}</InputLabel>
          <Select
            value={value ?? fieldSchema.default ?? ''}
            onChange={(e) => handleFieldChange(currentPath, e.target.value)}
            label={key}
          >
            {fieldSchema.options.map((option: string) => (
              <MenuItem key={option} value={option}>
                {option}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      )
    }

    // Bitmap → Multi-select checkboxes (tcp-flags, etc.)
    if (fieldType === 'bitmap' && Array.isArray(fieldSchema?.options)) {
      const selectedFlags = Array.isArray(value) ? value : []
      const numericValue = typeof value === 'number' ? value : 0

      return (
        <Box key={pathString} sx={{ marginY: 2, border: '1px solid #E0E0E0', padding: 2, borderRadius: 1 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 'bold', marginBottom: 1 }}>
            {key} (bitmap)
          </Typography>
          {fieldSchema.options.map((option: string, idx: number) => {
            // Calculate if this bit is set (assuming bit positions from 0-7 for size 1 bitmap)
            const bitPosition = idx
            const isChecked = (numericValue & (1 << bitPosition)) !== 0

            return (
              <FormControlLabel
                key={`${pathString}-${option}`}
                control={
                  <Switch
                    checked={isChecked}
                    onChange={(e) => {
                      let newValue = numericValue
                      if (e.target.checked) {
                        // Set bit
                        newValue |= (1 << bitPosition)
                      } else {
                        // Clear bit
                        newValue &= ~(1 << bitPosition)
                      }
                      handleFieldChange(currentPath, newValue)
                    }}
                  />
                }
                label={option}
                sx={{ display: 'block', marginY: 0.5 }}
              />
            )
          })}
        </Box>
      )
    }

    // Integer → Number input with validation
    if (fieldType === 'integer') {
      const min = fieldSchema?.min
      const max = fieldSchema?.max
      const numeric = Number(value)
      const hasError = typeof min === 'number' && (numeric < min || (typeof max === 'number' && numeric > max))

      return (
        <TextField
          key={pathString}
          fullWidth
          label={key}
          type="number"
          value={value}
          onChange={(e) => {
            const num = parseInt(e.target.value as string, 10)
            handleFieldChange(currentPath, isNaN(num) ? 0 : num)
          }}
          margin="normal"
          size="small"
          error={hasError}
          helperText={
            hasError
              ? `Must be between ${min ?? '-inf'} and ${max ?? 'inf'}`
              : typeof min === 'number'
              ? `Range: ${min} - ${max ?? 'max'}`
              : ''
          }
          inputProps={{ min: min, max: max }}
        />
      )
    }

    // Float → Number input
    if (fieldType === 'float') {
      return (
        <TextField
          key={pathString}
          fullWidth
          label={key}
          type="number"
          value={value}
          onChange={(e) => {
            const num = parseFloat(e.target.value as string)
            handleFieldChange(currentPath, isNaN(num) ? 0.0 : num)
          }}
          margin="normal"
          size="small"
          inputProps={{ step: 0.01 }}
        />
      )
    }

    // IPv4/IPv6 → Text input with validation
    if (fieldType === 'ipv4' || fieldType === 'ipv6') {
      const validateIP = (ip: string) => {
        if (fieldType === 'ipv4') {
          const ipv4Regex = /^(\d{1,3}\.){3}\d{1,3}$/
          if (!ipv4Regex.test(ip)) return false
          const parts = ip.split('.')
          return parts.every((part) => {
            const num = parseInt(part, 10)
            return !isNaN(num) && num >= 0 && num <= 255
          })
        } else {
          // IPv6 validation (simplified)
          const ipv6Regex = /^([0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}$/
          return ipv6Regex.test(ip)
        }
      }

      const isValid = !value || validateIP(String(value))

      return (
        <TextField
          key={pathString}
          fullWidth
          label={`${key} (${fieldType.toUpperCase()})`}
          value={value}
          onChange={(e) => handleFieldChange(currentPath, e.target.value)}
          margin="normal"
          size="small"
          placeholder={fieldType === 'ipv4' ? '192.168.1.1' : '2001:db8::1'}
          error={!isValid}
          helperText={!isValid ? `Invalid ${fieldType.toUpperCase()} address` : ''}
        />
      )
    }

    // Array → Render items with their fields
    if (fieldType === 'array' || fieldType === 'fixed-array') {
      const arrayValue = Array.isArray(value) ? value : []
      const itemSchema = fieldSchema?.itemSchema || {}
      const isFootprintArray = fieldSchema?.footprintTypes === true
      const isSwitchArray = itemSchema?.fieldType === 'switch'

      const handleAddIteration = () => {
        // Check if fixed array has reached max size
        if (fieldType === 'fixed-array' && fieldSchema?.maxItems && arrayValue.length >= fieldSchema.maxItems) {
          return
        }

        if (isSwitchArray) {
          // compute available options from schema and existing items
          const switchOptions = itemSchema?.options || {}
          const availableOptions = Object.keys(switchOptions).filter((optionKey) => {
            // Filter out already-selected options in this array
            return !arrayValue.some((item: any) => Object.keys(item)[0] === optionKey)
          })
          setAvailableSwitchOptions(availableOptions)
          setPendingFootprintPath(currentPath)
          setFootprintTypeDialog(true)
        } else if (isFootprintArray) {
          // open dialog to pick footprint type and remember path
          setPendingFootprintPath(currentPath)
          setFootprintTypeDialog(true)
        } else {
          const newItem: any = {}
          // Initialize with defaults from schema (itemSchema may be object of fields)
          if (itemSchema && typeof itemSchema === 'object' && !Array.isArray(itemSchema)) {
            Object.keys(itemSchema).forEach((k) => {
              newItem[k] = itemSchema[k]?.default ?? ''
            })
          }

          // Auto-increment port field if it exists in the item schema
          if (itemSchema && typeof itemSchema === 'object' && 'port' in itemSchema) {
            // Find the highest port number in existing items
            let maxPort = 0
            arrayValue.forEach((item: any) => {
              if (item && typeof item === 'object' && typeof item.port === 'number') {
                maxPort = Math.max(maxPort, item.port)
              }
            })
            newItem.port = maxPort + 1
          }

          // Auto-increment policy-name field if it exists in the item schema
          if (itemSchema && typeof itemSchema === 'object' && 'policy-name' in itemSchema) {
            // Find the highest policy number in existing items
            let maxPolicyNum = 0
            arrayValue.forEach((item: any) => {
              if (item && typeof item === 'object' && typeof item['policy-name'] === 'string') {
                const match = item['policy-name'].match(/pol(\d+)/)
                if (match) {
                  const policyNum = parseInt(match[1], 10)
                  maxPolicyNum = Math.max(maxPolicyNum, policyNum)
                }
              }
            })
            newItem['policy-name'] = `pol${maxPolicyNum + 1}`
          }

          handleFieldChange(currentPath, [...arrayValue, newItem])
        }
      }

      const handleAddFootprintType = (type: string) => {
        if (!pendingFootprintPath) return
        const existing = getNestedValue(messageData || {}, pendingFootprintPath) || []
        // For switch arrays we add the selected option as an object with its key
        const newItem = { [type]: [] }
        handleFieldChange(pendingFootprintPath, [...existing, newItem])
        setFootprintTypeDialog(false)
        setPendingFootprintPath(null)
        setAvailableSwitchOptions([])
      }

      const handleRemoveIteration = (idx: number) => {
        const newArray = arrayValue.filter((_: any, i: number) => i !== idx)
        handleFieldChange(currentPath, newArray)
      }

      return (
        <Box key={pathString} sx={{ marginY: 2, border: '1px solid #E0E0E0', padding: 2, borderRadius: 1 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 1 }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 'bold' }}>
              {key} ({arrayValue.length} iteration{arrayValue.length !== 1 ? 's' : ''})
            </Typography>
            <Button
              size="small"
              variant="outlined"
              onClick={handleAddIteration}
              disabled={fieldType === 'fixed-array' && fieldSchema?.maxItems && arrayValue.length >= fieldSchema.maxItems}
              startIcon={<span>+</span>}
            >
              {isSwitchArray ? 'Add Footprint' : 'Add Iteration'}
            </Button>
          </Box>
          {arrayValue.length === 0 ? (
            <Typography variant="body2" color="textSecondary">No iterations</Typography>
          ) : (
            arrayValue.map((item: any, idx: number) => (
              <Accordion key={`${pathString}-${idx}`} sx={{ marginBottom: 1 }}>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
                    <Typography variant="body2">
                      {isSwitchArray ? Object.keys(item)[0] : `Iteration ${idx + 1}`}
                    </Typography>
                    <IconButton
                      size="small"
                      onClick={(e) => {
                        e.stopPropagation()
                        handleRemoveIteration(idx)
                      }}
                      sx={{ marginRight: 1 }}
                    >
                      <span style={{ fontSize: '16px' }}>×</span>
                    </IconButton>
                  </Box>
                </AccordionSummary>
                <AccordionDetails>
                  <Box sx={{ paddingLeft: 2 }}>
                    {isSwitchArray ? (
                      // For switch arrays, item has ONE key (the selected option)
                      (() => {
                        const selectedOption = Object.keys(item)[0]
                        const selectedSchema = itemSchema?.options?.[selectedOption]?.schema
                        return renderField(
                          selectedOption,
                          selectedSchema || {},
                          item[selectedOption],
                          [...currentPath, idx.toString()]
                        )
                      })()
                    ) : isFootprintArray ? (
                      // For footprint arrays, render the single type that exists
                      Object.keys(item).map((itemKey) =>
                        renderField(
                          itemKey,
                          { type: 'array', fieldType: 'array', itemSchema: { value: { type: 'uint-32', fieldType: 'integer', min: 0, max: 4294967295 } } },
                          item[itemKey],
                          [...currentPath, idx.toString()]
                        )
                      )
                    ) : (
                      // For regular arrays, check if itemSchema describes a primitive item (render directly)
                      (() => {
                        const itemSchemaFieldType = itemSchema?.fieldType
                        // Primitive types - render as simple input
                        if (itemSchemaFieldType && ['integer', 'float', 'string', 'boolean', 'ipv4', 'ipv6', 'enum'].includes(itemSchemaFieldType)) {
                          const displayValue = item ?? itemSchema?.default ?? ''

                          if (itemSchemaFieldType === 'boolean') {
                            return (
                              <FormControlLabel
                                key={`${pathString}-${idx}`}
                                control={
                                  <Switch
                                    checked={Boolean(displayValue)}
                                    onChange={(e) => {
                                      const newArray = [...arrayValue]
                                      newArray[idx] = e.target.checked
                                      handleFieldChange(currentPath, newArray)
                                    }}
                                  />
                                }
                                label={`Value ${idx + 1}`}
                                sx={{ marginY: 1, display: 'block' }}
                              />
                            )
                          }

                          if (itemSchemaFieldType === 'enum' && Array.isArray(itemSchema?.options)) {
                            return (
                              <FormControl key={`${pathString}-${idx}`} fullWidth margin="normal" size="small">
                                <InputLabel>{`Value ${idx + 1}`}</InputLabel>
                                <Select
                                  value={displayValue}
                                  onChange={(e) => {
                                    const newArray = [...arrayValue]
                                    newArray[idx] = e.target.value
                                    handleFieldChange(currentPath, newArray)
                                  }}
                                  label={`Value ${idx + 1}`}
                                >
                                  {itemSchema.options.map((opt: string) => (
                                    <MenuItem key={opt} value={opt}>{opt}</MenuItem>
                                  ))}
                                </Select>
                              </FormControl>
                            )
                          }

                          // Number or text input
                          return (
                            <TextField
                              key={`${pathString}-${idx}`}
                              fullWidth
                              label={`Value ${idx + 1}`}
                              type={itemSchemaFieldType === 'integer' || itemSchemaFieldType === 'float' ? 'number' : 'text'}
                              value={displayValue}
                              onChange={(e) => {
                                let newValue: any = e.target.value
                                if (itemSchemaFieldType === 'integer') {
                                  const num = parseInt(e.target.value as string, 10)
                                  newValue = isNaN(num) ? 0 : num
                                } else if (itemSchemaFieldType === 'float') {
                                  const num = parseFloat(e.target.value as string)
                                  newValue = isNaN(num) ? 0.0 : num
                                }
                                const newArray = [...arrayValue]
                                newArray[idx] = newValue
                                handleFieldChange(currentPath, newArray)
                              }}
                              margin="normal"
                              size="small"
                              inputProps={{ min: itemSchema?.min, max: itemSchema?.max }}
                            />
                          )
                        }

                        // Complex object - render all fields (existing behavior)
                        return Object.keys(itemSchema)
                          .filter((itemKey) => !metadataKeys.includes(itemKey))
                          .map((itemKey) =>
                            renderField(itemKey, itemSchema[itemKey], item ? item[itemKey] : undefined, [...currentPath, idx.toString()])
                          )
                      })()
                     )}
                   </Box>
                 </AccordionDetails>
               </Accordion>
             ))
           )}

          {/* Footprint Type Selection Dialog */}
          {(isFootprintArray || isSwitchArray) && (
            <Dialog open={footprintTypeDialog} onClose={() => setFootprintTypeDialog(false)}>
              <DialogTitle>Select Type</DialogTitle>
              <DialogContent>
                <List>
                  {/* Use availableSwitchOptions when this is a switch array, otherwise fallback to footprintTypes */}
                  {(isSwitchArray ? availableSwitchOptions : footprintTypes).length === 0 ? (
                    <ListItemText primary="No available options" />
                  ) : (isSwitchArray ? availableSwitchOptions : footprintTypes).map((type) => (
                    <ListItemButton key={type} onClick={() => handleAddFootprintType(type)}>
                      <ListItemText primary={type} />
                    </ListItemButton>
                  ))}
                </List>
              </DialogContent>
            </Dialog>
          )}
        </Box>
      )
    }

    // Clone → Render enumeration values as nested objects with collapsible sections
    // CHECK THIS FIRST because fieldType might be 'object' even for clone fields
    if (fieldSchema?.type === 'clone' && fieldSchema?.fields && typeof fieldSchema.fields === 'object') {
      const cloneValue = value ?? {}
      const cloneOptions = fieldSchema.fields

      return (
        <Box key={pathString} sx={{ marginY: 2, border: '1px solid #E0E0E0', padding: 2, borderRadius: 1 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 'bold', marginBottom: 1 }}>
            {key}
          </Typography>
          {Object.keys(cloneOptions).map((optionKey) => {
            const optionSchema = cloneOptions[optionKey]
            const optionValue = cloneValue[optionKey] ?? {}

            return (
              <Accordion key={`${pathString}-${optionKey}`} sx={{ marginBottom: 1 }}>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography variant="body2">{optionKey}</Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Box sx={{ paddingLeft: 2 }}>
                    {optionSchema && typeof optionSchema === 'object' && optionSchema.fields ? (
                      Object.keys(optionSchema.fields)
                        .filter((nestedKey) => !metadataKeys.includes(nestedKey))
                        .map((nestedKey) =>
                          renderField(nestedKey, optionSchema.fields[nestedKey], optionValue[nestedKey], [...currentPath, optionKey])
                        )
                    ) : (
                      <Typography variant="body2" color="textSecondary">No fields available</Typography>
                    )}
                  </Box>
                </AccordionDetails>
              </Accordion>
            )
          })}
        </Box>
      )
    }

    // Object → Render nested fields in Accordion
    if (fieldType === 'object' && fieldSchema?.fields && typeof fieldSchema.fields === 'object') {
      const nestedValue = value ?? {}

      // Special handling for overlap structures
      const isOverlap = fieldSchema.type === 'overlap'

      return (
        <Accordion key={pathString} sx={{ marginY: 1 }}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="subtitle2" sx={{ fontWeight: 'bold' }}>{key}</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Box sx={{ paddingLeft: 2 }}>
              {Object.keys(fieldSchema.fields)
                .filter((nestedKey) => {
                  if (metadataKeys.includes(nestedKey)) return false

                  // Special handling for footprint structure: hide 'and' field when relation is 'or'
                  if (fieldSchema.type === 'footprint' && nestedKey === 'and') {
                    const relationValue = nestedValue['relation']
                    // Only show 'and' field when relation is 'and'
                    return relationValue === 'and'
                  }

                  // Check if this is a switch field with a selector
                  const fieldDef = fieldSchema.fields[nestedKey]
                  if (fieldDef?.type === 'switch' && fieldDef?.selector) {
                    // For overlap structures, check if selectorField is specified
                    if (isOverlap && fieldDef?.selectorField) {
                      // Find the selector field value in the current overlap value
                      const selectorValue = nestedValue[fieldDef.selectorField]

                      // Only show the switch fields, not the switch wrapper itself
                      // The switch will be handled by renderSwitchBasedOnSelector below
                      return false
                    }

                    // Extract enum name from selector (e.g., "httpflood.rules-status" -> "rules-status")
                    const selectorEnumName = fieldDef.selector.split('.').pop()

                    // Find corresponding enum field in schema
                    const enumField = Object.keys(fieldSchema.fields).find(k => {
                      const f = fieldSchema.fields[k]
                      return f?.fieldType === 'enum' && f?.type?.endsWith(selectorEnumName)
                    })

                    // Only show switch if the enum value is "changed"
                    if (enumField) {
                      const enumValue = nestedValue[enumField]
                      return enumValue === 'changed'
                    }
                  }

                  return true
                })
                .map((nestedKey) =>
                  renderField(nestedKey, fieldSchema.fields[nestedKey], nestedValue[nestedKey], currentPath)
                )}

              {/* Special rendering for overlap switches based on selector */}
              {isOverlap && Object.keys(fieldSchema.fields).map((nestedKey) => {
                const fieldDef = fieldSchema.fields[nestedKey]
                if (fieldDef?.type === 'switch' && fieldDef?.selectorField && fieldDef?.selector) {
                  const switchValue = nestedValue[nestedKey] ?? {}
                  const availableCases = Object.keys(fieldDef.fields || {})

                  // When selectorField matches the switch field name, the selected case is determined by which key exists in switchValue
                  let selectorValue: string | undefined
                  if (fieldDef.selectorField === nestedKey) {
                    // Merged selector/switch pattern - find which case is currently selected
                    selectorValue = availableCases.find(caseName => caseName in switchValue)

                    // Render a selector dropdown for choosing the case
                    if (!selectorValue && availableCases.length > 0) {
                      selectorValue = availableCases[0]
                    }
                  } else {
                    // Separate selector field
                    selectorValue = nestedValue[fieldDef.selectorField]
                  }

                  // Render the selected case's fields directly (not wrapped in switch accordion)
                  if (!selectorValue || !fieldDef.fields || !fieldDef.fields[selectorValue]) {
                    return null
                  }

                  // TypeScript type narrowing - store in const with explicit type
                  const selectedCase: string = selectorValue
                  const caseSchema = fieldDef.fields[selectedCase]
                  const caseValue = switchValue[selectedCase] ?? {}

                  // For merged pattern, render selector dropdown
                  const isMergedPattern = fieldDef.selectorField === nestedKey
                  const hasFields = caseSchema?.fields && Object.keys(caseSchema.fields).length > 0

                  // For merged pattern, always render (to show dropdown), but only show fields if they exist
                  if (isMergedPattern || hasFields) {
                      return (
                        <Box key={`${pathString}-${nestedKey}-case`} sx={{ marginTop: 2 }}>
                          {/* For merged pattern, show dropdown to select case */}
                          {isMergedPattern && availableCases.length > 1 && (
                            <FormControl fullWidth sx={{ marginBottom: 2 }}>
                              <InputLabel>{nestedKey}</InputLabel>
                              <Select
                                value={selectedCase}
                                label={nestedKey}
                                onChange={(e) => {
                                  const newCase = e.target.value
                                  // Switch to the new case
                                  const oldCase = selectedCase
                                  const newValue = { ...nestedValue }

                                  // Remove old case data
                                  if (oldCase && newValue[nestedKey]) {
                                    delete newValue[nestedKey][oldCase]
                                  }

                                  // Initialize new case with empty object
                                  if (!newValue[nestedKey]) {
                                    newValue[nestedKey] = {}
                                  }
                                  newValue[nestedKey][newCase] = {}

                                  handleFieldChange(currentPath, newValue)
                                }}
                              >
                                {availableCases.map((caseName) => (
                                  <MenuItem key={caseName} value={caseName}>
                                    {caseName}
                                  </MenuItem>
                                ))}
                              </Select>
                            </FormControl>
                          )}

                          {/* Only show fields section if case has fields */}
                          {hasFields && (
                            <>
                              <Typography variant="caption" color="textSecondary" sx={{ display: 'block', marginBottom: 1 }}>
                                {selectedCase} fields:
                              </Typography>
                              {Object.keys(caseSchema.fields)
                                .filter((caseFieldKey) => !metadataKeys.includes(caseFieldKey))
                                .map((caseFieldKey) =>
                                  renderField(
                                    caseFieldKey,
                                    caseSchema.fields[caseFieldKey],
                                    caseValue[caseFieldKey],
                                    [...currentPath, nestedKey, selectedCase]
                                  )
                                )}
                            </>
                          )}
                        </Box>
                      )
                  }
                }
                return null
              })}
            </Box>
          </AccordionDetails>
        </Accordion>
      )
    }

    // Switch → Render with selector and case fields
    if (fieldType === 'switch' && fieldSchema?.fields && typeof fieldSchema.fields === 'object') {
      const nestedValue = value ?? {}
      const selectorEnum = fieldSchema?.selector

      // Get the selector field from parent if needed, or use the current value's key as selector
      const selectedCase = Object.keys(nestedValue).length > 0 ? Object.keys(nestedValue)[0] : Object.keys(fieldSchema.fields)[0]
      const selectedCaseData = nestedValue[selectedCase] ?? {}

      return (
        <Accordion key={pathString} sx={{ marginY: 1 }}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="subtitle2" sx={{ fontWeight: 'bold' }}>{key}</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Box sx={{ paddingLeft: 2 }}>
              {/* Selector dropdown to choose case */}
              <FormControl fullWidth margin="normal" size="small">
                <InputLabel>Case</InputLabel>
                <Select
                  value={selectedCase || ''}
                  onChange={(e) => {
                    const newCase = e.target.value
                    // Initialize with proper structure based on schema
                    const caseSchema = fieldSchema.fields[newCase]
                    const newCaseData: any = {}

                    if (caseSchema?.fields) {
                      // Initialize nested fields with defaults
                      Object.keys(caseSchema.fields).forEach((fieldKey) => {
                        const fieldDef = caseSchema.fields[fieldKey]
                        if (fieldDef?.default !== undefined) {
                          newCaseData[fieldKey] = fieldDef.default
                        }
                      })
                    }

                    handleFieldChange(currentPath, { [newCase]: newCaseData })
                  }}
                  label="Case"
                >
                  {Object.keys(fieldSchema.fields).map((caseKey) => (
                    <MenuItem key={caseKey} value={caseKey}>{caseKey}</MenuItem>
                  ))}
                </Select>
              </FormControl>

              {/* Render fields for selected case */}
              {selectedCase && fieldSchema.fields[selectedCase]?.fields && (
                <Box sx={{ marginTop: 2, paddingLeft: 2 }}>
                  {Object.keys(fieldSchema.fields[selectedCase].fields)
                    .filter((nestedKey) => !metadataKeys.includes(nestedKey))
                    .map((nestedKey) =>
                      renderField(
                        nestedKey,
                        fieldSchema.fields[selectedCase].fields[nestedKey],
                        selectedCaseData[nestedKey],
                        [...currentPath, selectedCase]
                      )
                    )}
                </Box>
              )}
            </Box>
          </AccordionDetails>
        </Accordion>
      )
    }

    // Fallback: If value is an object and fieldSchema is an object with fields, render as object
    if (typeof value === 'object' && value !== null && !Array.isArray(value) &&
        fieldSchema && typeof fieldSchema === 'object' && fieldSchema.fields && fieldSchema.type !== 'clone') {
      const nestedValue = value
      return (
        <Accordion key={pathString} sx={{ marginY: 1 }}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="subtitle2" sx={{ fontWeight: 'bold' }}>{key}</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Box sx={{ paddingLeft: 2 }}>
              {Object.keys(fieldSchema.fields)
                .filter((nestedKey) => !metadataKeys.includes(nestedKey))
                .map((nestedKey) =>
                  renderField(nestedKey, fieldSchema.fields[nestedKey], nestedValue?.[nestedKey], currentPath)
                )}
            </Box>
          </AccordionDetails>
        </Accordion>
      )
    }

    // String (default) → Text input
    // Special handling for attack-id field - add randomize button
    if (key === 'attack-id') {
      return (
        <TextField
          key={pathString}
          fullWidth
          label={key}
          value={value}
          onChange={(e) => handleFieldChange(currentPath, e.target.value)}
          margin="normal"
          size="small"
          InputProps={{
            endAdornment: (
              <InputAdornment position="end">
                <Tooltip title="Generate random attack-id">
                  <IconButton
                    size="small"
                    onClick={() => {
                      const newAttackId = generateAttackId()
                      handleFieldChange(currentPath, newAttackId)
                    }}
                    edge="end"
                  >
                    <CasinoIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              </InputAdornment>
            ),
          }}
        />
      )
    }

    // Regular string field
    return (
      <TextField
        key={pathString}
        fullWidth
        label={key}
        value={value}
        onChange={(e) => handleFieldChange(currentPath, e.target.value)}
        margin="normal"
        size="small"
        inputProps={{ maxLength: fieldSchema?.maxLength }}
      />
    )
  }

  return (
    <Box>
      {Object.keys(schema || {}).map((key) => renderField(key, schema[key], (messageData || {})[key]))}
    </Box>
  )
}

export default IRPMessageForm
