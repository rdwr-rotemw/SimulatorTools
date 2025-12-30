import React, {useEffect, useState} from 'react'
import {useNavigate, useSearchParams} from 'react-router-dom'
import {
    Alert,
    Box,
    Button,
    CircularProgress,
    Collapse,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    FormControl,
    IconButton,
    InputLabel,
    List,
    ListItem,
    ListItemButton,
    ListItemText,
    MenuItem,
    Paper,
    Select,
    Snackbar,
    TextField,
    Tooltip,
    Typography,
} from '@mui/material'
import SendIcon from '@mui/icons-material/Send'
import AddIcon from '@mui/icons-material/Add'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import ExpandLessIcon from '@mui/icons-material/ExpandLess'
import DeleteIcon from '@mui/icons-material/Delete'
import CasinoIcon from '@mui/icons-material/Casino'
import LoopIcon from '@mui/icons-material/Loop'
import StopIcon from '@mui/icons-material/Stop'
import ScienceIcon from '@mui/icons-material/Science'
import UnfoldMoreIcon from '@mui/icons-material/UnfoldMore'
import UnfoldLessIcon from '@mui/icons-material/UnfoldLess'
import UploadFileIcon from '@mui/icons-material/UploadFile'
import { IRPPcapAnalysisResponse } from '../api/services/irpSchema.service'
import Checkbox from '@mui/material/Checkbox'

import Layout from '../components/common/Layout'
import useCCStore from '../store/ccStore'
import useLoopStore from '../store/useLoopStore'
import useFormStore from '../store/useFormStore'
import useAuthStore from '../store/authStore'
import {irpSchemaService, SchemaMessage} from '../api/services/irpSchema.service'
import IRPMessageForm from '../components/irp/IRPMessageForm'

// ============================================================================
// CONSOLIDATED METADATA & RANDOMIZATION HELPERS
// ============================================================================

/**
 * Comprehensive metadata keys that should NEVER be treated as actual fields
 * Must match the list in IRPMessageForm.tsx
 */
const METADATA_KEYS = [
    'type', 'fieldType', 'default', 'min', 'max', 'required', 'itemType', 'itemSchema',
    '_switchSelector', '_switchCases', '_selectedCase', 'discriminator', 'selector', 'options'
]

/**
 * Check if a key is metadata (should not be randomized/rendered as data)
 */
const isMetadataKey = (key: string): boolean => {
    return METADATA_KEYS.includes(key) || key.startsWith('_')
}

/**
 * Get non-metadata keys from an object safely
 * Prevents accidentally treating schema metadata as data fields
 */
const getNonMetadataKeys = (obj: any): string[] => {
    if (!obj || typeof obj !== 'object') return []
    return Object.keys(obj).filter(key => !isMetadataKey(key))
}

// Helper functions to support switch schemas in two formats (top-level options or nested fields)
/**
 * Get available case names from a switch
 * Works with both options (top-level) and fields (nested) formats
 */
