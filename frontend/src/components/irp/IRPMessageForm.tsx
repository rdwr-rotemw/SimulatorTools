import React from 'react'
import {
    Accordion,
    AccordionDetails,
    AccordionSummary,
    Box,
    Button,
    Dialog,
    DialogContent,
    DialogTitle,
    FormControl,
    FormControlLabel,
    IconButton,
    InputAdornment,
    InputLabel,
    List,
    ListItemButton,
    ListItemText,
    MenuItem,
    Select,
    Switch,
    TextField,
    Tooltip,
    Typography,
} from '@mui/material'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import CasinoIcon from '@mui/icons-material/Casino'
import {generateAttackId} from '../../pages/IRPSenderPage'

interface IRPMessageFormProps {
    messageData: Record<string, any>
    schema: Record<string, any>
    onChange: (data: Record<string, any>) => void
    onValidationChange?: (isValid: boolean) => void
}

// ============================================================================
// SWITCH HELPER FUNCTIONS - Consolidated logic
// ============================================================================

/**
 * Check if a field definition is a switch type
 * Handles both type/fieldType and selector/discriminator variations
 */
const isSwitchField = (fieldDef: any): boolean => {
    if (!fieldDef) return false
    const isSwitch = fieldDef?.type === 'switch' || fieldDef?.fieldType === 'switch'
    const hasSelector = fieldDef?.selector || fieldDef?.discriminator
    return isSwitch && hasSelector
}

/**
 * Get available case names from a switch
 * Works with both options (top-level) and fields (nested) formats
 */
const getSwitchCases = (fieldDef: any): string[] => {
    if (!fieldDef) return []
    const caseMap = fieldDef.options || fieldDef.fields || {}
    return Object.keys(caseMap)
}

/**
 * Get the schema for a specific case within a switch
 * Handles both formats: {schema: {...}} and direct {...}
 */
const getCaseSchema = (fieldDef: any, caseName: string): any => {
    if (!fieldDef || !caseName) return {}

    // Try options first (top-level switches)
    if (fieldDef.options?.[caseName]) {
        const caseOption = fieldDef.options[caseName]
        return caseOption?.schema || caseOption
    }

    // Fall back to fields (nested switches)
    if (fieldDef.fields?.[caseName]) {
        return fieldDef.fields[caseName]
    }

    return {}
}

/**
 * Check if a schema represents a nested switch with metadata
 * These have _switchSelector, _switchCases fields at the schema root
 */
const isNestedSwitchWithMetadata = (fieldSchema: any): boolean => {
    // Metadata (_switchSelector/_switchCases) is stored at the schema root
    return Boolean(fieldSchema?._switchSelector && fieldSchema?._switchCases)
}

/**
 * Common metadata keys that should not be rendered as fields
 */
const METADATA_KEYS = ['type', 'fieldType', 'default', 'min', 'max', 'required', 'itemType', 'itemSchema',
    '_switchSelector', '_switchCases', '_selectedCase', 'discriminator', 'selector', 'options']

// ============================================================================