const getSwitchCases = (fieldDef: any): string[] => {
    if (!fieldDef) return []
    const caseMap = fieldDef.options || fieldDef.fields || {}
    return getNonMetadataKeys(caseMap)
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

// Utility function to generate random data based on schema
// Schema-driven recursion: Uses schema to understand and randomize all nested types
function generateRandomData(schema: Record<string, any>, currentData?: Record<string, any>): Record<string, any> {
    const randomizeValue = (fieldSchema: any, currentValue?: any, fieldKey?: string, iterationIndex?: number): any => {

        if (!fieldSchema) return currentValue ?? ''

        const fieldType = fieldSchema?.fieldType || fieldSchema?.type || 'string'

        // Special case: policy-name field
        // If in an array iteration (iterationIndex provided), increment: pol1, pol2, pol3...
        // Otherwise, random: pol1-pol30
        if (fieldKey === 'policy-name' && fieldType === 'string') {
            if (typeof iterationIndex === 'number') {
                const policyNumber = iterationIndex + 1
                return `pol${policyNumber}`
            } else {
                const policyNumber = Math.floor(Math.random() * 30) + 1
                return `pol${policyNumber}`
            }
        }

        // Special case: attack-id field should NOT be randomized by general randomize
        if (fieldKey === 'attack-id' && fieldType === 'string') {
            return currentValue ?? `0-${Math.floor(Date.now() / 1000)}`
        }

        // Primitive types - return early
        if (fieldType === 'integer') {
            let min = fieldSchema?.min ?? 0
            let max = fieldSchema?.max ?? 1000

            if (fieldSchema?.type && (fieldSchema.type.includes('uint-64') || fieldSchema.type.includes('int-64'))) {
                if (fieldSchema?.min === undefined) min = 0
                if (fieldSchema?.max === undefined) max = 9223372036854775807
            }

            if (max > 1000000) {
                const maxDigits = Math.floor(Math.log10(max)) + 1
                const minDigits = Math.max(1, Math.floor(Math.log10(min)) + 1)
                const digits = Math.floor(Math.random() * (maxDigits - minDigits + 1)) + minDigits

                let result
                if (digits === 1) {
                    result = Math.floor(Math.random() * 10) + min
                } else {
                    const lowerBound = Math.pow(10, digits - 1)
                    const upperBound = Math.min(Math.pow(10, digits) - 1, max)
                    result = Math.floor(Math.random() * (upperBound - lowerBound + 1)) + lowerBound
                }

                return Math.min(result, max)
            }

            return Math.floor(Math.random() * (max - min + 1)) + min
        }
        if (fieldType === 'float') {
            const beforeDecimal = Math.floor(Math.random() * 90) + 10
            const afterDecimal = Math.floor(Math.random() * 100)
            return parseFloat(`${beforeDecimal}.${afterDecimal.toString().padStart(2, '0')}`)
        }
        if (fieldType === 'boolean') {
            const hasConditionalFields = fieldSchema?.fields && Object.keys(fieldSchema.fields).length > 0

            if (hasConditionalFields) {
                const isCurrentlyEnabled = currentValue && typeof currentValue === 'object'

                if (isCurrentlyEnabled) {
                    const result: any = {}
                    Object.keys(fieldSchema.fields).forEach(key => {
                        result[key] = randomizeValue(fieldSchema.fields[key], currentValue?.[key], key)
                    })
                    return result
                } else {
                    return currentValue !== undefined ? currentValue : false
                }
            }

            return Math.random() > 0.5
        }
        if (fieldType === 'enum' && Array.isArray(fieldSchema?.options)) {
            if (currentValue !== undefined && currentValue !== null && fieldSchema.options.includes(currentValue)) {
                return currentValue
            }
            return fieldSchema.options[Math.floor(Math.random() * fieldSchema.options.length)]
        }
        if (fieldType === 'bitmap' && Array.isArray(fieldSchema?.options)) {
            // Generate random bitmap by randomly selecting flags
            const maxBits = fieldSchema.options.length
            let bitmapValue = 0

            // Randomly set 1-3 bits
            const numBitsToSet = Math.floor(Math.random() * 3) + 1
            for (let i = 0; i < numBitsToSet; i++) {
                const bitIndex = Math.floor(Math.random() * maxBits)
                bitmapValue |= (1 << bitIndex)
            }

            return bitmapValue
        }
        if (fieldType === 'ipv4') {
            return `${Math.floor(Math.random() * 256)}.${Math.floor(Math.random() * 256)}.${Math.floor(Math.random() * 256)}.${Math.floor(Math.random() * 256)}`
        }
        if (fieldType === 'ipv6') {
            return Array.from({length: 8}, () => Math.floor(Math.random() * 0xffff).toString(16)).join(':')
        }
        if (fieldType === 'string') {
            if (fieldKey && fieldKey.toLowerCase().includes('url')) {
                return 'https://radware.com'
            }
            if (fieldKey && (fieldKey.toLowerCase().includes('fqdn') || fieldKey.toLowerCase().includes('domain'))) {
                const tlds = ['.com', '.org', '.net', '.io', '.co', '.info', '.biz']
                const randomTld = tlds[Math.floor(Math.random() * tlds.length)]
                const randomDomain = Math.random().toString(36).substring(2, 10)
                return `${randomDomain}${randomTld}`
            }
            return Math.random().toString(36).substring(2, 12)
        }

        // ========================================================================
        // ARRAY HANDLING - CONSOLIDATED WITH SAFEGUARDS
        // ========================================================================
        if (fieldType === 'array' || fieldType === 'fixed-array') {
            const itemSchema = fieldSchema?.itemSchema
            const existingArray = Array.isArray(currentValue) ? currentValue : []

            // Special handling for footprint-values arrays
            const isFootprintValuesArray = itemSchema?.discriminator === 'vsecure.footprint-types'
            if (isFootprintValuesArray && existingArray.length === 0) {
                const footprintOptions = itemSchema?.options ? Object.keys(itemSchema.options) : []
                if (footprintOptions.length > 0) {
                    const randomFootprintType = footprintOptions[Math.floor(Math.random() * footprintOptions.length)]
                    const footprintOption = itemSchema.options[randomFootprintType]
                    const footprintSchema = footprintOption?.schema

                    const footprintItem: any = {[randomFootprintType]: []}

                    if (footprintSchema) {
                        const itemType = footprintSchema.itemType || 'uint-32'
                        const nestedItemSchema = footprintSchema.itemSchema

                        let randomValue: any
                        if (nestedItemSchema) {
                            randomValue = randomizeValue(nestedItemSchema, undefined, randomFootprintType)
                        } else if (itemType === 'string') {
                            randomValue = Math.random().toString(36).substring(2, 12)
                        } else {
                            randomValue = Math.floor(Math.random() * 65535)
                        }

                        footprintItem[randomFootprintType] = [randomValue]
                    }

                    return [footprintItem]
                }
            }

            // PRESERVE EXISTING ITERATIONS - Map and randomize each one
            if (existingArray.length > 0) {
                return existingArray.map((item: any, itemIndex: number) => {
                    // Switch array items - preserve option, randomize content
                    if (itemSchema?.fieldType === 'switch' && (itemSchema?.options || itemSchema?.fields) && typeof item === 'object' && item !== null) {
                        const selectedOption = Object.keys(item)[0]
                        const cases = getSwitchCases(itemSchema)
                        if (selectedOption && cases.includes(selectedOption)) {
                            const optionSchema = getCaseSchema(itemSchema, selectedOption)
                            const currentOptionValue = item[selectedOption]
                            return {[selectedOption]: randomizeValue(optionSchema, currentOptionValue, selectedOption, itemIndex)}
                        }
                        return item
                    }

                    // Primitive item types - randomize directly
                    if (itemSchema?.fieldType && !['object', 'clone', 'switch'].includes(itemSchema.fieldType)) {
                        return randomizeValue(itemSchema, item, fieldKey, itemIndex)
                    }

                    // Complex object items - randomize fields using non-metadata keys
                    const result: Record<string, any> = {}
                    const fieldKeys = getNonMetadataKeys(itemSchema || {})

                    fieldKeys.forEach((key) => {
                        const fieldDef = itemSchema[key]
                        const currentFieldValue = (typeof item === 'object' && item !== null) ? item[key] : undefined

                        // Special: preserve port, randomize others
                        if (key === 'port' && typeof currentFieldValue === 'number') {
                            result[key] = currentFieldValue
                        } else {
                            result[key] = randomizeValue(fieldDef, currentFieldValue, key, itemIndex)
                        }
                    })

                    return result
                })
            }

            // EMPTY ARRAY - Create 1-2 random items (only if no existing data)
            const arraySize = Math.floor(Math.random() * 2) + 1
            return Array.from({length: arraySize}, (_, index) => {
                // Primitive items
                if (itemSchema?.fieldType && !['object', 'clone', 'switch'].includes(itemSchema.fieldType)) {
                    return randomizeValue(itemSchema, undefined, fieldKey, index)
                }

                // Complex object items
                const result: Record<string, any> = {}
                const fieldKeys = getNonMetadataKeys(itemSchema || {})

                fieldKeys.forEach((key) => {
                    if (key === 'port' && itemSchema[key]?.fieldType === 'integer') {
                        result[key] = index + 1
                    } else {
                        result[key] = randomizeValue(itemSchema[key], undefined, key, index)
                    }
                })

                return result
            })
        }

        // ========================================================================
        // SWITCH HANDLING
        // ========================================================================
        if ((fieldType === 'switch' || fieldSchema?.type === 'switch') && (fieldSchema?.options || fieldSchema?.fields)) {
            const allCases = getSwitchCases(fieldSchema)

            if (allCases.length === 0) {
                return currentValue || {}
            }

            // Detect currently selected case from currentValue
            // If this switch has selectorField, preserve the current selection
            // (don't pick random - the selector controls which case to use)
            let selectedCase: string | null = null
            if (fieldSchema.selectorField) {
                if (typeof currentValue === 'object' && currentValue !== null) {
                    const existingCases = allCases.filter(caseName => currentValue[caseName] !== undefined)
                    selectedCase = existingCases.length === 1 ? existingCases[0] : null
                }
                // If no valid case, don't pick random - return empty to match enum behavior
                if (!selectedCase) {
                    return {}
                }
            } else {
                // Regular switch without selector - detect or pick random
                if (typeof currentValue === 'object' && currentValue !== null) {
                    const existingCases = allCases.filter(caseName => currentValue[caseName] !== undefined)
                    selectedCase = existingCases.length === 1 ? existingCases[0] : null
                }

                // If no case detected, pick random one
                if (!selectedCase) {
                    selectedCase = allCases[Math.floor(Math.random() * allCases.length)]
                }
            }

            const selectedCaseKey: string = selectedCase
            const caseSchema = getCaseSchema(fieldSchema, selectedCaseKey)

            // Build result with selected case
            const result: Record<string, any> = {}

            // Check if the case schema has nested switch metadata
            if (caseSchema._switchSelector && caseSchema._switchCases) {
                // This case has a nested switch - randomize using nested switch logic
                result[selectedCaseKey] = randomizeValue(caseSchema, currentValue?.[selectedCaseKey], selectedCaseKey)
            } else if (caseSchema.fields && Object.keys(caseSchema.fields).length > 0) {
                // Regular case with fields - randomize each field
                result[selectedCaseKey] = {}
                getNonMetadataKeys(caseSchema.fields).forEach(fieldKey => {
                    result[selectedCaseKey][fieldKey] = randomizeValue(
                        caseSchema.fields[fieldKey],
                        currentValue?.[selectedCaseKey]?.[fieldKey],
                        fieldKey
                    )
                })
            } else {
                // Empty case
                result[selectedCaseKey] = {}
            }

            return result
        }

        // ========================================================================
        // NESTED SWITCH WITH METADATA
        // ========================================================================
        if (fieldSchema?._switchSelector && fieldSchema?._switchCases) {
            const switchCases = fieldSchema._switchCases
            const allCases = Object.keys(switchCases)

            if (allCases.length === 0) {
                return currentValue || {}
            }

            // Detect currently selected case
            let selectedCase: string | null = null
            if (typeof currentValue === 'object' && currentValue !== null) {
                selectedCase = allCases.find(caseName => currentValue[caseName] !== undefined) || null
            }

            if (!selectedCase) {
                selectedCase = allCases[Math.floor(Math.random() * allCases.length)]
            }

            if (!selectedCase) {
                return currentValue || {}
            }

            const finalSelectedCase: string = selectedCase
            const result: Record<string, any> = {}
            const caseSchema = switchCases[finalSelectedCase]

            // Check if case is a direct field type (array, integer, etc.)
            if (caseSchema.fieldType && caseSchema.fieldType !== 'object') {
                // Direct field type - randomize using the case schema directly
                result[finalSelectedCase] = randomizeValue(caseSchema, currentValue?.[finalSelectedCase], finalSelectedCase)
            } else if (caseSchema.fields && caseSchema.fields._switchSelector && caseSchema.fields._switchCases) {
                // Nested nested switch
                result[finalSelectedCase] = randomizeValue(caseSchema, currentValue?.[finalSelectedCase], finalSelectedCase)
            } else if (caseSchema.fields && Object.keys(caseSchema.fields).length > 0) {
                // Object with fields
                const caseFieldKeys = getNonMetadataKeys(caseSchema.fields)

                if (caseFieldKeys.length === 1 && caseFieldKeys[0] === finalSelectedCase) {
                    result[finalSelectedCase] = randomizeValue(
                        caseSchema.fields[finalSelectedCase],
                        currentValue?.[finalSelectedCase],
                        finalSelectedCase
                    )
                } else {
                    result[finalSelectedCase] = {}
                    caseFieldKeys.forEach(fieldKey => {
                        result[finalSelectedCase][fieldKey] = randomizeValue(
                            caseSchema.fields[fieldKey],
                            currentValue?.[finalSelectedCase]?.[fieldKey],
                            fieldKey
                        )
                    })
                }
            } else {
                result[finalSelectedCase] = {}
            }

            return result
        }

        // ========================================================================
        // OBJECT HANDLING
        // ========================================================================
        if (fieldSchema?.fields && typeof fieldSchema.fields === 'object') {
            const result: Record<string, any> = {}
            const isFootprint = fieldSchema.type === 'footprint'

            getNonMetadataKeys(fieldSchema.fields).forEach((key) => {
                const nestedValue = (typeof currentValue === 'object' && currentValue !== null) ? currentValue[key] : undefined

                if (isFootprint && key === 'relation') {
                    result[key] = nestedValue !== undefined ? nestedValue : 'or'
                } else {
                    const randomized = randomizeValue(fieldSchema.fields[key], nestedValue, key)

                    if (key === 'protocols') {
                        console.log('=== PROTOCOLS RANDOMIZATION ===', {
                            'nestedValue': JSON.stringify(nestedValue),
                            'randomized result': JSON.stringify(randomized),
                            'is switch': fieldSchema.fields[key]?.fieldType === 'switch'
                        })
                    }

                    result[key] = randomized
                }
            })

            return result
        }

        // ========================================================================
        // CLONE HANDLING
        // ========================================================================
        if ((fieldType === 'clone' || fieldSchema?.type === 'clone') && fieldSchema?.fields) {
            const result: Record<string, any> = {}
            getNonMetadataKeys(fieldSchema.fields).forEach((optionKey) => {
                const optionValue = (typeof currentValue === 'object' && currentValue !== null) ? currentValue[optionKey] : undefined
                result[optionKey] = randomizeValue(fieldSchema.fields[optionKey], optionValue, optionKey)
            })
            return result
        }

        // Fallback: random string
        return Math.random().toString(36).substring(2, 12)
    }

    const result: Record<string, any> = {}
    Object.keys(schema).forEach((key) => {
        result[key] = randomizeValue(schema[key], currentData?.[key], key)
    })

    return result
}

// Transform time + cnt fields into attack-id for UI display
function transformToAttackId(data: any, schema: any): any {
    if (!data || typeof data !== 'object') return data
    if (Array.isArray(data)) {
        return data.map((item) => {
            const itemSchema = schema?.itemSchema || schema
            return transformToAttackId(item, itemSchema)
        })
    }

    const result: any = {}
    const hasTimeAndCnt = 'time' in data && 'cnt' in data &&
        schema?.time && schema?.cnt

    if (hasTimeAndCnt) {
        const time = data.time
        const cnt = data.cnt

        // Iterate schema keys to preserve XML/schema order
        Object.keys(schema).forEach(schemaKey => {
            if (schemaKey === 'time' || schemaKey === 'cnt') {
                // Skip individual time/cnt fields; they are merged into attack-id
                result['attack-id'] = `${cnt}-${time}`
            } else if (schemaKey === 'attack-id') {
                // If schema already defines attack-id, set it here
                result['attack-id'] = `${cnt}-${time}`
            } else if (schemaKey in data) {
                // Recursively transform child fields using their schema
                result[schemaKey] = transformToAttackId(data[schemaKey], schema[schemaKey])
            }
        })
    } else {
        Object.keys(data).forEach(key => {
            const fieldSchema = schema?.[key] || schema?.fields?.[key]
            result[key] = transformToAttackId(data[key], fieldSchema)
        })
    }

    return result
}

// Transform attack-id back to time + cnt fields for backend
function transformFromAttackId(data: any, originalSchema: any): any {
    if (!data || typeof data !== 'object') return data
    if (Array.isArray(data)) {
        return data.map((item) => {
            const itemSchema = originalSchema?.itemSchema || originalSchema

            // If item is wrapped (single-key object), check inner data for attack-id
            if (typeof item === 'object' && item !== null && Object.keys(item).length === 1) {
                const wrapperKey = Object.keys(item)[0]
                const innerData = item[wrapperKey]

                // Check if innerData has attack-id
                if (innerData && typeof innerData === 'object' && 'attack-id' in innerData) {
                    // Find schema for wrapper - try multiple paths
                    let innerSchema = itemSchema?.[wrapperKey] ||
                                      itemSchema?.fields?.[wrapperKey] ||
                                      itemSchema?.itemSchema?.[wrapperKey]
                    if (innerSchema) {
                        // Recursively transform with inner schema
                        const transformed = transformFromAttackId(innerData, innerSchema)
                        return {[wrapperKey]: transformed}
                    }
                }
            }

            return transformFromAttackId(item, itemSchema)
        })
    }

    const result: any = {}
    const hasAttackId = 'attack-id' in data
    const schemaHasTimeAndCnt = originalSchema?.time && originalSchema?.cnt

    if (hasAttackId && schemaHasTimeAndCnt) {
        const attackId = data['attack-id'] || ''
        const parts = attackId.toString().split('-')
        const cnt = parseInt(parts[0]) || 0
        const time = parseInt(parts[1]) || 0

        // Iterate schema keys in order to preserve XML field order
        Object.keys(originalSchema).forEach(schemaKey => {
            if (schemaKey === 'time') {
                result.time = time
            } else if (schemaKey === 'cnt') {
                result.cnt = cnt
            } else if (schemaKey in data) {
                // Resolve child schema. Prefer explicit child entry, then fields.
                let fieldSchema = originalSchema?.[schemaKey] || originalSchema?.fields?.[schemaKey]

                // If not found and parent schema is a switch (or uses _switch metadata),
                // try to resolve the case schema (preserve wrapper keys like 'source').
                if (!fieldSchema) {
                    const parentIsSwitch = originalSchema && (
                        originalSchema.fieldType === 'switch' ||
                        originalSchema.type === 'switch' ||
                        originalSchema.options ||
                        (originalSchema.fields && originalSchema.fields._switchSelector && originalSchema.fields._switchCases)
                    )

                    if (parentIsSwitch) {
                        const caseSchema = getCaseSchema(originalSchema, schemaKey)
                        if (caseSchema && typeof caseSchema === 'object') {
                            fieldSchema = caseSchema
                        }
                    }
                }

                result[schemaKey] = transformFromAttackId(data[schemaKey], fieldSchema)
            }
        })
    } else {
        Object.keys(data).forEach(key => {
            // Resolve child schema similar to above: try direct child, then fields.
            let fieldSchema = originalSchema?.[key] || originalSchema?.fields?.[key]

            if (!fieldSchema) {
                const parentIsSwitch = originalSchema && (
                    originalSchema.fieldType === 'switch' ||
                    originalSchema.type === 'switch' ||
                    originalSchema.options ||
                    (originalSchema.fields && originalSchema.fields._switchSelector && originalSchema.fields._switchCases)
                )

                if (parentIsSwitch) {
                    const caseSchema = getCaseSchema(originalSchema, key)
                    if (caseSchema && typeof caseSchema === 'object') {
                        fieldSchema = caseSchema
                    }
                }
            }

            result[key] = transformFromAttackId(data[key], fieldSchema)
        })
    }

    return result
}

// Transform schema to replace time + cnt with attack-id
function transformSchemaForAttackId(schema: any): any {
    if (!schema || typeof schema !== 'object') return schema

    const hasTimeAndCnt = schema.time && schema.cnt

    if (hasTimeAndCnt) {
        const result: any = {}

        // Iterate schema keys in order and place attack-id where time/cnt appear
        Object.keys(schema).forEach(key => {
            if (key === 'time' || key === 'cnt') {
                // Replace with attack-id at first occurrence
                if (!result['attack-id']) {
                    result['attack-id'] = {
                        type: 'string',
                        fieldType: 'string',
                        default: `${schema.cnt.default || 0}-${schema.time.default || 0}`,
                        required: true
                    }
                }
            } else {
                result[key] = transformSchemaForAttackId(schema[key])
            }
        })

        return result
    }

    if (schema.fields && typeof schema.fields === 'object') {
        return {
            ...schema,
            fields: transformSchemaForAttackId(schema.fields)
        }
    }

    if (schema.itemSchema) {
        return {
            ...schema,
            itemSchema: transformSchemaForAttackId(schema.itemSchema)
        }
    }

    if (schema.fieldType) {
        return schema
    }

    const result: any = {}
    let hasFieldDefinitions = false

    Object.keys(schema).forEach(key => {
        const value = schema[key]
        if (value && typeof value === 'object' && (value.type || value.fieldType || value.fields || value.itemSchema)) {
            hasFieldDefinitions = true
            result[key] = transformSchemaForAttackId(value)
        } else {
            result[key] = value
        }
    })

    return result
}

// Generate random attack-id in cnt-time format
export function generateAttackId(): string {
    const cnt = Math.floor(Math.random() * 10000)
    const time = Math.floor(Date.now() / 1000)
    return `${cnt}-${time}`
}

export const IRPSenderPage: React.FC = () => {
    const navigate = useNavigate()
    const [searchParams] = useSearchParams()
    const schemaId = searchParams.get('schema_id')

    const currentCC = useCCStore((state) => state.currentCC)
    const devices = useCCStore((state) => state.devices)
    const managementPorts = useCCStore((state) => state.managementPorts)
    const user = useAuthStore((state) => state.user)

    const [schemaInfo, setSchemaInfo] = useState<{ name: string; version: string } | null>(null)
    const [selectedSimulator, setSelectedSimulator] = useState<string>('')
    const [selectedDestinationPort, setSelectedDestinationPort] = useState<string>('')
    const [messages, setMessages] = useState<Array<{
        messageType: string;
        messageName: string;
        data: Record<string, any>;
        schema: Record<string, any>;
        originalSchema: Record<string, any>;
    }>>([])
    const [expandedMessages, setExpandedMessages] = useState<number[]>([])
    const [availableMessages, setAvailableMessages] = useState<SchemaMessage[]>([])
    const [addMessageDialogOpen, setAddMessageDialogOpen] = useState(false)
    const [isLoading, setIsLoading] = useState(false)
    const [snackbar, setSnackbar] = useState<{
        open: boolean;
        message: string;
        severity: 'success' | 'error' | 'info' | 'warning'
    }>({open: false, message: '', severity: 'success'})

    // Template management state
    const [saveDialogOpen, setSaveDialogOpen] = useState(false)
    const [loadDialogOpen, setLoadDialogOpen] = useState(false)
    const [templateName, setTemplateName] = useState('')
    const [savedTemplates, setSavedTemplates] = useState<any[]>([])
    const [loadingTemplates, setLoadingTemplates] = useState(false)

    // Validation state
    const [messageValidationState, setMessageValidationState] = useState<Map<number, boolean>>(new Map())
    const hasValidationErrors = Array.from(messageValidationState.values()).some(isValid => !isValid)

    // Test message state
    const [testDialogOpen, setTestDialogOpen] = useState(false)
    const [testResult, setTestResult] = useState<any>(null)
    const [testingMessage, setTestingMessage] = useState(false)

    // Loop functionality state
    const [loopDialogOpen, setLoopDialogOpen] = useState(false)
    const [loopDelay, setLoopDelay] = useState<number>(15)
    const [loopTimeout, setLoopTimeout] = useState<number>(600)
    const isLooping = useLoopStore((state) => state.irp.isLooping)
    const loopIntervalRef = React.useRef<NodeJS.Timeout | null>(null)
    const loopTimeoutRef = React.useRef<NodeJS.Timeout | null>(null)

    const sendMessagesOnceRef = React.useRef<() => Promise<boolean>>(async () => false)

    // PCAP Import state
    const [pcapDialogOpen, setPcapDialogOpen] = useState(false)
    const [pcapFile, setPcapFile] = useState<File | null>(null)
    const [pcapResults, setPcapResults] = useState<IRPPcapAnalysisResponse | null>(null)
    const [analyzingPcap, setAnalyzingPcap] = useState(false)
    const [selectedMessageIds, setSelectedMessageIds] = useState<string[]>([])

    // Redirect if missing context
    useEffect(() => {
        if (!currentCC || !schemaId) {
            navigate('/cc/reporting/irp')
        }
    }, [currentCC, schemaId, navigate])

    // Set current session and restore form state on mount
    useEffect(() => {
        if (currentCC && user) {
            useFormStore.getState().setCurrentSession(currentCC, user.username)
        }

        const formState = useFormStore.getState().getIrpFormState()

        if (formState.messages && formState.messages.length > 0 && messages.length === 0) {
            setMessages(formState.messages)
            setExpandedMessages(formState.expandedMessages)
            setSnackbar({
                open: true,
                message: `Messages restored from previous session (${formState.messages.length} message(s))`,
                severity: 'info'
            })
        }
    }, [])

    // Restore loop on mount if it was running
    useEffect(() => {
        const loopState = useLoopStore.getState().getIrpLoopState()

        if (loopState.isLooping && loopState.startTime) {
            const remaining = useLoopStore.getState().getRemainingTime('irp')

            if (remaining > 0) {
                setSelectedSimulator(loopState.simulator)
                setSelectedDestinationPort(loopState.destinationPort)
                setLoopDelay(loopState.loopDelay)
                setLoopTimeout(loopState.loopTimeout)

                setSnackbar({
                    open: true,
                    message: `Loop resumed - ${remaining} seconds remaining, ${loopState.batchesSent} batch(es) sent`,
                    severity: 'info'
                })

                loopIntervalRef.current = setInterval(async () => {
                    const success = await sendMessagesOnceRef.current()
                    if (success) {
                        useLoopStore.getState().incrementIrpBatches()
                        const currentBatches = useLoopStore.getState().getIrpLoopState().batchesSent
                        setSnackbar({
                            open: true,
                            message: `Loop running - Sent batch #${currentBatches}`,
                            severity: 'info'
                        })
                    }
                }, loopState.loopDelay * 1000)

                loopTimeoutRef.current = setTimeout(() => {
                    handleStopLoop()
                    const elapsed = useLoopStore.getState().getElapsedTime('irp')
                    const finalBatches = useLoopStore.getState().getIrpLoopState().batchesSent
                    setSnackbar({
                        open: true,
                        message: `Loop stopped after ${elapsed}s - Sent ${finalBatches} batch(es)`,
                        severity: 'success'
                    })
                }, remaining * 1000)
            } else {
                useLoopStore.getState().clearIrpLoop()
            }
        }

        return () => {
            // DO NOT clear intervals - loop should persist
        }
    }, [])

    const compatibleSimulators = devices.filter((d) => d.version === schemaInfo?.version)

    // Fetch schema info and available messages
    useEffect(() => {
        if (currentCC && schemaId) {
            const fetchData = async () => {
                try {
                    setIsLoading(true)
                    const schemas = await irpSchemaService.listSchemas(currentCC)
                    const schema = schemas.find((s) => s.mongo_id === schemaId)
                    if (schema) {
                        setSchemaInfo({name: schema.template_name, version: schema.version})
                    }
                    const msgs = await irpSchemaService.listMessages(currentCC, schemaId)
                    setAvailableMessages(msgs)
                } catch (error) {
                    setSnackbar({open: true, message: 'Failed to load schema data', severity: 'error'})
                } finally {
                    setIsLoading(false)
                }
            }
            fetchData()
        }
    }, [currentCC, schemaId])

    // Prefer a default destination port (G2 > G1 > first available)
    useEffect(() => {
        if (managementPorts && managementPorts.length > 0 && !selectedDestinationPort) {
            const g2Port = managementPorts.find((p) => p.interface && p.interface.toLowerCase() === 'g2')
            const g1Port = managementPorts.find((p) => p.interface && p.interface.toLowerCase() === 'g1')
            const defaultPort = g2Port || g1Port || managementPorts[0]
            if (defaultPort && defaultPort.address) {
                setSelectedDestinationPort(defaultPort.address)
            }
        }
    }, [managementPorts, selectedDestinationPort])

    // Message management
    const addMessage = async (messageType: string, messageName: string) => {
        try {
            setIsLoading(true)
            const template = await irpSchemaService.getMessageTemplate(currentCC!, schemaId!, messageType)

            const transformedData = transformToAttackId(template.template, template.schema)
            const transformedSchema = transformSchemaForAttackId(template.schema)

            setMessages((prev) => [...prev, {
                messageType,
                messageName,
                data: transformedData,
                schema: transformedSchema,
                originalSchema: template.schema,
            }])
            setExpandedMessages((prev) => [...prev, messages.length])
            setAddMessageDialogOpen(false)
            setSnackbar({open: true, message: `Added ${messageName}`, severity: 'success'})
        } catch (error: any) {
            setSnackbar({open: true, message: 'Failed to load message template', severity: 'error'})
        } finally {
            setIsLoading(false)
        }
    }

    const handleToggleAllMessages = () => {
        const allExpanded = expandedMessages.length === messages.length && messages.length > 0
        if (allExpanded) {
            setExpandedMessages([])
        } else {
            setExpandedMessages(messages.map((_, i) => i))
        }
    }

    const deleteMessage = (index: number) => {
        setMessages((prev) => prev.filter((_, i) => i !== index))
        setExpandedMessages((prev) => prev.filter((i) => i !== index).map((i) => (i > index ? i - 1 : i)))
    }

    const toggleMessage = (index: number) => {
        setExpandedMessages((prev) => (prev.includes(index) ? prev.filter((i) => i !== index) : [...prev, index]))
    }

    function updateMessage(index: number, data: Record<string, any>) {
        setMessages((prev) => {
            const next = [...prev]
            next[index] = {...next[index], data}


            return next
        })
    }

    // Save Template
    const handleSaveTemplate = async () => {
        if (!templateName.trim()) {
            alert('Please enter a template name')
            return
        }

        try {
            const templateData = {
                name: templateName.trim(),
                schema_id: schemaId!,
                schema_name: schemaInfo?.name || '',
                messages: messages,
            }

            await irpSchemaService.saveTemplate(currentCC!, templateData)
            alert('Template saved successfully')
            setSaveDialogOpen(false)
            setTemplateName('')
        } catch (error) {
            alert('Failed to save template')
        }
    }

    // Load Template - Open Dialog
    const handleOpenLoadDialog = async () => {
        setLoadingTemplates(true)
        setLoadDialogOpen(true)

        try {
            const result = await irpSchemaService.listTemplates(currentCC!)
            setSavedTemplates(result.templates)
        } catch (error) {
            alert('Failed to load templates')
        } finally {
            setLoadingTemplates(false)
        }
    }

    // Load Template - Apply
    const handleLoadTemplate = async (templateId: string) => {
        try {
            const result = await irpSchemaService.loadTemplate(currentCC!, templateId)
            const template = result.template

            const messagesWithSchemas = await Promise.all(
                template.messages.map(async (msg: any) => {
                    try {
                        const templateData = await irpSchemaService.getMessageTemplate(currentCC!, schemaId!, msg.messageType)
                        const transformedData = transformToAttackId(msg.data, templateData.schema)
                        const transformedSchema = transformSchemaForAttackId(templateData.schema)
                        return {
                            ...msg,
                            data: transformedData,
                            schema: transformedSchema,
                            originalSchema: templateData.schema
                        }
                    } catch {
                        return {
                            ...msg,
                            schema: {},
                            originalSchema: {}
                        }
                    }
                })
            )

            setMessages(messagesWithSchemas)
            setLoadDialogOpen(false)
            useFormStore.getState().clearIrpFormState()
            alert('Template loaded successfully')
        } catch (error) {
            alert('Failed to load template')
        }
    }

    // Delete Template
    const handleDeleteTemplate = async (templateId: string) => {
        if (!window.confirm('Are you sure you want to delete this template?')) {
            return
        }

        try {
            await irpSchemaService.deleteTemplate(currentCC!, templateId)
            const result = await irpSchemaService.listTemplates(currentCC!)
            setSavedTemplates(result.templates)
        } catch (error) {
            alert('Failed to delete template')
        }
    }

    // PCAP Import handlers
    const handleOpenPcapDialog = () => {
        setPcapDialogOpen(true)
        setPcapFile(null)
        setPcapResults(null)
        setSelectedMessageIds([])
    }

    const handlePcapFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0]
        if (file) {
            setPcapFile(file)
            setPcapResults(null)
            setSelectedMessageIds([])
            // Auto-analyze when file is selected
            analyzePcapFile(file)
        }
    }

    const analyzePcapFile = async (file: File) => {
        try {
            setAnalyzingPcap(true)
            const results = await irpSchemaService.analyzePcap(file, schemaId!)
            setPcapResults(results)

            // Check if no messages found
            if (results.messages.length === 0) {
                setSnackbar({
                    open: true,
                    message: 'Warning: No IRP messages found in PCAP',
                    severity: 'warning'
                })
            } else {
                // Check for unknown messages
                const unknownMessages = results.messages.filter(msg =>
                    msg.message_name.includes('Unknown') || msg.message_name.includes('No schema loaded')
                )
                if (unknownMessages.length > 0) {
                    setSnackbar({
                        open: true,
                        message: `Warning: ${unknownMessages.length} unknown message(s) found (not in current schema)`,
                        severity: 'warning'
                    })
                }

                setSnackbar({
                    open: true,
                    message: `Found ${results.irp_packets} IRP packets with ${results.messages.length} unique message types`,
                    severity: 'success'
                })
            }
        } catch (error: any) {
            setSnackbar({
                open: true,
                message: error?.response?.data?.detail || 'Failed to analyze PCAP',
                severity: 'error'
            })
        } finally {
            setAnalyzingPcap(false)
        }
    }

    const handleToggleMessage = (messageId: string) => {
        setSelectedMessageIds(prev =>
            prev.includes(messageId)
                ? prev.filter(id => id !== messageId)
                : [...prev, messageId]
        )
    }

    const handleSelectAll = () => {
        if (!pcapResults) return

        // Only select messages that are NOT unknown
        const knownMessages = pcapResults.messages.filter(msg =>
            !msg.message_name.includes('Unknown') && !msg.message_name.includes('No schema loaded')
        )

        if (selectedMessageIds.length === knownMessages.length) {
            // Deselect all
            setSelectedMessageIds([])
        } else {
            // Select all known messages
            setSelectedMessageIds(knownMessages.map(msg => msg.message_id))
        }
    }

    const handleLoadSelectedMessages = async () => {
        if (selectedMessageIds.length === 0) {
            setSnackbar({open: true, message: 'Please select at least one message', severity: 'error'})
            return
        }

        try {
            setIsLoading(true)

            // Clear current messages
            setMessages([])
            setExpandedMessages([])

            const loadedMessages: any[] = []
            const failedMessages: string[] = []

            // Add selected messages one by one
            for (const messageId of selectedMessageIds) {
                const message = pcapResults?.messages.find(msg => msg.message_id === messageId)
                if (message) {
                    try {
                        const template = await irpSchemaService.getMessageTemplate(currentCC!, schemaId!, messageId)

                        const transformedData = transformToAttackId(template.template, template.schema)
                        const transformedSchema = transformSchemaForAttackId(template.schema)

                        loadedMessages.push({
                            messageType: messageId,
                            messageName: message.message_name,
                            data: transformedData,
                            schema: transformedSchema,
                            originalSchema: template.schema,
                        })
                    } catch (error) {
                        // Message not found in current schema
                        failedMessages.push(`${message.message_name} (ID: ${messageId})`)
                    }
                }
            }

            setMessages(loadedMessages)

            // Expand all added messages
            setExpandedMessages(loadedMessages.map((_, index) => index))

            setPcapDialogOpen(false)

            if (failedMessages.length > 0) {
                setSnackbar({
                    open: true,
                    message: `Loaded ${loadedMessages.length} message(s). ${failedMessages.length} message(s) not found in current schema: ${failedMessages.join(', ')}`,
                    severity: 'warning'
                })
            } else {
                setSnackbar({
                    open: true,
                    message: `Loaded ${loadedMessages.length} message(s) from PCAP`,
                    severity: 'success'
                })
            }
        } catch (error: any) {
            setSnackbar({open: true, message: 'Failed to load messages', severity: 'error'})
        } finally {
            setIsLoading(false)
        }
    }

    // Download JSON
    const handleDownloadJSON = () => {
        const messagesForExport = messages.map((msg) => ({
            message: msg.messageName,
            ...msg.data,
        }))

        const dataToDownload = {
            messages: messagesForExport,
        }

        const blob = new Blob([JSON.stringify(dataToDownload, null, 2)], {type: 'application/json'})
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `irp-messages-${new Date().toISOString().slice(0, 10)}.json`
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
        URL.revokeObjectURL(url)
    }

    // Test single message with e2e workflow
    const handleTestMessage = async (messageIndex: number) => {
        if (!schemaId) {
            setSnackbar({open: true, message: 'Schema not loaded', severity: 'error'})
            return
        }

        const msg = messages[messageIndex]

        try {
            setTestingMessage(true)
            setTestResult(null)

            const backendData = transformFromAttackId(msg.data, msg.originalSchema)

            const payload = {
                schema_id: schemaId,
                message_id: parseInt(msg.messageType),
                message_name: msg.messageName,
                template: backendData
            }


            const response = await fetch(`${process.env.REACT_APP_API_BASE_URL}/reporter/irp/test-message`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Bearer ${localStorage.getItem('token')}`,
                },
                body: JSON.stringify(payload),
            })

            if (!response.ok) {
                const error = await response.json()
                throw new Error(error.detail || 'Test failed')
            }

            const result = await response.json()
            setTestResult(result)
            setTestDialogOpen(true)

            if (result.success) {
                setSnackbar({open: true, message: 'Message test completed successfully', severity: 'success'})
            } else {
                setSnackbar({open: true, message: 'Message test failed - see details', severity: 'error'})
            }
        } catch (error: any) {
            setSnackbar({open: true, message: error.message || 'Failed to test message', severity: 'error'})
        } finally {
            setTestingMessage(false)
        }
    }

    // Send Messages
    const handleSendMessages = async () => {
        if (!selectedSimulator || !selectedDestinationPort || messages.length === 0) {
            setSnackbar({open: true, message: 'Please select simulator, port, and add messages', severity: 'error'})
            return
        }

        try {
            setIsLoading(true)

            const formattedMessages = messages.map((msg) => {
                const backendData = transformFromAttackId(msg.data, msg.originalSchema)
                return {
                    message: msg.messageName,
                    ...backendData,
                }
            })

            const payload = {
                mongo_id: schemaId!,
                message_data: {
                    messages: formattedMessages,
                },
            }

            await irpSchemaService.sendMessages(selectedDestinationPort, selectedSimulator, payload)
            setSnackbar({open: true, message: `Successfully sent ${messages.length} message(s)`, severity: 'success'})
        } catch (error: any) {
            const errorMsg = error?.response?.data?.detail || error?.message || 'Failed to send messages'
            setSnackbar({open: true, message: errorMsg, severity: 'error'})
        } finally {
            setIsLoading(false)
        }
    }

    // Send messages once (used by loop)
    const sendMessagesOnce = async () => {
        if (!selectedSimulator || !selectedDestinationPort || messages.length === 0) {
            return false
        }

        try {
            const formattedMessages = messages.map((msg) => {
                const backendData = transformFromAttackId(msg.data, msg.originalSchema)
                return {
                    message: msg.messageName,
                    ...backendData,
                }
            })

            const payload = {
                mongo_id: schemaId!,
                message_data: {
                    messages: formattedMessages,
                },
            }

            await irpSchemaService.sendMessages(selectedDestinationPort, selectedSimulator, payload)
            return true
        } catch (error: any) {
            const errorMsg = error?.response?.data?.detail || error?.message || 'Failed to send messages'
            setSnackbar({open: true, message: errorMsg, severity: 'error'})
            return false
        }
    }

    // Update ref whenever dependencies change
    useEffect(() => {
        sendMessagesOnceRef.current = sendMessagesOnce
    }, [selectedDestinationPort, selectedSimulator, messages, schemaId])

    // Auto-save form state to localStorage on every change
    useEffect(() => {
        if (messages.length > 0) {
            useFormStore.getState().setIrpFormState(messages, expandedMessages)
        }
    }, [messages, expandedMessages])

    const handleStartLoop = () => {
        if (!selectedSimulator) {
            setSnackbar({open: true, message: 'Please select a simulator', severity: 'error'})
            return
        }

        if (!selectedDestinationPort) {
            setSnackbar({open: true, message: 'Please select a destination port', severity: 'error'})
            return
        }

        if (messages.length === 0) {
            setSnackbar({open: true, message: 'Please add at least one message', severity: 'error'})
            return
        }

        if (loopDelay < 1) {
            setSnackbar({open: true, message: 'Loop delay must be at least 1 second', severity: 'error'})
            return
        }

        if (loopTimeout < 1) {
            setSnackbar({open: true, message: 'Timeout must be at least 1 second', severity: 'error'})
            return
        }

        setLoopDialogOpen(false)

        const startTime = Date.now()

        useLoopStore.getState().setIrpLoopState({
            isLooping: true,
            loopDelay: loopDelay,
            loopTimeout: loopTimeout,
            startTime: startTime,
            batchesSent: 0,
            simulator: selectedSimulator,
            destinationPort: selectedDestinationPort,
        })

        sendMessagesOnce().then(success => {
            if (success) {
                useLoopStore.getState().incrementIrpBatches()
                const currentBatches = useLoopStore.getState().getIrpLoopState().batchesSent
                setSnackbar({open: true, message: `Loop started - Sent batch #${currentBatches}`, severity: 'info'})
            }
        })

        loopIntervalRef.current = setInterval(async () => {
            const success = await sendMessagesOnceRef.current()
            if (success) {
                useLoopStore.getState().incrementIrpBatches()
                const currentBatches = useLoopStore.getState().getIrpLoopState().batchesSent
                setSnackbar({open: true, message: `Loop running - Sent batch #${currentBatches}`, severity: 'info'})
            }
        }, loopDelay * 1000)

        loopTimeoutRef.current = setTimeout(() => {
            handleStopLoop()
            const elapsedSeconds = useLoopStore.getState().getElapsedTime('irp')
            const finalBatches = useLoopStore.getState().getIrpLoopState().batchesSent
            setSnackbar({
                open: true,
                message: `Loop stopped after ${elapsedSeconds}s - Sent ${finalBatches} batch(es)`,
                severity: 'success'
            })
        }, loopTimeout * 1000)
    }

    const handleStopLoop = () => {
        if (loopIntervalRef.current) {
            clearInterval(loopIntervalRef.current)
            loopIntervalRef.current = null
        }
        if (loopTimeoutRef.current) {
            clearTimeout(loopTimeoutRef.current)
            loopTimeoutRef.current = null
        }

        useLoopStore.getState().setIrpLoopState({
            isLooping: false,
        })
    }

    const handleOpenLoopDialog = () => {
        setLoopDialogOpen(true)
    }

    return (
        <Layout>
            <Box sx={{height: 'calc(100vh - 64px)', display: 'flex', flexDirection: 'column'}}>
                {/* Fixed Header */}
                <Box sx={{padding: 3, borderBottom: '1px solid #E0E0E0'}}>
                    <Typography variant="h4" sx={{marginBottom: 1}}>
                        IRP Message Sender
                    </Typography>
                    {schemaInfo && (
                        <Alert severity="info" sx={{marginBottom: 2}}>
                            Using schema: {schemaInfo.name} (Version: {schemaInfo.version})
                        </Alert>
                    )}

                    <FormControl fullWidth>
                        <InputLabel>Target Simulator</InputLabel>
                        <Select value={selectedSimulator}
                                onChange={(e) => setSelectedSimulator(e.target.value as string)}
                                label="Target Simulator">
                            {compatibleSimulators.map((device) => (
                                <MenuItem key={device.management_ip} value={device.management_ip}>
                                    {device.name || device.management_ip} ({device.management_ip})
                                </MenuItem>
                            ))}
                        </Select>
                    </FormControl>

                    <FormControl fullWidth sx={{marginTop: 2}}>
                        <InputLabel>Destination Port</InputLabel>
                        <Select value={selectedDestinationPort}
                                onChange={(e) => setSelectedDestinationPort(e.target.value as string)}
                                label="Destination Port">
                            {managementPorts.map((port) => (
                                <MenuItem key={port.interface} value={port.address}>
                                    {port.interface}: {port.address}
                                </MenuItem>
                            ))}
                        </Select>
                    </FormControl>
                </Box>

                {/* Scrollable Message List */}
                <Box sx={{flex: 1, overflow: 'auto', padding: 3}}>
                    {isLoading ? (
                        <Box display="flex" alignItems="center" gap={2}>
                            <CircularProgress size={20}/>
                            <Typography>Loading...</Typography>
                        </Box>
                    ) : messages.length === 0 ? (
                        <Typography color="textSecondary">No messages. Use "Add Message" to add one from the
                            schema.</Typography>
                    ) : (
                        messages.map((msg, index) => (
                            <Paper key={index} sx={{marginBottom: 2, padding: 2}}>
                                <Box sx={{
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    alignItems: 'center',
                                    marginBottom: 2
                                }}>
                                    <Typography variant="h6">{msg.messageName}</Typography>
                                    <Box>
                                        <IconButton onClick={() => toggleMessage(index)}>
                                            {expandedMessages.includes(index) ? <ExpandLessIcon/> : <ExpandMoreIcon/>}
                                        </IconButton>
                                        <Tooltip title="Generate random values (preserves iterations)">
                                            <IconButton
                                                onClick={() => {
                                                    const randomData = generateRandomData(msg.schema, msg.data)
                                                    updateMessage(index, randomData)
                                                }}
                                                size="small"
                                            >
                                                <CasinoIcon fontSize="small"/>
                                            </IconButton>
                                        </Tooltip>
                                        <Tooltip title="Test message parsing">
                                            <IconButton
                                                onClick={() => handleTestMessage(index)}
                                                size="small"
                                                color="primary"
                                                disabled={!messageValidationState.get(index) || testingMessage}
                                            >
                                                <ScienceIcon fontSize="small"/>
                                            </IconButton>
                                        </Tooltip>
                                        <IconButton onClick={() => deleteMessage(index)} color="error">
                                            <DeleteIcon/>
                                        </IconButton>
                                    </Box>
                                </Box>
                                <Collapse in={expandedMessages.includes(index)}>
                                    <IRPMessageForm
                                        messageData={msg.data}
                                        schema={msg.schema}
                                        onChange={(data) => updateMessage(index, data)}
                                        onValidationChange={(isValid) => {
                                            setMessageValidationState(prev => {
                                                const newMap = new Map(prev)
                                                newMap.set(index, isValid)
                                                return newMap
                                            })
                                        }}
                                    />
                                </Collapse>
                            </Paper>
                        ))
                    )}
                </Box>

                {/* Fixed Footer */}
                <Box sx={{padding: 3, borderTop: '1px solid #E0E0E0', display: 'flex', gap: 2, flexWrap: 'wrap'}}>
                    <Button variant="outlined" startIcon={<AddIcon/>} onClick={() => setAddMessageDialogOpen(true)}>
                        Add Message
                    </Button>
                    <Button
                        variant="outlined"
                        startIcon={expandedMessages.length === messages.length && messages.length > 0 ?
                            <UnfoldLessIcon/> : <UnfoldMoreIcon/>}
                        onClick={handleToggleAllMessages}
                        disabled={messages.length === 0}
                    >
                        {expandedMessages.length === messages.length && messages.length > 0 ? 'Collapse All' : 'Expand All'}
                    </Button>
                    <Button
                        variant="contained"
                        color="secondary"
                        onClick={() => setSaveDialogOpen(true)}
                        disabled={messages.length === 0 || hasValidationErrors}
                    >
                        Save Template
                    </Button>
                    <Button
                        variant="contained"
                        color="secondary"
                        onClick={handleDownloadJSON}
                        disabled={messages.length === 0 || hasValidationErrors}
                    >
                        Download JSON
                    </Button>
                    <Button
                        variant="contained"
                        color="secondary"
                        onClick={handleOpenLoadDialog}
                    >
                        Load Template
                    </Button>
                    <Button
                        variant="contained"
                        color="secondary"
                        startIcon={<UploadFileIcon />}
                        onClick={handleOpenPcapDialog}
                    >
                        Import from PCAP
                    </Button>
                    <Box sx={{flex: 1}}/>
                    <Button
                        variant="contained"
                        color="primary"
                        startIcon={<SendIcon/>}
                        disabled={!selectedSimulator || !selectedDestinationPort || messages.length === 0 || isLoading || isLooping || hasValidationErrors}
                        onClick={handleSendMessages}
                    >
                        {isLoading ? 'Sending...' : `Send Messages (${messages.length})`}
                    </Button>

                    {!isLooping ? (
                        <Button
                            variant="contained"
                            color="secondary"
                            startIcon={<LoopIcon/>}
                            onClick={handleOpenLoopDialog}
                            disabled={!selectedSimulator || !selectedDestinationPort || messages.length === 0 || isLoading || hasValidationErrors}
                        >
                            Send Loop
                        </Button>
                    ) : (
                        <Button
                            variant="contained"
                            color="error"
                            startIcon={<StopIcon/>}
                            onClick={handleStopLoop}
                        >
                            Stop Loop
                        </Button>
                    )}
                </Box>

                {/* Loop Configuration Dialog */}
                <Dialog open={loopDialogOpen} onClose={() => setLoopDialogOpen(false)} maxWidth="sm" fullWidth>
                    <DialogTitle>Configure Send Loop</DialogTitle>
                    <DialogContent>
                        <TextField
                            autoFocus
                            margin="dense"
                            label="Loop Delay (seconds)"
                            type="number"
                            fullWidth
                            value={loopDelay}
                            onChange={(e) => setLoopDelay(Math.floor(parseInt(e.target.value) || 0))}
                            helperText="Time between sending messages (minimum 1 second)"
                            inputProps={{min: 1, step: 1}}
                        />
                        <TextField
                            margin="dense"
                            label="Timeout (seconds)"
                            type="number"
                            fullWidth
                            required
                            value={loopTimeout}
                            onChange={(e) => setLoopTimeout(Math.floor(parseInt(e.target.value) || 0))}
                            helperText="Loop will automatically stop after this duration (required, minimum 1 second)"
                            inputProps={{min: 1, step: 1}}
                        />
                    </DialogContent>
                    <DialogActions>
                        <Button onClick={() => setLoopDialogOpen(false)}>Cancel</Button>
                        <Button onClick={handleStartLoop} variant="contained" color="secondary">
                            Start Loop
                        </Button>
                    </DialogActions>
                </Dialog>

                {/* Save Template Dialog */}
                <Dialog open={saveDialogOpen} onClose={() => setSaveDialogOpen(false)}>
                    <DialogTitle>Save Template</DialogTitle>
                    <DialogContent>
                        <TextField
                            autoFocus
                            margin="dense"
                            label="Template Name"
                            fullWidth
                            value={templateName}
                            onChange={(e) => setTemplateName(e.target.value)}
                            onKeyPress={(e) => {
                                if (e.key === 'Enter') {
                                    handleSaveTemplate()
                                }
                            }}
                        />
                    </DialogContent>
                    <DialogActions>
                        <Button onClick={() => setSaveDialogOpen(false)}>Cancel</Button>
                        <Button onClick={handleSaveTemplate} variant="contained" color="primary">
                            Save
                        </Button>
                    </DialogActions>
                </Dialog>

                {/* Load Template Dialog */}
                <Dialog
                    open={loadDialogOpen}
                    onClose={() => setLoadDialogOpen(false)}
                    maxWidth="md"
                    fullWidth
                >
                    <DialogTitle>Load Template</DialogTitle>
                    <DialogContent>
                        {loadingTemplates ? (
                            <Box sx={{display: 'flex', justifyContent: 'center', padding: 3}}>
                                <CircularProgress/>
                            </Box>
                        ) : savedTemplates.length === 0 ? (
                            <Typography color="textSecondary">No saved templates</Typography>
                        ) : (
                            <List>
                                {savedTemplates.map((template) => (
                                    <ListItem key={template.id} secondaryAction={
                                        <IconButton edge="end" onClick={() => handleDeleteTemplate(template.id)}>
                                            <DeleteIcon/>
                                        </IconButton>
                                    }>
                                        <ListItemButton onClick={() => handleLoadTemplate(template.id)}>
                                            <ListItemText
                                                primary={template.name}
                                                secondary={`Schema: ${template.schema_name} | Created: ${new Date(template.created_at).toLocaleDateString()}`}
                                            />
                                        </ListItemButton>
                                    </ListItem>
                                ))}
                            </List>
                        )}
                    </DialogContent>
                    <DialogActions>
                        <Button onClick={() => setLoadDialogOpen(false)}>Close</Button>
                    </DialogActions>
                </Dialog>

            </Box>

            {/* Add Message Dialog */}
            <Dialog open={addMessageDialogOpen} onClose={() => setAddMessageDialogOpen(false)} maxWidth="sm" fullWidth>
                <DialogTitle>Add Message</DialogTitle>
                <DialogContent>
                    <List>
                        {availableMessages.map((msg) => (
                            <ListItemButton key={msg.id} onClick={() => addMessage(msg.id, msg.name)}>
                                <ListItemText primary={msg.name} secondary={`ID: ${msg.id}`}/>
                            </ListItemButton>
                        ))}
                    </List>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setAddMessageDialogOpen(false)}>Cancel</Button>
                </DialogActions>
            </Dialog>

            <Snackbar
                open={snackbar.open}
                autoHideDuration={3000}
                onClose={() => setSnackbar((s) => ({...s, open: false}))}
                anchorOrigin={{vertical: 'top', horizontal: 'center'}}
            >
                <Alert severity={snackbar.severity}>{snackbar.message}</Alert>
            </Snackbar>

            {/* Test Result Dialog */}
            <Dialog
                open={testDialogOpen}
                onClose={() => setTestDialogOpen(false)}
                maxWidth="md"
                fullWidth
            >
                <DialogTitle>
                    Message Test Result
                    {testResult?.success && ' ✓'}
                    {testResult && !testResult.success && ' ✗'}
                </DialogTitle>
                <DialogContent>
                    {testResult && (
                        <Box>
                            <Typography variant="subtitle2" gutterBottom>
                                Status: {testResult.success ? 'Success' : 'Failed'}
                            </Typography>

                            {testResult.result?.error && (
                                <Box sx={{marginTop: 2}}>
                                    <Typography variant="subtitle2" gutterBottom color="error">
                                        Error:
                                    </Typography>
                                    <TextField
                                        multiline
                                        fullWidth
                                        rows={8}
                                        value={testResult.result.error}
                                        InputProps={{
                                            readOnly: true,
                                            sx: {fontFamily: 'monospace', fontSize: '0.85rem', color: 'error.main'}
                                        }}
                                        sx={{
                                            marginTop: 1,
                                            '& .MuiOutlinedInput-root': {
                                                '& fieldset': {borderColor: 'error.main'}
                                            }
                                        }}
                                    />
                                </Box>
                            )}

                            {testResult.result?.errors && testResult.result.errors.length > 0 && (
                                <Box sx={{marginTop: 2}}>
                                    <Typography variant="subtitle2" gutterBottom color="error">
                                        Parser Errors:
                                    </Typography>
                                    <TextField
                                        multiline
                                        fullWidth
                                        rows={12}
                                        value={testResult.result.errors.join('\n')}
                                        InputProps={{
                                            readOnly: true,
                                            sx: {fontFamily: 'monospace', fontSize: '0.85rem', color: 'error.main'}
                                        }}
                                        sx={{
                                            marginTop: 1,
                                            '& .MuiOutlinedInput-root': {
                                                '& fieldset': {borderColor: 'error.main'}
                                            }
                                        }}
                                    />
                                </Box>
                            )}

                            {testResult.parsed_xml && (
                                <Box sx={{marginTop: 2}}>
                                    <Typography variant="subtitle2" gutterBottom>
                                        Parsed XML Result:
                                    </Typography>
                                    <TextField
                                        multiline
                                        fullWidth
                                        rows={20}
                                        value={testResult.parsed_xml}
                                        InputProps={{
                                            readOnly: true,
                                            sx: {fontFamily: 'monospace', fontSize: '0.85rem'}
                                        }}
                                        sx={{marginTop: 1}}
                                    />
                                </Box>
                            )}

                            {testResult.result && (
                                <Box sx={{marginTop: 2}}>
                                    <Typography variant="subtitle2" gutterBottom>
                                        Test Steps:
                                    </Typography>
                                    {testResult.result.steps?.map((step: any, idx: number) => (
                                        <Box key={idx} sx={{marginLeft: 2, marginTop: 1}}>
                                            <Typography variant="body2">
                                                {idx + 1}. {step.step}: {step.status}
                                            </Typography>
                                        </Box>
                                    ))}
                                </Box>
                            )}
                        </Box>
                    )}
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setTestDialogOpen(false)}>Close</Button>
                </DialogActions>
            </Dialog>

            {/* PCAP Import Dialog */}
            <Dialog
                open={pcapDialogOpen}
                onClose={() => setPcapDialogOpen(false)}
                maxWidth="md"
                fullWidth
            >
                <DialogTitle>Import Messages from PCAP</DialogTitle>
                <DialogContent>
                    <Box sx={{ marginTop: 2 }}>
                        {/* File Upload */}
                        <input
                            accept=".pcap,.pcapng"
                            style={{ display: 'none' }}
                            id="pcap-file-input"
                            type="file"
                            onChange={handlePcapFileChange}
                        />
                        <label htmlFor="pcap-file-input">
                            <Button
                                variant="outlined"
                                component="span"
                                startIcon={<UploadFileIcon />}
                                fullWidth
                                disabled={analyzingPcap}
                            >
                                {pcapFile ? pcapFile.name : 'Select PCAP File'}
                            </Button>
                        </label>

                        {/* Loading */}
                        {analyzingPcap && (
                            <Box sx={{ display: 'flex', justifyContent: 'center', padding: 3 }}>
                                <CircularProgress />
                                <Typography sx={{ marginLeft: 2 }}>Analyzing PCAP...</Typography>
                            </Box>
                        )}

                        {/* Results */}
                        {pcapResults && pcapResults.messages.length > 0 && (
                            <Box sx={{ marginTop: 3 }}>
                                {/* Summary */}
                                <Alert severity="info" sx={{ marginBottom: 2 }}>
                                    Found {pcapResults.irp_packets} IRP packets with {pcapResults.messages.length} unique message types
                                </Alert>

                                {/* Select All Checkbox */}
                                <Box sx={{ display: 'flex', alignItems: 'center', marginBottom: 1, paddingLeft: 1 }}>
                                    <Checkbox
                                        checked={
                                            pcapResults.messages.filter(msg =>
                                                !msg.message_name.includes('Unknown') &&
                                                !msg.message_name.includes('No schema loaded')
                                            ).length > 0 &&
                                            selectedMessageIds.length === pcapResults.messages.filter(msg =>
                                                !msg.message_name.includes('Unknown') &&
                                                !msg.message_name.includes('No schema loaded')
                                            ).length
                                        }
                                        indeterminate={
                                            selectedMessageIds.length > 0 &&
                                            selectedMessageIds.length < pcapResults.messages.filter(msg =>
                                                !msg.message_name.includes('Unknown') &&
                                                !msg.message_name.includes('No schema loaded')
                                            ).length
                                        }
                                        onChange={handleSelectAll}
                                    />
                                    <Typography variant="subtitle1" sx={{ fontWeight: 'bold' }}>
                                        Select All / Deselect All
                                    </Typography>
                                </Box>

                                {/* Message List with Checkboxes */}
                                <List>
                                    {pcapResults.messages.map((msg) => {
                                        // Only disable truly unknown messages (not in schema), not "No schema loaded"
                                        const isUnknown = msg.message_name.includes('Unknown') &&
                                                          !msg.message_name.includes('No schema loaded')

                                        return (
                                            <ListItem key={msg.message_id} disablePadding>
                                                <ListItemButton
                                                    onClick={() => !isUnknown && handleToggleMessage(msg.message_id)}
                                                    disabled={isUnknown}
                                                >
                                                    <Checkbox
                                                        edge="start"
                                                        checked={selectedMessageIds.includes(msg.message_id)}
                                                        disabled={isUnknown}
                                                        tabIndex={-1}
                                                        disableRipple
                                                    />
                                                    <ListItemText
                                                        primary={
                                                            <Typography
                                                                sx={{
                                                                    color: isUnknown ? 'text.disabled' : 'text.primary',
                                                                    fontStyle: isUnknown ? 'italic' : 'normal'
                                                                }}
                                                            >
                                                                {msg.message_name}
                                                            </Typography>
                                                        }
                                                        secondary={
                                                            <Typography variant="body2" color="text.secondary">
                                                                ID: {msg.message_id} | Count: {msg.count} |{' '}
                                                                Packets: {msg.packet_numbers.slice(0, 5).join(', ')}
                                                                {msg.packet_numbers.length > 5 && '...'}
                                                            </Typography>
                                                        }
                                                    />
                                                </ListItemButton>
                                            </ListItem>
                                        )
                                    })}
                                </List>
                            </Box>
                        )}

                        {/* No messages found */}
                        {pcapResults && pcapResults.messages.length === 0 && (
                            <Alert severity="warning" sx={{ marginTop: 3 }}>
                                No IRP messages found in PCAP file
                            </Alert>
                        )}
                    </Box>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setPcapDialogOpen(false)}>Cancel</Button>
                    <Button
                        variant="contained"
                        color="primary"
                        onClick={handleLoadSelectedMessages}
                        disabled={selectedMessageIds.length === 0 || isLoading}
                    >
                        {isLoading ? 'Loading...' : `Load Messages (${selectedMessageIds.length})`}
                    </Button>
                </DialogActions>
            </Dialog>
        </Layout>
    )
}