const IRPMessageForm: React.FC<IRPMessageFormProps> = ({messageData, schema, onChange, onValidationChange}) => {
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

        // Keys that represent switch-case wrappers and MUST NOT be flattened
        const SWITCH_CASE_KEYS = ['source', 'size', 'none', 'other', 'changed', 'unchanged']

        // Helper: recursively flatten struct-wrapper patterns like {tcp: {tcp: {...}}} -> {tcp: {...}}
        const flattenStructWrappers = (obj: any) => {
            if (!obj || typeof obj !== 'object') return

            if (Array.isArray(obj)) {
                obj.forEach(item => flattenStructWrappers(item))
                return
            }

            Object.keys(obj).forEach((key) => {
                const val = obj[key]
                if (val && typeof val === 'object' && !Array.isArray(val)) {
                    const innerKeys = Object.keys(val)
                    // Detect exact wrapper pattern: single inner key equals outer key
                    // Avoid flattening when the outer key is a known switch-case name
                    if (innerKeys.length === 1 && innerKeys[0] === key &&
                        !SWITCH_CASE_KEYS.includes(key) &&
                        val[innerKeys[0]] && typeof val[innerKeys[0]] === 'object') {
                        obj[key] = val[innerKeys[0]]
                        // Recurse into the unwrapped object
                        flattenStructWrappers(obj[key])
                    } else {
                        // Recurse into child
                        flattenStructWrappers(val)
                    }
                }
            })
        }

        // Flatten any struct wrappers across the new data to match backend expectations
        flattenStructWrappers(newData)

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

    // Validate all fields recursively
    const validateForm = React.useCallback((data: any, schemaObj: any): boolean => {
        if (!data || !schemaObj) return true

        const validateValue = (value: any, fieldSchema: any): boolean => {
            const fieldType = fieldSchema?.fieldType

            // Integer validation
            if (fieldType === 'integer') {
                const numValue = typeof value === 'number' ? value : 0
                const min = fieldSchema?.min
                const max = fieldSchema?.max
                if ((typeof min === 'number' && numValue < min) || (typeof max === 'number' && numValue > max)) {
                    return false
                }
            }

            // Float validation
            if (fieldType === 'float') {
                const numValue = typeof value === 'number' ? value : 0
                const min = fieldSchema?.min
                const max = fieldSchema?.max
                if ((typeof min === 'number' && numValue < min) || (typeof max === 'number' && numValue > max)) {
                    return false
                }
            }

            // String maxLength validation
            if (fieldType === 'string' || !fieldType) {
                const stringValue = typeof value === 'string' ? value : ''
                const maxLength = fieldSchema?.maxLength
                if (typeof maxLength === 'number' && stringValue.length > maxLength) {
                    return false
                }
            }

            // Array validation
            if ((fieldType === 'array' || fieldType === 'fixed-array') && Array.isArray(value)) {
                const itemSchema = fieldSchema?.itemSchema
                if (itemSchema) {
                    for (const item of value) {
                        if (!validateValue(item, itemSchema)) {
                            return false
                        }
                    }
                }
            }

            // Object validation
            if (fieldType === 'object' && fieldSchema?.fields && typeof value === 'object') {
                for (const key in fieldSchema.fields) {
                    if (!validateValue(value[key], fieldSchema.fields[key])) {
                        return false
                    }
                }
            }

            return true
        }

        // Validate all schema fields
        for (const key in schemaObj) {
            if (!validateValue(data[key], schemaObj[key])) {
                return false
            }
        }

        return true
    }, [])

    // Track previous validation state to avoid infinite loops
    const prevValidationRef = React.useRef<boolean | null>(null)

    // Notify parent of validation state whenever data changes
    React.useEffect(() => {
        if (onValidationChange) {
            const isValid = validateForm(messageData, schema)
            // Only call onValidationChange if the validation state has actually changed
            if (prevValidationRef.current !== isValid) {
                prevValidationRef.current = isValid
                onValidationChange(isValid)
            }
        }
    }, [messageData, schema, onValidationChange, validateForm])

    const renderField = (key: string, fieldSchema: any, value: any, path: string[] = []): React.ReactNode => {
        const currentPath = [...path, key]
        const pathString = currentPath.join('.')
        const fieldType = fieldSchema?.fieldType || 'string'

        // Handle null/undefined by using schema default when available
        if (value === null || value === undefined) {
            value = fieldSchema?.default ?? ''
        }

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
                        sx={{marginY: 1, display: 'block'}}
                    />

                    {/* Render conditional fields when boolean is true */}
                    {hasConditionalFields && boolValue && typeof value === 'object' && (
                        <Box sx={{
                            marginLeft: 4,
                            marginTop: 1,
                            marginBottom: 2,
                            paddingLeft: 2,
                            borderLeft: '2px solid #ddd'
                        }}>
                            {Object.keys(fieldSchema.fields).map((nestedKey) => {
                                const nestedFieldSchema = fieldSchema.fields[nestedKey]
                                const nestedValue = value[nestedKey]
                                return renderField(nestedKey, nestedFieldSchema, nestedValue, currentPath)
                            })}
                        </Box>
                    )}
                </Box>
            )
        }

        // Enum → Select
        if (fieldType === 'enum' && Array.isArray(fieldSchema?.options)) {
            const currentEnumValue = value ?? fieldSchema.default ?? fieldSchema.options[0] ?? ''

            const handleEnumChange = (newValue: string) => {
                handleFieldChange(currentPath, newValue)
            }

            return (
                <FormControl key={pathString} fullWidth margin="normal" size="small">
                    <InputLabel>{key}</InputLabel>
                    <Select
                        value={currentEnumValue}
                        onChange={(e) => handleEnumChange(e.target.value)}
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
            const numericValue = typeof value === 'number' ? value : 0

            return (
                <Box key={pathString} sx={{marginY: 2, border: '1px solid #E0E0E0', padding: 2, borderRadius: 1}}>
                    <Typography variant="subtitle2" sx={{fontWeight: 'bold', marginBottom: 1}}>
                        {key} (bitmap)
                    </Typography>
                    {fieldSchema.options.map((option: string, idx: number) => {
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
                                                newValue |= (1 << bitPosition)
                                            } else {
                                                newValue &= ~(1 << bitPosition)
                                            }
                                            handleFieldChange(currentPath, newValue)
                                        }}
                                    />
                                }
                                label={option}
                                sx={{display: 'block', marginY: 0.5}}
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
                    inputProps={{min: min, max: max}}
                />
            )
        }

        // Float → Number input
        if (fieldType === 'float') {
            const min = fieldSchema?.min
            const max = fieldSchema?.max
            const numValue = typeof value === 'number' ? value : 0
            const hasError = (typeof min === 'number' && numValue < min) || (typeof max === 'number' && numValue > max)

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
                    error={hasError}
                    inputProps={{step: 0.01, min: min, max: max}}
                    helperText={
                        hasError
                            ? `Must be between ${min ?? '-inf'} and ${max ?? 'inf'}`
                            : typeof min === 'number'
                                ? `Range: ${min} - ${max ?? 'max'}`
                                : ''
                    }
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
                if (fieldType === 'fixed-array' && fieldSchema?.maxItems && arrayValue.length >= fieldSchema.maxItems) {
                    return
                }

                if (isSwitchArray) {
                    const switchOptions = itemSchema?.options || {}
                    const availableOptions = Object.keys(switchOptions).filter((optionKey) => {
                        return !arrayValue.some((item: any) => Object.keys(item)[0] === optionKey)
                    })
                    setAvailableSwitchOptions(availableOptions)
                    setPendingFootprintPath(currentPath)
                    setFootprintTypeDialog(true)
                } else if (isFootprintArray) {
                    setPendingFootprintPath(currentPath)
                    setFootprintTypeDialog(true)
                } else {
                    let newItem: any = {}

                    const isPrimitiveItem = itemSchema?.fieldType && ['integer', 'float', 'string', 'boolean', 'ipv4', 'ipv6', 'enum'].includes(itemSchema.fieldType)

                    if (isPrimitiveItem) {
                        newItem = itemSchema?.default ?? 0
                    } else if (itemSchema && typeof itemSchema === 'object' && !Array.isArray(itemSchema)) {
                        Object.keys(itemSchema).forEach((k) => {
                            if (!METADATA_KEYS.includes(k)) {
                                if (k.toLowerCase().includes('url')) {
                                    newItem[k] = itemSchema[k]?.default ?? 'radware.com'
                                } else {
                                    newItem[k] = itemSchema[k]?.default ?? ''
                                }
                            }
                        })
                    }

                    if (itemSchema && typeof itemSchema === 'object' && 'port' in itemSchema) {
                        let maxPort = 0
                        arrayValue.forEach((item: any) => {
                            if (item && typeof item === 'object' && typeof item.port === 'number') {
                                maxPort = Math.max(maxPort, item.port)
                            }
                        })
                        newItem.port = maxPort + 1
                    }

                    if (itemSchema && typeof itemSchema === 'object' && 'policy-name' in itemSchema) {
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
                const newItem = {[type]: []}
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
                <Box key={pathString} sx={{marginY: 2, border: '1px solid #E0E0E0', padding: 2, borderRadius: 1}}>
                    <Box sx={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 1}}>
                        <Typography variant="subtitle2" sx={{fontWeight: 'bold'}}>
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
                            <Accordion key={`${pathString}-${idx}`} sx={{marginBottom: 1}}>
                                <AccordionSummary expandIcon={<ExpandMoreIcon/>}>
                                    <Typography variant="body2">
                                        {isSwitchArray ? Object.keys(item)[0] : `Iteration ${idx + 1}`}
                                    </Typography>
                                </AccordionSummary>
                                <AccordionDetails>
                                    <Box sx={{paddingLeft: 2}}>
                                        <Box sx={{display: 'flex', justifyContent: 'flex-end', marginBottom: 1}}>
                                            <Button
                                                size="small"
                                                color="error"
                                                onClick={() => handleRemoveIteration(idx)}
                                            >
                                                Remove
                                            </Button>
                                        </Box>

                                        {isSwitchArray ? (
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
                                            Object.keys(item).map((itemKey) =>
                                                renderField(
                                                    itemKey,
                                                    {
                                                        type: 'array',
                                                        fieldType: 'array',
                                                        itemSchema: {
                                                            value: {
                                                                type: 'uint-32',
                                                                fieldType: 'integer',
                                                                min: 0,
                                                                max: 4294967295
                                                            }
                                                        }
                                                    },
                                                    item[itemKey],
                                                    [...currentPath, idx.toString()]
                                                )
                                            )
                                        ) : (
                                            (() => {
                                                const itemSchemaFieldType = itemSchema?.fieldType
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
                                                                sx={{marginY: 1, display: 'block'}}
                                                            />
                                                        )
                                                    }

                                                    if (itemSchemaFieldType === 'enum' && Array.isArray(itemSchema?.options)) {
                                                        return (
                                                            <FormControl key={`${pathString}-${idx}`} fullWidth
                                                                         margin="normal" size="small">
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

                                                    const numValue = typeof displayValue === 'number' ? displayValue : 0
                                                    const hasItemError = (itemSchemaFieldType === 'integer' || itemSchemaFieldType === 'float') &&
                                                        ((typeof itemSchema?.min === 'number' && numValue < itemSchema.min) ||
                                                            (typeof itemSchema?.max === 'number' && numValue > itemSchema.max))

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
                                                            error={hasItemError}
                                                            inputProps={{
                                                                min: itemSchema?.min,
                                                                max: itemSchema?.max,
                                                                step: itemSchemaFieldType === 'float' ? 0.01 : undefined
                                                            }}
                                                            helperText={
                                                                hasItemError
                                                                    ? `Must be between ${itemSchema?.min ?? '-inf'} and ${itemSchema?.max ?? 'inf'}`
                                                                    : typeof itemSchema?.min === 'number'
                                                                        ? `Range: ${itemSchema.min} - ${itemSchema?.max ?? 'max'}`
                                                                        : undefined
                                                            }
                                                        />
                                                    )
                                                }

                                                return Object.keys(itemSchema)
                                                    .filter((itemKey) => !METADATA_KEYS.includes(itemKey))
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

                    {(isFootprintArray || isSwitchArray) && (
                        <Dialog open={footprintTypeDialog} onClose={() => setFootprintTypeDialog(false)}>
                            <DialogTitle>Select Type</DialogTitle>
                            <DialogContent>
                                <List>
                                    {(isSwitchArray ? availableSwitchOptions : footprintTypes).length === 0 ? (
                                        <ListItemText primary="No available options"/>
                                    ) : (isSwitchArray ? availableSwitchOptions : footprintTypes).map((type) => (
                                        <ListItemButton key={type} onClick={() => handleAddFootprintType(type)}>
                                            <ListItemText primary={type}/>
                                        </ListItemButton>
                                    ))}
                                </List>
                            </DialogContent>
                        </Dialog>
                    )}
                </Box>
            )
        }

        if (isNestedSwitchWithMetadata(fieldSchema)) {
            const nestedValue = value ?? {}
            const switchCases = fieldSchema._switchCases
            const selectedCase = fieldSchema._selectedCase || Object.keys(switchCases)[0]

            const currentSelectedCase = Object.keys(switchCases).find(caseName =>
                nestedValue[caseName] !== undefined
            ) || selectedCase


            const caseNames = Object.keys(switchCases).filter(name =>
                switchCases[name].type !== 'nil' && switchCases[name].type !== 'error'
            )

            return (
                <Box key={pathString} sx={{marginY: 2, border: '1px solid #E0E0E0', padding: 2, borderRadius: 1}}>
                    <Typography variant="subtitle2" sx={{fontWeight: 'bold', marginBottom: 2}}>{key}</Typography>

                    <FormControl fullWidth sx={{marginBottom: 2}}>
                        <InputLabel>Select Case</InputLabel>
                        <Select
                            value={currentSelectedCase}
                            label="Select Case"
                            onChange={(e) => {
                                const newCase = e.target.value
                                const newCaseSchema = switchCases[newCase]

                                const initializeFromSchema = (schema: any, fieldName?: string): any => {
                                    if (!schema) return {}

                                    if (schema.fieldType === 'array' || schema.type === 'array') {
                                        return []
                                    }

                                    if (schema.fieldType === 'integer' || schema.fieldType === 'float') {
                                        return schema.default ?? 0
                                    }

                                    if (schema.fieldType === 'boolean') {
                                        return schema.default ?? false
                                    }

                                    if (schema.fieldType === 'string' || schema.fieldType === 'ipv4' || schema.fieldType === 'ipv6') {
                                        if (fieldName && fieldName.toLowerCase().includes('url')) {
                                            return schema.default ?? 'radware.com'
                                        }
                                        return schema.default ?? ''
                                    }

                                    if (schema.fields && typeof schema.fields === 'object') {
                                        const obj: Record<string, any> = {}
                                        Object.keys(schema.fields)
                                            .filter(k => !METADATA_KEYS.includes(k))
                                            .forEach(fieldKey => {
                                                obj[fieldKey] = initializeFromSchema(schema.fields[fieldKey], fieldKey)
                                            })
                                        return obj
                                    }

                                    return {}
                                }

                                const newValue: Record<string, any> = {}
                                // Handle direct field types (array, integer, etc.) without .fields
                                // and fall back to fields-based initialization
                                // when appropriate.
                                if (newCaseSchema && typeof newCaseSchema === 'object') {
                                    // Initialize container
                                    // If schema directly describes a primitive/array type, initialize accordingly
                                    if (newCaseSchema.fieldType && newCaseSchema.fieldType !== 'object') {
                                        if (newCaseSchema.fieldType === 'array' || newCaseSchema.type === 'array') {
                                            newValue[newCase] = []
                                        } else if (newCaseSchema.fieldType === 'integer' || newCaseSchema.fieldType === 'float') {
                                            newValue[newCase] = newCaseSchema.default ?? 0
                                        } else if (newCaseSchema.fieldType === 'boolean') {
                                            newValue[newCase] = newCaseSchema.default ?? false
                                        } else {
                                            newValue[newCase] = newCaseSchema.default ?? ''
                                        }
                                    } else if (newCaseSchema.fields && Object.keys(newCaseSchema.fields).length > 0) {
                                        const caseFieldKeys = Object.keys(newCaseSchema.fields).filter(k => !METADATA_KEYS.includes(k))

                                        if (caseFieldKeys.length === 1 && caseFieldKeys[0] === newCase) {
                                            newValue[newCase] = initializeFromSchema(newCaseSchema.fields[newCase])
                                        } else {
                                            newValue[newCase] = {}
                                            caseFieldKeys.forEach(fieldKey => {
                                                newValue[newCase][fieldKey] = initializeFromSchema(newCaseSchema.fields[fieldKey])
                                            })
                                        }
                                    } else {
                                        newValue[newCase] = {}
                                    }
                                } else {
                                    newValue[newCase] = {}
                                }

                                handleFieldChange(currentPath, newValue)
                            }}
                        >
                            {caseNames.map((caseName) => (
                                <MenuItem key={caseName} value={caseName}>
                                    {caseName}
                                </MenuItem>
                            ))}
                        </Select>
                    </FormControl>

                    {(() => {
                        if (!currentSelectedCase || !switchCases[currentSelectedCase]) {
                            return null
                        }

                        const caseSchema = switchCases[currentSelectedCase]

                        // Handle direct field types (array, integer, etc.) without .fields
                        if (caseSchema.fieldType && caseSchema.fieldType !== 'object') {
                            return (
                                <Box sx={{paddingLeft: 2}}>
                                    {renderField(
                                        currentSelectedCase,
                                        caseSchema,
                                        nestedValue[currentSelectedCase],
                                        currentPath
                                    )}
                                </Box>
                            )
                        }

                        // Handle object types with .fields
                        if (!caseSchema.fields) {
                            return null
                        }

                        const caseFields = Object.keys(caseSchema.fields)
                            .filter((fieldKey) => !METADATA_KEYS.includes(fieldKey))

                        if (caseFields.length === 0) {
                            return null
                        }

                        return (
                            <Box sx={{paddingLeft: 2}}>
                                {caseFields.map((fieldKey) => {
                                    const fieldValue = fieldKey === currentSelectedCase
                                        ? nestedValue[currentSelectedCase]
                                        : nestedValue[currentSelectedCase]?.[fieldKey]

                                    const fieldPath = [...currentPath, currentSelectedCase]

                                    return renderField(
                                        fieldKey,
                                        caseSchema.fields[fieldKey],
                                        fieldValue,
                                        fieldPath
                                    )
                                })}
                            </Box>
                        )
                    })()}
                </Box>
            )
        }

        // Clone → Render enumeration values as nested objects with collapsible sections
        if (fieldSchema?.type === 'clone' && fieldSchema?.fields && typeof fieldSchema.fields === 'object') {
            const cloneValue = value ?? {}
            const cloneOptions = fieldSchema.fields

            return (
                <Box key={pathString} sx={{marginY: 2, border: '1px solid #E0E0E0', padding: 2, borderRadius: 1}}>
                    <Typography variant="subtitle2" sx={{fontWeight: 'bold', marginBottom: 1}}>
                        {key}
                    </Typography>
                    {Object.keys(cloneOptions).map((optionKey) => {
                        const optionSchema = cloneOptions[optionKey]
                        const optionValue = cloneValue[optionKey] ?? {}

                        return (
                            <Accordion key={`${pathString}-${optionKey}`} sx={{marginBottom: 1}}>
                                <AccordionSummary expandIcon={<ExpandMoreIcon/>}>
                                    <Typography variant="body2">{optionKey}</Typography>
                                </AccordionSummary>
                                <AccordionDetails>
                                    <Box sx={{paddingLeft: 2}}>
                                        {optionSchema && typeof optionSchema === 'object' && optionSchema.fields ? (
                                            Object.keys(optionSchema.fields)
                                                .filter((nestedKey) => !METADATA_KEYS.includes(nestedKey))
                                                .map((nestedKey) =>
                                                    renderField(nestedKey, optionSchema.fields[nestedKey], optionValue[nestedKey], [...currentPath, optionKey])
                                                )
                                        ) : (
                                            <Typography variant="body2" color="textSecondary">No fields
                                                available</Typography>
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
            const isOverlap = fieldSchema.type === 'overlap'

            return (
                <Accordion key={pathString} sx={{marginY: 1}}>
                    <AccordionSummary expandIcon={<ExpandMoreIcon/>}>
                        <Typography variant="subtitle2" sx={{fontWeight: 'bold'}}>{key}</Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                        <Box sx={{paddingLeft: 2}}>
                            {Object.keys(fieldSchema.fields)
                                .filter((nestedKey) => {
                                    if (METADATA_KEYS.includes(nestedKey)) return false

                                    if (fieldSchema.type === 'footprint' && nestedKey === 'and') {
                                        const relationValue = nestedValue['relation']
                                        return relationValue === 'and'
                                    }

                                    // Hide switch fields from normal rendering (handled by overlap special renderer below)
                                    const fieldDef = fieldSchema.fields[nestedKey]
                                    if (isSwitchField(fieldDef)) {
                                        if (isOverlap && fieldDef?.selectorField) {
                                            return false  // Hidden, rendered separately below
                                        }
                                    }

                                    return true
                                })
                                .map((nestedKey) =>
                                    renderField(nestedKey, fieldSchema.fields[nestedKey], nestedValue[nestedKey], currentPath)
                                )}

                            {/* SPECIAL OVERLAP SWITCH RENDERING - handles top-level switches with selector fields */}
                            {isOverlap && Object.keys(fieldSchema.fields).map((nestedKey) => {
                                const fieldDef = fieldSchema.fields[nestedKey]
                                if (!isSwitchField(fieldDef) || !fieldDef?.selectorField) {
                                    return null
                                }

                                const switchValue = nestedValue[nestedKey] ?? {}
                                const availableCases = getSwitchCases(fieldDef)
                                const selectorFieldValue = nestedValue[fieldDef.selectorField]

                                if (!selectorFieldValue || !availableCases.includes(selectorFieldValue)) {
                                    return null
                                }

                                const selectedCase = selectorFieldValue
                                const caseSchema = getCaseSchema(fieldDef, selectedCase)
                                const caseValue = switchValue[selectedCase] ?? {}
                                const hasFields = caseSchema?.fields && Object.keys(caseSchema.fields).length > 0

                                if (!hasFields) {
                                    return null
                                }

                                // CHECK: Does this case have nested switch metadata?
                                const hasNestedSwitch = isNestedSwitchWithMetadata(caseSchema)

                                if (hasNestedSwitch) {
                                    // Initialize nested switch data if not wrapped
                                    let switchData: any = caseValue
                                    const switchCases = caseSchema._switchCases || {}
                                    const selectedInnerCase = caseSchema._selectedCase || Object.keys(switchCases)[0]

                                    // Check if data is already wrapped with a case (e.g., {"source": {...}})
                                    const hasValidCase = Object.keys(switchCases).some(caseName =>
                                        caseValue && typeof caseValue === 'object' && caseName in caseValue
                                    )

                                    if (!hasValidCase && selectedInnerCase) {
                                        // Data is not wrapped - wrap it with the default/selected case
                                        switchData = {[selectedInnerCase]: caseValue}
                                    }

                                    // Render as nested switch with dropdown using existing handler
                                    return renderField(
                                        selectedCase,
                                        caseSchema,
                                        switchData,
                                        [...currentPath, nestedKey]
                                    )
                                }

                                // Normal case: render fields directly
                                return (
                                    <Box key={`${pathString}-${nestedKey}-case`} sx={{marginTop: 2}}>
                                        {Object.keys(caseSchema.fields)
                                            .filter((caseFieldKey) => !METADATA_KEYS.includes(caseFieldKey))
                                            .map((caseFieldKey) =>
                                                renderField(
                                                    caseFieldKey,
                                                    caseSchema.fields[caseFieldKey],
                                                    caseValue[caseFieldKey],
                                                    [...currentPath, nestedKey, selectedCase]
                                                )
                                            )}
                                    </Box>
                                )
                            })}
                        </Box>
                    </AccordionDetails>
                </Accordion>
            )
        }

        // Switch → Generic switch rendering (for non-overlap switches)
        if (isSwitchField(fieldSchema)) {
            const nestedValue = value ?? {}
            const availableCases = getSwitchCases(fieldSchema)

            const getDefaultCase = () => {
                return availableCases.find(caseName => {
                    const caseSchema = getCaseSchema(fieldSchema, caseName)
                    return caseSchema?.type !== 'nil' && caseSchema?.type !== 'error'
                }) || availableCases[0]
            }

            const selectedCase = Object.keys(nestedValue).length > 0
                ? Object.keys(nestedValue)[0]
                : getDefaultCase()
            const selectedCaseData = nestedValue[selectedCase] ?? {}

            return (
                <Accordion key={pathString} sx={{marginY: 1}}>
                    <AccordionSummary expandIcon={<ExpandMoreIcon/>}>
                        <Typography variant="subtitle2" sx={{fontWeight: 'bold'}}>{key}</Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                        <Box sx={{paddingLeft: 2}}>
                            <FormControl fullWidth margin="normal" size="small">
                                <InputLabel>Case</InputLabel>
                                <Select
                                    value={selectedCase || ''}
                                    onChange={(e) => {
                                        const newCase = e.target.value as string
                                        const caseSchema = getCaseSchema(fieldSchema, newCase)
                                        const newCaseData: any = {}

                                        if (caseSchema?.fields) {
                                            Object.keys(caseSchema.fields).forEach((fieldKey) => {
                                                const fieldDef = caseSchema.fields[fieldKey]
                                                if (fieldDef?.default !== undefined) {
                                                    newCaseData[fieldKey] = fieldDef.default
                                                }
                                            })
                                        }

                                        handleFieldChange(currentPath, {[newCase]: newCaseData})
                                    }}
                                    label="Case"
                                >
                                    {availableCases.map((caseKey) => (
                                        <MenuItem key={caseKey} value={caseKey}>{caseKey}</MenuItem>
                                    ))}
                                </Select>
                            </FormControl>

                            {selectedCase && (() => {
                                const caseSchema = getCaseSchema(fieldSchema, selectedCase)
                                return caseSchema?.fields && (
                                    <Box sx={{marginTop: 2, paddingLeft: 2}}>
                                        {Object.keys(caseSchema.fields)
                                            .filter((nestedKey) => !METADATA_KEYS.includes(nestedKey))
                                            .map((nestedKey) =>
                                                renderField(
                                                    nestedKey,
                                                    caseSchema.fields[nestedKey],
                                                    selectedCaseData[nestedKey],
                                                    [...currentPath, selectedCase]
                                                )
                                            )}
                                    </Box>
                                )
                            })()}
                        </Box>
                    </AccordionDetails>
                </Accordion>
            )
        }

        // Fallback: generic object rendering
        if (typeof value === 'object' && value !== null && !Array.isArray(value) &&
            fieldSchema && typeof fieldSchema === 'object' && fieldSchema.fields && fieldSchema.type !== 'clone') {
            const nestedValue = value
            return (
                <Accordion key={pathString} sx={{marginY: 1}}>
                    <AccordionSummary expandIcon={<ExpandMoreIcon/>}>
                        <Typography variant="subtitle2" sx={{fontWeight: 'bold'}}>{key}</Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                        <Box sx={{paddingLeft: 2}}>
                            {Object.keys(fieldSchema.fields)
                                .filter((nestedKey) => !METADATA_KEYS.includes(nestedKey))
                                .map((nestedKey) =>
                                    renderField(nestedKey, fieldSchema.fields[nestedKey], nestedValue?.[nestedKey], [...currentPath, key])
                                )}
                        </Box>
                    </AccordionDetails>
                </Accordion>
            )
        }

        // String (default) → Text input
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
                                        <CasinoIcon fontSize="small"/>
                                    </IconButton>
                                </Tooltip>
                            </InputAdornment>
                        ),
                    }}
                />
            )
        }

        // Regular string field
        const maxLength = fieldSchema?.maxLength
        const stringValue = typeof value === 'string' ? value : ''
        const hasLengthError = typeof maxLength === 'number' && stringValue.length > maxLength

        return (
            <TextField
                key={pathString}
                fullWidth
                label={key}
                value={value}
                onChange={(e) => handleFieldChange(currentPath, e.target.value)}
                margin="normal"
                size="small"
                error={hasLengthError}
                helperText={
                    hasLengthError
                        ? `Maximum length is ${maxLength} characters (current: ${stringValue.length})`
                        : typeof maxLength === 'number'
                            ? `Max length: ${maxLength}`
                            : ''
                }
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
