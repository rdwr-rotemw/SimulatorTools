import React, {useEffect, useState} from 'react'
import {useNavigate, useSearchParams} from 'react-router-dom'
import {
    Alert,
    Box,
    Button,
    Chip,
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
    Pagination,
} from '@mui/material'
import SendIcon from '@mui/icons-material/Send'
import AddIcon from '@mui/icons-material/Add'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import ExpandLessIcon from '@mui/icons-material/ExpandLess'
import DeleteIcon from '@mui/icons-material/Delete'
import ContentCopyIcon from '@mui/icons-material/ContentCopy'
import CasinoIcon from '@mui/icons-material/Casino'
import LoopIcon from '@mui/icons-material/Loop'
import StopIcon from '@mui/icons-material/Stop'
import ScienceIcon from '@mui/icons-material/Science'
import UnfoldMoreIcon from '@mui/icons-material/UnfoldMore'
import UnfoldLessIcon from '@mui/icons-material/UnfoldLess'
import FullscreenIcon from '@mui/icons-material/Fullscreen'
import FullscreenExitIcon from '@mui/icons-material/FullscreenExit'
import UploadFileIcon from '@mui/icons-material/UploadFile'
import UploadIcon from '@mui/icons-material/Upload'
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward'
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward'
import DragIndicatorIcon from '@mui/icons-material/DragIndicator'
import DeleteSweepIcon from '@mui/icons-material/DeleteSweep'
import {IRPPcapAnalysisResponse} from '../api/services/irpSchema.service'
import Checkbox from '@mui/material/Checkbox'
import IRPAttackIdConfigDialog from '../components/irp/IRPAttackIdConfigDialog'
import {
    DndContext,
    closestCenter,
    KeyboardSensor,
    PointerSensor,
    useSensor,
    useSensors,
    DragEndEvent,
} from '@dnd-kit/core'
import {
    arrayMove,
    SortableContext,
    sortableKeyboardCoordinates,
    verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import {useSortable} from '@dnd-kit/sortable'
import {CSS} from '@dnd-kit/utilities'

import Layout from '../components/common/Layout'
import ImportModeDialog from '../components/common/ImportModeDialog'
import useCCStore from '../store/ccStore'
import useFormStore from '../store/useFormStore'
import useAuthStore from '../store/authStore'
import {irpSchemaService, SchemaMessage} from '../api/services/irpSchema.service'
import {irpLoopService} from '../api/services/irpLoop.service'
import {formStateService} from '../api/services/formState.service'
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

    Object.keys(schema).forEach(key => {
        const value = schema[key]
        if (value && typeof value === 'object' && (value.type || value.fieldType || value.fields || value.itemSchema)) {
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

// ============================================================================
// SORTABLE MESSAGE COMPONENT
// ============================================================================
interface SortableMessageProps {
    id: number
    index: number
    msg: any
    isExpanded: boolean
    isFirst: boolean
    isLast: boolean
    onToggle: () => void
    onDelete: () => void
    onDuplicate: () => void
    onUpdate: (data: Record<string, any>) => void
    onMoveUp: () => void
    onMoveDown: () => void
    onTestMessage: () => void
    onRandomize: () => void
    onValidationChange: (isValid: boolean) => void
    isTestingMessage: boolean
    isValid: boolean
    messages: any[]
    setMessages: (messages: any[]) => void
}

const SortableMessage: React.FC<SortableMessageProps> = React.memo(({
                                                                        id,
                                                                        index,
                                                                        msg,
                                                                        isExpanded,
                                                                        isFirst,
                                                                        isLast,
                                                                        onToggle,
                                                                        onDelete,
                                                                        onDuplicate,
                                                                        onUpdate,
                                                                        onMoveUp,
                                                                        onMoveDown,
                                                                        onTestMessage,
                                                                        onRandomize,
                                                                        onValidationChange,
                                                                        isTestingMessage,
                                                                        isValid,
                                                                        messages,
                                                                        setMessages
                                                                    }) => {
    const {
        attributes,
        listeners,
        setNodeRef,
        transform,
        transition,
        isDragging,
    } = useSortable({id})

    const style = {
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.5 : 1,
    }

    return (
        <Paper ref={setNodeRef} style={style} id={`irp-message-${index}`} sx={{marginBottom: 2, padding: 2}}>
            <Box sx={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 2}}>
                {/* Left side: Drag handle + Up/Down arrows */}
                <Box sx={{display: 'flex', alignItems: 'center', gap: 0.5}}>
                    <IconButton
                        {...attributes}
                        {...listeners}
                        size="small"
                        sx={{cursor: 'grab', '&:active': {cursor: 'grabbing'}}}
                    >
                        <DragIndicatorIcon/>
                    </IconButton>
                    <IconButton
                        size="small"
                        onClick={onMoveUp}
                        disabled={isFirst}
                        color="primary"
                    >
                        <ArrowUpwardIcon fontSize="small"/>
                    </IconButton>
                    <IconButton
                        size="small"
                        onClick={onMoveDown}
                        disabled={isLast}
                        color="primary"
                    >
                        <ArrowDownwardIcon fontSize="small"/>
                    </IconButton>
                    <Typography variant="h6" sx={{marginLeft: 1}}>{msg.messageName}</Typography>
                </Box>

                {/* Right side: Action buttons */}
                <Box>
                    <IconButton onClick={onToggle}>
                        {isExpanded ? <ExpandLessIcon/> : <ExpandMoreIcon/>}
                    </IconButton>
                    <Tooltip title="Generate random values (preserves iterations)">
                        <IconButton onClick={onRandomize} size="small">
                            <CasinoIcon fontSize="small"/>
                        </IconButton>
                    </Tooltip>
                    <Tooltip title="Test message parsing">
                        <IconButton
                            onClick={onTestMessage}
                            size="small"
                            color="primary"
                            disabled={!isValid || isTestingMessage}
                        >
                            <ScienceIcon fontSize="small"/>
                        </IconButton>
                    </Tooltip>
                    <Tooltip title="Duplicate message">
                        <IconButton onClick={onDuplicate} size="small">
                            <ContentCopyIcon fontSize="small"/>
                        </IconButton>
                    </Tooltip>
                    <IconButton onClick={onDelete} color="error">
                        <DeleteIcon/>
                    </IconButton>
                </Box>
            </Box>
            <Collapse in={isExpanded} unmountOnExit>
                <IRPMessageForm
                    messageData={msg.data}
                    schema={msg.schema}
                    onChange={onUpdate}
                    onValidationChange={onValidationChange}
                />
                <TextField
                    label="Pause After Message (seconds)"
                    type="number"
                    size="small"
                    fullWidth
                    value={msg.pause ?? ''}
                    onChange={(e) => {
                        const newMessages = [...messages]
                        newMessages[index].pause = e.target.value ? parseInt(e.target.value) : undefined
                        setMessages(newMessages)
                    }}
                    inputProps={{min: 0, max: 60, step: 1}}
                    helperText="Optional: Wait before sending next message (max 60s)"
                    sx={{marginTop: 2}}
                />
            </Collapse>
        </Paper>
    )
}, (prevProps, nextProps) => {
    // Custom comparison to prevent unnecessary re-renders
    return (
        prevProps.id === nextProps.id &&
        prevProps.index === nextProps.index &&
        prevProps.msg === nextProps.msg &&
        prevProps.isExpanded === nextProps.isExpanded &&
        prevProps.isFirst === nextProps.isFirst &&
        prevProps.isLast === nextProps.isLast &&
        prevProps.isTestingMessage === nextProps.isTestingMessage &&
        prevProps.isValid === nextProps.isValid
    )
})

export const IRPSenderPage: React.FC = () => {
    const navigate = useNavigate()
    const [searchParams] = useSearchParams()
    const schemaId = searchParams.get('schema_id')

    const currentCC = useCCStore((state) => state.currentCC)
    const allDevices = useCCStore((state) => state.devices)
    const saproSimulators = useCCStore((state) => state.saproSimulators)

    // Filter devices: only show those that exist in Sapro
    const saproIPs = new Set(saproSimulators.map(sim => sim.ip_address))
    const devices = allDevices.filter(device => saproIPs.has(device.management_ip))

    const managementPorts = useCCStore((state) => state.managementPorts)
    const user = useAuthStore((state) => state.user)

    const [schemaInfo, setSchemaInfo] = useState<{ name: string; version: string } | null>(null)
    const [selectedSimulators, setSelectedSimulators] = useState<string[]>([])
    const [selectedDestinationPort, setSelectedDestinationPort] = useState<string>('')
    const [messages, setMessages] = useState<Array<{
        messageType: string;
        messageName: string;
        data: Record<string, any>;
        schema: Record<string, any>;
        originalSchema: Record<string, any>;
        pause?: number;
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

    // Sending progress state
    const [isSending, setIsSending] = useState(false);
    const [currentMessage, setCurrentMessage] = useState(0);
    const [totalMessages, setTotalMessages] = useState(0);
    const [scrollToMessageIndex, setScrollToMessageIndex] = useState<number | null>(null);

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

    // Loop functionality state (now managed by backend)
    const [loopDialogOpen, setLoopDialogOpen] = useState(false)
    const [loopStatusDialogOpen, setLoopStatusDialogOpen] = useState(false)
    const [loopDelay, setLoopDelay] = useState<number>(15)
    const [loopTimeout, setLoopTimeout] = useState<number>(600)
    const [isLooping, setIsLooping] = useState<boolean>(false) // Backend loop status
    const [batchesSent, setBatchesSent] = useState<number>(0) // Number of batches sent
    const [failedBatches, setFailedBatches] = useState<number>(0) // Number of failed batches
    const [lastError, setLastError] = useState<string | null>(null) // Most recent error
    const [remainingSeconds, setRemainingSeconds] = useState<number>(0) // Time remaining
    const statusPollIntervalRef = React.useRef<NodeJS.Timeout | null>(null)
    const formSaveTimerRef = React.useRef<NodeJS.Timeout | null>(null)

    // Check if any message data (at any nesting level) contains attack-id fields
    const hasAttackIdFields = (data: any): boolean => {
        if (!data || typeof data !== 'object') return false
        if ('attack-id' in data) return true
        return Object.values(data).some((value: any) => {
            if (Array.isArray(value)) return value.some(item => hasAttackIdFields(item))
            if (value && typeof value === 'object') return hasAttackIdFields(value)
            return false
        })
    }

    // Attack-ID configuration dialog state
    const [attackIdDialogOpen, setAttackIdDialogOpen] = useState(false)
    const [pendingAction, setPendingAction] = useState<'send' | 'loop' | null>(null)
    const [pendingLoopPerSimMessages, setPendingLoopPerSimMessages] = useState<Record<string, any[]> | null>(null)

    // PCAP Import state
    const [pcapDialogOpen, setPcapDialogOpen] = useState(false)

    // JSON Import state
    const [importProgress, setImportProgress] = useState<number>(0)
    const [isImporting, setIsImporting] = useState<boolean>(false)
    const [isFullscreen, setIsFullscreen] = useState(false)
    const [messagePage, setMessagePage] = useState(1)
    const MESSAGES_PER_PAGE = 20
    const jsonFileInputRef = React.useRef<HTMLInputElement>(null)

    // Import mode dialog (replace vs add)
    const MAX_IRP_MESSAGES = 100
    const [importModeDialogOpen, setImportModeDialogOpen] = useState(false)
    const pendingImportRef = React.useRef<{ items: any[], expanded: number[] } | null>(null)

    const confirmImport = (newItems: any[], expandedItems: number[]) => {
        if (newItems.length > MAX_IRP_MESSAGES) {
            setSnackbar({open: true, message: `Cannot import ${newItems.length} messages. Maximum is ${MAX_IRP_MESSAGES}.`, severity: 'error'})
            return
        }
        if (messages.length === 0) {
            setMessages(newItems)
            setExpandedMessages(expandedItems)
            setMessagePage(1)
            return
        }
        pendingImportRef.current = { items: newItems, expanded: expandedItems }
        setImportModeDialogOpen(true)
    }

    const handleImportReplace = () => {
        if (pendingImportRef.current) {
            if (pendingImportRef.current.items.length > MAX_IRP_MESSAGES) {
                setSnackbar({open: true, message: `Cannot import ${pendingImportRef.current.items.length} messages. Maximum is ${MAX_IRP_MESSAGES}.`, severity: 'error'})
                pendingImportRef.current = null
                setImportModeDialogOpen(false)
                return
            }
            setMessages(pendingImportRef.current.items)
            setExpandedMessages(pendingImportRef.current.expanded)
            setMessagePage(1)
            pendingImportRef.current = null
        }
        setImportModeDialogOpen(false)
    }

    const handleImportAdd = () => {
        if (pendingImportRef.current) {
            const totalAfterAdd = messages.length + pendingImportRef.current.items.length
            if (totalAfterAdd > MAX_IRP_MESSAGES) {
                setSnackbar({open: true, message: `Cannot add ${pendingImportRef.current.items.length} messages. Total would be ${totalAfterAdd}, maximum is ${MAX_IRP_MESSAGES}.`, severity: 'error'})
                pendingImportRef.current = null
                setImportModeDialogOpen(false)
                return
            }
            setMessages(prev => [...prev, ...pendingImportRef.current!.items])
            setMessagePage(1)
            pendingImportRef.current = null
        }
        setImportModeDialogOpen(false)
    }

    const handleImportCancel = () => {
        pendingImportRef.current = null
        setImportModeDialogOpen(false)
    }

    // Pagination computed values
    const totalPages = Math.max(1, Math.ceil(messages.length / MESSAGES_PER_PAGE))
    const safeMessagePage = Math.min(messagePage, totalPages)
    const pageStartIndex = (safeMessagePage - 1) * MESSAGES_PER_PAGE
    const visibleMessages = messages.slice(pageStartIndex, pageStartIndex + MESSAGES_PER_PAGE)
    const visibleIndices = visibleMessages.map((_, i) => pageStartIndex + i)

    // ========================================================================
    // DRAG AND DROP SENSORS
    // ========================================================================
    const sensors = useSensors(
        useSensor(PointerSensor, {
            activationConstraint: {
                distance: 8, // 8px movement required to start drag
            },
        }),
        useSensor(KeyboardSensor, {
            coordinateGetter: sortableKeyboardCoordinates,
        })
    )
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

    // Set current session and restore form state from MongoDB on mount
    useEffect(() => {
        if (currentCC && user) {
            useFormStore.getState().setCurrentSession(currentCC, user.username)
        }

        if (!currentCC || messages.length > 0) return

        let cancelled = false
        formStateService.loadIrpFormState(currentCC).then(formState => {
            if (cancelled) return
            if (formState.messages && formState.messages.length > 0) {
                setMessages(formState.messages)
                setExpandedMessages(formState.expandedMessages)
                setSnackbar({
                    open: true,
                    message: `Messages restored from previous session (${formState.messages.length} message(s))`,
                    severity: 'info'
                })
            }
        }).catch(err => {
            console.error('Failed to load IRP form state:', err)
        })

        return () => { cancelled = true }
    }, [])  // eslint-disable-line react-hooks/exhaustive-deps

    // Poll loop status from backend every 10 seconds
    useEffect(() => {
        const fetchLoopStatus = async () => {
            try {
                const status = await irpLoopService.getStatus();
                setIsLooping(status.is_active);
                setBatchesSent(status.batches_sent);
                setFailedBatches(status.failed_batches);
                setLastError(status.last_error);
                setRemainingSeconds(status.remaining_seconds);

                // If loop is active, restore UI state
                if (status.is_active && (status.simulators?.length || status.simulator)) {
                    setSelectedSimulators(status.simulators?.length ? status.simulators : [status.simulator!]);
                    if (status.destination_port) {
                        setSelectedDestinationPort(status.destination_port);
                    }
                    if (status.loop_delay) {
                        setLoopDelay(status.loop_delay);
                    }
                    if (status.loop_timeout) {
                        setLoopTimeout(status.loop_timeout);
                    }
                }
            } catch (error: any) {
                console.error('Failed to fetch IRP loop status:', error);
            }
        };

        // Fetch initial status
        fetchLoopStatus();

        // Set up polling every 10 seconds to update status
        statusPollIntervalRef.current = setInterval(fetchLoopStatus, 10000);

        // Cleanup on unmount
        return () => {
            if (statusPollIntervalRef.current) {
                clearInterval(statusPollIntervalRef.current);
                statusPollIntervalRef.current = null;
            }
        };
    }, [])

    const compatibleSimulators = devices.filter((d) => {
        const saproSim = saproSimulators.find(sim => sim.ip_address === d.management_ip)
        return saproSim?.version === schemaInfo?.version
    })

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
        if (messages.length >= MAX_IRP_MESSAGES) {
            setSnackbar({open: true, message: `Cannot add message. Maximum of ${MAX_IRP_MESSAGES} messages reached.`, severity: 'error'})
            return
        }
        try {
            setIsLoading(true)
            const template = await irpSchemaService.getMessageTemplate(currentCC!, schemaId!, messageType)

            const transformedData = transformToAttackId(template.template, template.schema)
            const transformedSchema = transformSchemaForAttackId(template.schema)

            setMessages((prev) => {
                const newMessages = [...prev, {
                    messageType,
                    messageName,
                    data: transformedData,
                    schema: transformedSchema,
                    originalSchema: template.schema,
                }]
                // Navigate to last page so the new message is visible
                setMessagePage(Math.ceil(newMessages.length / MESSAGES_PER_PAGE))
                return newMessages
            })
            setExpandedMessages((prev) => [...prev, messages.length])
            setAddMessageDialogOpen(false)
            setSnackbar({open: true, message: `Added ${messageName}`, severity: 'success'})
        } catch (error: any) {
            setSnackbar({open: true, message: 'Failed to load message template', severity: 'error'})
        } finally {
            setIsLoading(false)
        }
    }

    const handleToggleAllMessages = async () => {
        const allVisibleExpanded = visibleIndices.length > 0 && visibleIndices.every(i => expandedMessages.includes(i))
        if (allVisibleExpanded) {
            // Collapse all at once (cheap — unmountOnExit handles cleanup)
            setExpandedMessages(prev => prev.filter(i => !visibleIndices.includes(i)))
        } else {
            // Expand one at a time with a frame delay so each form mounts without freezing
            const toExpand = visibleIndices.filter(i => !expandedMessages.includes(i))
            for (const idx of toExpand) {
                setExpandedMessages(prev => [...prev, idx])
                await new Promise(resolve => requestAnimationFrame(resolve))
            }
        }
    }

    const deleteMessage = (index: number) => {
        setMessages((prev) => prev.filter((_, i) => i !== index))
        setExpandedMessages((prev) => prev.filter((i) => i !== index).map((i) => (i > index ? i - 1 : i)))
    }

    const duplicateMessage = (index: number) => {
        if (messages.length >= MAX_IRP_MESSAGES) {
            setSnackbar({open: true, message: `Cannot duplicate. Maximum of ${MAX_IRP_MESSAGES} messages reached.`, severity: 'error'})
            return
        }
        setMessages((prev) => {
            const clone = JSON.parse(JSON.stringify(prev[index]))
            const next = [...prev]
            next.splice(index + 1, 0, clone)
            return next
        })
        setExpandedMessages((prev) => {
            const shifted = prev.map((i) => (i > index ? i + 1 : i))
            return [...shifted, index + 1]
        })
        setScrollToMessageIndex(index + 1)
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

    // ========================================================================
    // MESSAGE REORDERING FUNCTIONS - OPTIMIZED
    // ========================================================================

    // Move message up - OPTIMIZED with React.startTransition
    const moveMessageUp = (index: number) => {
        if (index === 0) return

        // Use React batching for multiple state updates
        React.startTransition(() => {
            setMessages((prev) => arrayMove(prev, index, index - 1))
            setExpandedMessages((prev) => {
                return prev.map((i) => {
                    if (i === index) return index - 1
                    if (i === index - 1) return index
                    return i
                })
            })
            // Update validation state map indices
            setMessageValidationState((prev) => {
                const newMap = new Map()
                prev.forEach((value, key) => {
                    if (key === index) {
                        newMap.set(index - 1, value)
                    } else if (key === index - 1) {
                        newMap.set(index, value)
                    } else {
                        newMap.set(key, value)
                    }
                })
                return newMap
            })
        })
    }

    // Move message down - OPTIMIZED with React.startTransition
    const moveMessageDown = (index: number) => {
        if (index === messages.length - 1) return

        // Use React batching for multiple state updates
        React.startTransition(() => {
            setMessages((prev) => arrayMove(prev, index, index + 1))
            setExpandedMessages((prev) => {
                return prev.map((i) => {
                    if (i === index) return index + 1
                    if (i === index + 1) return index
                    return i
                })
            })
            // Update validation state map indices
            setMessageValidationState((prev) => {
                const newMap = new Map()
                prev.forEach((value, key) => {
                    if (key === index) {
                        newMap.set(index + 1, value)
                    } else if (key === index + 1) {
                        newMap.set(index, value)
                    } else {
                        newMap.set(key, value)
                    }
                })
                return newMap
            })
        })
    }

    // Handle drag end - OPTIMIZED with React.startTransition
    const handleDragEnd = (event: DragEndEvent) => {
        const {active, over} = event

        if (!over || active.id === over.id) return

        const oldIndex = Number(active.id)
        const newIndex = Number(over.id)

        if (oldIndex === newIndex) return

        // Use React batching for multiple state updates
        React.startTransition(() => {
            setMessages((prev) => arrayMove(prev, oldIndex, newIndex))

            // Update expanded messages indices
            setExpandedMessages((prev) => {
                return prev.map((expandedIdx) => {
                    if (expandedIdx === oldIndex) return newIndex
                    if (expandedIdx > oldIndex && expandedIdx <= newIndex) return expandedIdx - 1
                    if (expandedIdx < oldIndex && expandedIdx >= newIndex) return expandedIdx + 1
                    return expandedIdx
                })
            })

            // Update validation state map indices
            setMessageValidationState((prev) => {
                const newMap = new Map()
                prev.forEach((value, key) => {
                    let newKey = key
                    if (key === oldIndex) {
                        newKey = newIndex
                    } else if (key > oldIndex && key <= newIndex) {
                        newKey = key - 1
                    } else if (key < oldIndex && key >= newIndex) {
                        newKey = key + 1
                    }
                    newMap.set(newKey, value)
                })
                return newMap
            })
        })
    }

    // ========================================================================
    // MEMOIZED CALLBACKS FOR PERFORMANCE
    // ========================================================================

    // Memoize callbacks to prevent re-creating functions on every render
    const memoizedToggleMessage = React.useCallback((index: number) => {
        toggleMessage(index)
    }, [])

    const memoizedDeleteMessage = React.useCallback((index: number) => {
        deleteMessage(index)
    }, [])

    const memoizedDuplicateMessage = React.useCallback((index: number) => {
        duplicateMessage(index)
    }, [])

    const memoizedUpdateMessage = React.useCallback((index: number, data: Record<string, any>) => {
        updateMessage(index, data)
    }, [])

    const memoizedMoveUp = React.useCallback((index: number) => {
        moveMessageUp(index)
    }, [])  // eslint-disable-line react-hooks/exhaustive-deps

    const memoizedMoveDown = React.useCallback((index: number) => {
        moveMessageDown(index)
    }, [])  // eslint-disable-line react-hooks/exhaustive-deps

    const memoizedRandomize = React.useCallback((index: number, msg: any) => {
        const randomData = generateRandomData(msg.schema, msg.data)
        updateMessage(index, randomData)
    }, [])

    const memoizedValidationChange = React.useCallback((index: number, isValid: boolean) => {
        setMessageValidationState(prev => {
            const newMap = new Map(prev)
            newMap.set(index, isValid)
            return newMap
        })
    }, [])

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

            // Deduplicate: fetch only unique message types, batched
            const uniqueTypes = new Set<string>(template.messages.map((msg: any) => msg.messageType))
            const schemaCache = new Map<string, any>()
            const uniqueEntries = Array.from(uniqueTypes)

            for (let batchStart = 0; batchStart < uniqueEntries.length; batchStart += MESSAGES_PER_PAGE) {
                const batch = uniqueEntries.slice(batchStart, batchStart + MESSAGES_PER_PAGE)
                const batchResults = await Promise.all(
                    batch.map(messageType =>
                        irpSchemaService.getMessageTemplate(currentCC!, schemaId!, messageType, 600000)
                            .then(tmpl => ({ messageType, tmpl }))
                            .catch(() => ({ messageType, tmpl: null }))
                    )
                )
                for (const { messageType, tmpl } of batchResults) {
                    if (tmpl) schemaCache.set(messageType, tmpl)
                }
            }

            const messagesWithSchemas = template.messages.map((msg: any) => {
                const cached = schemaCache.get(msg.messageType)
                if (cached) {
                    const transformedData = transformToAttackId(msg.data, cached.schema)
                    const transformedSchema = transformSchemaForAttackId(cached.schema)
                    return {
                        ...msg,
                        data: transformedData,
                        schema: transformedSchema,
                        originalSchema: cached.schema
                    }
                }
                return { ...msg, schema: {}, originalSchema: {} }
            })

            setLoadDialogOpen(false)
            confirmImport(messagesWithSchemas, [])
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

            // Deduplicate: fetch only unique message types, batched
            const uniqueTypes = new Set<string>(selectedMessageIds)
            const schemaCache = new Map<string, any>()
            const fetchErrors = new Set<string>()
            const uniqueEntries = Array.from(uniqueTypes)

            for (let batchStart = 0; batchStart < uniqueEntries.length; batchStart += MESSAGES_PER_PAGE) {
                const batch = uniqueEntries.slice(batchStart, batchStart + MESSAGES_PER_PAGE)
                const batchResults = await Promise.all(
                    batch.map(messageType =>
                        irpSchemaService.getMessageTemplate(currentCC!, schemaId!, messageType, 600000)
                            .then(tmpl => ({ messageType, tmpl }))
                            .catch(() => ({ messageType, tmpl: null }))
                    )
                )
                for (const { messageType, tmpl } of batchResults) {
                    if (tmpl) schemaCache.set(messageType, tmpl)
                    else fetchErrors.add(messageType)
                }
            }

            const loadedMessages: any[] = []
            const failedMessages: string[] = []

            for (const messageId of selectedMessageIds) {
                const message = pcapResults?.messages.find(msg => msg.message_id === messageId)
                if (!message) continue

                const cached = schemaCache.get(messageId)
                if (cached) {
                    const transformedData = transformToAttackId(cached.template, cached.schema)
                    const transformedSchema = transformSchemaForAttackId(cached.schema)
                    loadedMessages.push({
                        messageType: messageId,
                        messageName: message.message_name,
                        data: transformedData,
                        schema: transformedSchema,
                        originalSchema: cached.schema,
                    })
                } else {
                    failedMessages.push(`${message.message_name} (ID: ${messageId})`)
                }
            }

            setPcapDialogOpen(false)
            const expandedIndices = loadedMessages.map((_: any, index: number) => index)
            confirmImport(loadedMessages, expandedIndices)

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

    // Helper function: Merge imported data with template (fills missing fields)
    function mergeWithTemplate(
        importedData: Record<string, any>,
        templateData: Record<string, any>,
        schema: Record<string, any>
    ): Record<string, any> {
        const result: Record<string, any> = {...templateData}

        Object.keys(importedData).forEach(key => {
            if (key in schema || key in result) {
                result[key] = importedData[key]
            }
            // Ignore extra fields not in schema
        })

        return result
    }

    // Import JSON with values
    const handleImportJSON = async (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0]
        if (!file) return

        // Validate file type
        if (!file.name.toLowerCase().endsWith('.json')) {
            setSnackbar({open: true, message: 'Please select a .json file', severity: 'error'})
            return
        }

        setIsImporting(true)
        setImportProgress(0)

        // Helper: yield to UI thread so progress renders
        const yieldToUI = () => new Promise<void>(resolve => setTimeout(resolve, 0))

        try {
            // 1. Parse and validate JSON file
            const fileContent = await file.text()
            const imported = JSON.parse(fileContent)

            if (!imported.messages || !Array.isArray(imported.messages)) {
                throw new Error('Invalid JSON format: missing "messages" array')
            }

            const messagesToImport = imported.messages

            if (messagesToImport.length === 0) {
                throw new Error('No messages found in JSON file')
            }

            // Validate each message has required 'message' field
            const invalidIndices: number[] = []
            for (let i = 0; i < messagesToImport.length; i++) {
                const msg = messagesToImport[i]
                if (!msg || typeof msg !== 'object') {
                    invalidIndices.push(i + 1)
                } else if (!msg.message && !msg.messageType) {
                    invalidIndices.push(i + 1)
                }
            }
            if (invalidIndices.length > 0) {
                throw new Error(
                    `Invalid messages at position(s) ${invalidIndices.slice(0, 5).join(', ')}${invalidIndices.length > 5 ? ` and ${invalidIndices.length - 5} more` : ''}: each message must have a "message" (name) or "messageType" field`
                )
            }

            setImportProgress(10)
            await yieldToUI()

            // 2. Get list of available messages for name->type mapping
            const availableMessages = await irpSchemaService.listMessages(currentCC!, schemaId!, 600000)
            const messageNameToType = new Map(availableMessages.map(m => [m.name, m.id]))

            setImportProgress(20)
            await yieldToUI()

            // 3. Resolve message types and collect unique ones
            const uniqueMessageTypes = new Map<string, string>() // messageType -> messageName
            const resolvedTypes: Array<{ messageType: string | null, messageName: string }> = []

            for (const msg of messagesToImport) {
                const messageType = msg.messageType || messageNameToType.get(msg.message)
                resolvedTypes.push({ messageType: messageType || null, messageName: msg.message })
                if (messageType && !uniqueMessageTypes.has(messageType)) {
                    uniqueMessageTypes.set(messageType, msg.message)
                }
            }

            // 4. Fetch unique templates in batches of MESSAGES_PER_PAGE
            const templateCache = new Map<string, any>()
            const templateErrors = new Map<string, string>()
            const uniqueEntries = Array.from(uniqueMessageTypes.entries())

            for (let batchStart = 0; batchStart < uniqueEntries.length; batchStart += MESSAGES_PER_PAGE) {
                const batch = uniqueEntries.slice(batchStart, batchStart + MESSAGES_PER_PAGE)
                const batchResults = await Promise.all(
                    batch.map(([messageType, messageName]) =>
                        irpSchemaService.getMessageTemplate(currentCC!, schemaId!, messageType, 600000)
                            .then(tmpl => ({ messageType, tmpl, error: false as const }))
                            .catch(err => ({ messageType, tmpl: null, error: true as const, reason: err.message, messageName }))
                    )
                )

                for (const result of batchResults) {
                    if (!result.error) {
                        templateCache.set(result.messageType, result.tmpl)
                    } else {
                        templateErrors.set(result.messageType, (result as any).reason)
                    }
                }

                // Update progress: 20% (parsing) + 30% (template fetching spread across batches)
                const fetchProgress = 20 + ((batchStart + batch.length) / uniqueEntries.length) * 30
                setImportProgress(fetchProgress)
                await yieldToUI()
            }

            // 5. Process each message (all in memory, no more API calls)
            const results: Array<{
                success: boolean
                messageName: string
                messageType?: string
                error?: string
                warnings?: string[]
            }> = []

            const successfulMessages: Array<{
                messageType: string
                messageName: string
                data: Record<string, any>
                schema: Record<string, any>
                originalSchema: Record<string, any>
                pause?: number
            }> = []

            // Pre-compute transformed schemas per unique type (avoids recomputing for each message)
            const transformedSchemaCache = new Map<string, any>()

            for (let i = 0; i < messagesToImport.length; i++) {
                const msg = messagesToImport[i]
                const { messageType, messageName } = resolvedTypes[i]

                if (!messageType) {
                    results.push({ success: false, messageName, error: 'Message type not found in current schema' })
                    continue
                }

                const cached = templateCache.get(messageType)
                if (!cached) {
                    results.push({ success: false, messageName, messageType, error: templateErrors.get(messageType) || 'Template fetch failed' })
                    continue
                }

                const { template, schema, name } = cached
                const { message: _, messageType: __, pause: importedPause, ...importedData } = msg

                try {
                    // Deep-clone template since it's shared across messages of the same type
                    const templateClone = JSON.parse(JSON.stringify(template))

                    const schemaHasTimeCnt = 'time' in schema && 'cnt' in schema
                    const schemaHasAttackId = 'attack-id' in schema
                    const isMsg1 = messageType === '1'

                    let finalData: Record<string, any>
                    let warnings: string[] = []

                    if (!schemaHasTimeCnt && !schemaHasAttackId) {
                        finalData = mergeWithTemplate(importedData, templateClone, schema)
                    } else {
                        const hasAttackId = 'attack-id' in importedData
                        const hasTime = 'time' in importedData
                        const hasCnt = 'cnt' in importedData

                        if (isMsg1) {
                            if (hasAttackId && hasTime) {
                                finalData = mergeWithTemplate(importedData, templateClone, schema)
                            } else {
                                warnings.push('Message 1 requires both attack-id and time fields')
                                finalData = templateClone
                            }
                        } else {
                            if (hasAttackId && !hasCnt && !hasTime) {
                                const [cnt, time] = (importedData['attack-id'] as string).split('-')
                                const backendData = { ...importedData, cnt: parseInt(cnt), time: parseInt(time) }
                                delete backendData['attack-id']
                                const merged = mergeWithTemplate(backendData, templateClone, schema)
                                finalData = transformToAttackId(merged, schema)
                            } else if (hasCnt && hasTime) {
                                const merged = mergeWithTemplate(importedData, templateClone, schema)
                                finalData = transformToAttackId(merged, schema)
                            } else {
                                warnings.push('Missing required fields (cnt+time or attack-id)')
                                finalData = transformToAttackId(templateClone, schema)
                            }
                        }
                    }

                    // Cache transformed schema per type (same schema = same transform)
                    if (!transformedSchemaCache.has(messageType)) {
                        transformedSchemaCache.set(messageType, transformSchemaForAttackId(schema))
                    }

                    successfulMessages.push({
                        messageType,
                        messageName: name,
                        data: finalData,
                        schema: transformedSchemaCache.get(messageType),
                        originalSchema: schema,
                        pause: importedPause
                    })

                    results.push({
                        success: true,
                        messageName: name,
                        messageType,
                        warnings: warnings.length > 0 ? warnings : undefined
                    })

                } catch (err: any) {
                    results.push({ success: false, messageName: name, messageType, error: err.message })
                }

                // Yield to UI every 10 messages so progress bar updates
                if ((i + 1) % 10 === 0 || i === messagesToImport.length - 1) {
                    setImportProgress(50 + ((i + 1) / messagesToImport.length) * 45)
                    await yieldToUI()
                }
            }

            setImportProgress(98)
            await yieldToUI()

            // 6. Single state update (don't auto-expand — rendering many expanded forms freezes UI)
            confirmImport(successfulMessages, [])

            // 7. Show summary
            const successful = results.filter(r => r.success).length
            const failed = results.filter(r => !r.success).length
            const withWarnings = results.filter(r => r.success && r.warnings?.length).length

            let message = `Imported ${successful}/${results.length} messages`
            if (withWarnings > 0) message += ` (${withWarnings} with warnings)`
            if (failed > 0) message += ` - ${failed} failed`

            setSnackbar({
                open: true,
                message,
                severity: failed > 0 ? 'warning' : 'success'
            })

            if (failed > 0 || withWarnings > 0) {
                console.group('Import Details')
                results.forEach(r => {
                    if (!r.success) {
                        console.error(`Failed: ${r.messageName}: ${r.error}`)
                    } else if (r.warnings?.length) {
                        console.warn(`Warning: ${r.messageName}:`, r.warnings.join(', '))
                    }
                })
                console.groupEnd()
            }

        } catch (error: any) {
            const errorMessage = error instanceof Error ? error.message : 'Failed to import JSON'
            setSnackbar({open: true, message: errorMessage, severity: 'error'})
            console.error('JSON import error:', error)
        } finally {
            setIsImporting(false)
            setImportProgress(0)
            if (jsonFileInputRef.current) {
                jsonFileInputRef.current.value = ''
            }
        }
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
        if (selectedSimulators.length === 0) {
            setSnackbar({open: true, message: 'Please select at least one simulator', severity: 'error'})
            return
        }

        if (!selectedDestinationPort || messages.length === 0) {
            setSnackbar({open: true, message: 'Please select port, and add messages', severity: 'error'})
            return
        }

        // If multiple simulators selected and messages have attack-ID fields, show config dialog
        if (selectedSimulators.length > 1 && messages.some(msg => hasAttackIdFields(msg.data))) {
            setPendingAction('send');
            setAttackIdDialogOpen(true);
            return;
        }

        // Before sending
        setIsSending(true);
        setCurrentMessage(0);
        setTotalMessages(messages.length);

        try {
            const formattedMessages = messages.map((msg) => {
                const backendData = transformFromAttackId(msg.data, msg.originalSchema)
                return {
                    message: msg.messageName,
                    pause: msg.pause,
                    ...backendData,
                }
            })

            const payload = {
                mongo_id: schemaId!,
                // IRP doesn't use map folder (sends raw UDP), but include for API consistency
                map: '',
                message_data: {
                    messages: formattedMessages,
                },
            }

            await irpSchemaService.sendMessagesWithProgress(
                selectedDestinationPort,
                selectedSimulators,
                payload,
                (current, total, messageName, status) => {
                    setCurrentMessage(current);
                    setTotalMessages(total);
                },
                (successCount, failedCount, totalCount) => {
                    if (failedCount === 0) {
                        setSnackbar({
                            open: true,
                            message: `Successfully sent all ${successCount} message(s)`,
                            severity: 'success'
                        })
                    } else if (successCount === 0) {
                        setSnackbar({
                            open: true,
                            message: `Failed to send all ${failedCount} message(s)`,
                            severity: 'error'
                        })
                    } else {
                        setSnackbar({
                            open: true,
                            message: `Partially successful: ${successCount} succeeded, ${failedCount} failed`,
                            severity: 'warning'
                        })
                    }
                },
                (error) => {
                    setSnackbar({open: true, message: error, severity: 'error'})
                }
            )
        } catch (error: any) {
            // Error already handled in onError callback
        } finally {
            // Finally block
            setIsSending(false);
            setCurrentMessage(0);
            setTotalMessages(0);
        }
    }

    // Scroll to newly duplicated message
    useEffect(() => {
        if (scrollToMessageIndex === null) return
        const el = document.getElementById(`irp-message-${scrollToMessageIndex}`)
        if (el) el.scrollIntoView({behavior: 'smooth', block: 'start'})
        setScrollToMessageIndex(null)
    }, [scrollToMessageIndex])

    // Auto-save form state to MongoDB (debounced 2s)
    useEffect(() => {
        if (!currentCC) return

        if (formSaveTimerRef.current) {
            clearTimeout(formSaveTimerRef.current)
        }
        formSaveTimerRef.current = setTimeout(() => {
            if (messages.length > 0) {
                formStateService.saveIrpFormState(currentCC, messages, expandedMessages).catch(err => {
                    console.error('Failed to save IRP form state:', err)
                    setSnackbar({open: true, message: `Auto-save failed: ${err.message}`, severity: 'error'})
                })
            } else {
                formStateService.clearIrpFormState(currentCC).catch(err => {
                    console.error('Failed to clear IRP form state:', err)
                })
            }
        }, 2000)

        return () => {
            if (formSaveTimerRef.current) {
                clearTimeout(formSaveTimerRef.current)
            }
        }
    }, [messages, expandedMessages, currentCC])

    const handleStartLoop = async () => {
        if (!selectedSimulators.length) {
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

        try {
            // Format messages for backend (shared messages for all simulators)
            const formattedMessages = messages.map((msg: any) => {
                const backendData = transformFromAttackId(msg.data, msg.originalSchema)
                return {
                    message: msg.messageName,
                    pause: msg.pause || 0,
                    ...backendData,
                }
            })

            // Start loop via backend API
            const result = await irpLoopService.startLoop({
                cc_ip: currentCC!,
                loop_delay: loopDelay,
                loop_timeout: loopTimeout,
                simulators: selectedSimulators,
                destination_port: selectedDestinationPort,
                schema_id: schemaId!,
                messages: formattedMessages,
                per_simulator_messages: pendingLoopPerSimMessages || undefined,
            });

            // Update local state
            setIsLooping(true);
            setBatchesSent(result.batches_sent);
            setRemainingSeconds(loopTimeout);

            setSnackbar({
                open: true,
                message: `${result.message} - Loop will run for ${loopTimeout}s with ${loopDelay}s delay`,
                severity: 'success'
            });

            // Clear pending state
            setPendingAction(null);
            setPendingLoopPerSimMessages(null);

        } catch (error: any) {
            const errorMsg = error?.response?.data?.detail || error?.message || 'Failed to start loop';
            setSnackbar({open: true, message: `Failed to start loop: ${errorMsg}`, severity: 'error'});
        }
    }

    const handleStopLoop = async () => {
        try {
            // Stop loop via backend API
            const result = await irpLoopService.stopLoop();

            // Update local state
            setIsLooping(false);
            setBatchesSent(result.batches_sent);
            setRemainingSeconds(0);

            setSnackbar({
                open: true,
                message: `${result.message} - Sent ${result.batches_sent} batch(es) in ${result.elapsed_seconds}s`,
                severity: 'success'
            });

        } catch (error: any) {
            const errorMsg = error?.response?.data?.detail || error?.message || 'Failed to stop loop';
            setSnackbar({open: true, message: `Failed to stop loop: ${errorMsg}`, severity: 'error'});
        }
    }

    const handleOpenLoopDialog = () => {
        // Check validations first
        if (!selectedSimulators.length) {
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

        // If multiple simulators and messages have attack-ID fields, show config dialog first
        if (selectedSimulators.length > 1 && messages.some(msg => hasAttackIdFields(msg.data))) {
            setPendingAction('loop');
            setAttackIdDialogOpen(true);
            return;
        }

        // Single simulator: open loop dialog directly
        setLoopDialogOpen(true)
    }

    const handleAttackIdConfirm = async (attackIdConfig: Record<string, any[]>) => {
        setAttackIdDialogOpen(false);

        if (pendingAction === 'send') {
            // Send to all simulators in one request with per-simulator data
            setIsSending(true);
            setCurrentMessage(0);
            setTotalMessages(messages.length * selectedSimulators.length);

            try {
                // Build per-simulator data with custom attack IDs
                const perSimulatorData: Record<string, { messages: Array<Record<string, any>> }> = {};
                for (const simulatorIp of selectedSimulators) {
                    const simMessages = attackIdConfig[simulatorIp];
                    const formattedMessages = simMessages.map((msg: any) => {
                        const backendData = transformFromAttackId(msg.data, msg.originalSchema)
                        return {
                            message: msg.messageName,
                            pause: msg.pause,
                            ...backendData,
                        }
                    })
                    perSimulatorData[simulatorIp] = { messages: formattedMessages };
                }

                const payload = {
                    mongo_id: schemaId!,
                    map: '',
                    message_data: { messages: [] },
                    per_simulator_data: perSimulatorData,
                }

                let successCount = 0;
                let failedCount = 0;

                await irpSchemaService.sendMessagesWithProgress(
                    selectedDestinationPort,
                    selectedSimulators,
                    payload,
                    (current, total, messageName, status) => {
                        setCurrentMessage(current);
                    },
                    (totalSuccess, totalFailed, totalCount) => {
                        successCount = totalSuccess;
                        failedCount = totalFailed;
                    },
                    (error) => {
                        // Error handled in catch
                    }
                );

                if (failedCount === 0) {
                    setSnackbar({
                        open: true,
                        message: `Successfully sent all ${successCount} message(s) to ${selectedSimulators.length} simulator(s)`,
                        severity: 'success'
                    });
                } else if (successCount === 0) {
                    setSnackbar({
                        open: true,
                        message: `Failed to send all ${failedCount} message(s) to ${selectedSimulators.length} simulator(s)`,
                        severity: 'error'
                    });
                } else {
                    setSnackbar({
                        open: true,
                        message: `Partially successful: ${successCount} succeeded, ${failedCount} failed`,
                        severity: 'warning'
                    });
                }
            } catch (error: any) {
                setSnackbar({
                    open: true,
                    message: error.message || 'Failed to send messages',
                    severity: 'error'
                });
            } finally {
                setIsSending(false);
                setCurrentMessage(0);
                setTotalMessages(0);
            }
        } else if (pendingAction === 'loop') {
            // Build per-simulator messages for loop, then open loop dialog
            const perSimulatorMessages: Record<string, any[]> = {};
            for (const simulatorIp of selectedSimulators) {
                const simMessages = attackIdConfig[simulatorIp];
                perSimulatorMessages[simulatorIp] = simMessages.map((msg: any) => {
                    const backendData = transformFromAttackId(msg.data, msg.originalSchema)
                    return {
                        message: msg.messageName,
                        pause: msg.pause || 0,
                        ...backendData,
                    }
                });
            }
            setPendingLoopPerSimMessages(perSimulatorMessages);
            setLoopDialogOpen(true);
        }
        setPendingAction(null);
    }

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
                {/* Fixed Header — hidden in fullscreen mode */}
                {!isFullscreen && <Box sx={{padding: 3, borderBottom: '1px solid #E0E0E0'}}>
                    <Typography variant="h4" sx={{marginBottom: 1}}>
                        IRP Message Sender
                    </Typography>
                    {schemaInfo && (
                        <Alert severity="info" sx={{marginBottom: 2}}>
                            Using schema: {schemaInfo.name} (Version: {schemaInfo.version})
                        </Alert>
                    )}

                    <FormControl fullWidth>
                        <InputLabel id="target-simulator-label">Target Simulator</InputLabel>
                        <Select
                            labelId="target-simulator-label"
                            multiple
                            value={selectedSimulators}
                            onChange={(e) => {
                                const value = e.target.value;
                                const newValue = typeof value === 'string' ? value.split(',') : value;

                                // Check if the special "__SELECT_ALL__" marker is present (from Select All button)
                                if (newValue.includes('__SELECT_ALL__')) {
                                    // Select All was clicked - ignore this onChange and let onClick handle it
                                    return;
                                }

                                // Normal selection change
                                setSelectedSimulators(newValue);
                            }}
                            label="Target Simulator"
                            renderValue={(selected) => (
                                <Box sx={{
                                    display: 'flex',
                                    flexWrap: 'wrap',
                                    gap: 0.5,
                                    maxWidth: 'calc(100% - 40px)', // Leave space for dropdown arrow (Select has no clear button)
                                    overflow: 'hidden'
                                }}>
                                    <Chip
                                        label={`${(selected as string[]).length} simulator(s) selected`}
                                        size="small"
                                        sx={{
                                            backgroundColor: 'primary.main',
                                            color: 'white',
                                            maxWidth: '100%',
                                            '& .MuiChip-label': {
                                                overflow: 'hidden',
                                                textOverflow: 'ellipsis',
                                                whiteSpace: 'nowrap'
                                            }
                                        }}
                                    />
                                </Box>
                            )}
                        >
                            {/* Select All / Deselect All Option */}
                            <MenuItem
                                value="__SELECT_ALL__"
                                onClick={(e) => {
                                    e.stopPropagation();
                                    e.preventDefault();
                                    if (selectedSimulators.length === compatibleSimulators.length) {
                                        setSelectedSimulators([]);
                                    } else {
                                        setSelectedSimulators(compatibleSimulators.map(d => d.management_ip));
                                    }
                                }}
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter' || e.key === ' ') {
                                        e.stopPropagation();
                                        e.preventDefault();
                                        if (selectedSimulators.length === compatibleSimulators.length) {
                                            setSelectedSimulators([]);
                                        } else {
                                            setSelectedSimulators(compatibleSimulators.map(d => d.management_ip));
                                        }
                                    }
                                }}
                                sx={{fontWeight: 'bold', borderBottom: '1px solid #e0e0e0'}}
                            >
                                <ListItemText
                                    primary={selectedSimulators.length === compatibleSimulators.length ? 'Deselect All' : 'Select All'}
                                />
                            </MenuItem>

                            {/* Device Options */}
                            {compatibleSimulators.map((device) => (
                                <MenuItem key={device.management_ip} value={device.management_ip}>
                                    <Checkbox
                                        checked={selectedSimulators.includes(device.management_ip)}
                                        sx={{marginRight: 1}}
                                    />
                                    <ListItemText
                                        primary={`${device.name || device.management_ip} (${device.management_ip})`}
                                        secondary={device.map ? `Map: ${device.map}` : undefined}
                                    />
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
                </Box>}

                {/* Message list toolbar with fullscreen toggle */}
                <Box sx={{display: 'flex', justifyContent: 'flex-end', px: 2, pt: 1}}>
                    <Tooltip title={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}>
                        <IconButton size="small" onClick={() => setIsFullscreen(f => !f)}>
                            {isFullscreen ? <FullscreenExitIcon/> : <FullscreenIcon/>}
                        </IconButton>
                    </Tooltip>
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
                        <>
                            <DndContext
                                sensors={sensors}
                                collisionDetection={closestCenter}
                                onDragEnd={handleDragEnd}
                            >
                                <SortableContext
                                    items={visibleMessages.map((_, i) => pageStartIndex + i)}
                                    strategy={verticalListSortingStrategy}
                                >
                                    {visibleMessages.map((msg, pageIndex) => {
                                        const actualIndex = pageStartIndex + pageIndex
                                        return (
                                            <SortableMessage
                                                key={actualIndex}
                                                id={actualIndex}
                                                index={actualIndex}
                                                msg={msg}
                                                isExpanded={expandedMessages.includes(actualIndex)}
                                                isFirst={actualIndex === 0}
                                                isLast={actualIndex === messages.length - 1}
                                                onToggle={() => memoizedToggleMessage(actualIndex)}
                                                onDelete={() => memoizedDeleteMessage(actualIndex)}
                                                onDuplicate={() => memoizedDuplicateMessage(actualIndex)}
                                                onUpdate={(data) => memoizedUpdateMessage(actualIndex, data)}
                                                onMoveUp={() => memoizedMoveUp(actualIndex)}
                                                onMoveDown={() => memoizedMoveDown(actualIndex)}
                                                onTestMessage={() => handleTestMessage(actualIndex)}
                                                onRandomize={() => memoizedRandomize(actualIndex, msg)}
                                                onValidationChange={(isValid) => memoizedValidationChange(actualIndex, isValid)}
                                                isTestingMessage={testingMessage}
                                                isValid={messageValidationState.get(actualIndex) ?? true}
                                                messages={messages}
                                                setMessages={setMessages}
                                            />
                                        )
                                    })}
                                </SortableContext>
                            </DndContext>
                        </>
                    )}
                </Box>

                {/* Pagination - fixed between message list and footer */}
                {totalPages > 1 && (
                    <Box sx={{ display: 'flex', justifyContent: 'center', py: 1, borderTop: '1px solid #E0E0E0' }}>
                        <Pagination
                            count={totalPages}
                            page={safeMessagePage}
                            onChange={(_, page) => setMessagePage(page)}
                            color="primary"
                            showFirstButton
                            showLastButton
                        />
                    </Box>
                )}

                {/* Fixed Footer */}
                <Box sx={{padding: 3, borderTop: '1px solid #E0E0E0', display: 'flex', gap: 2, flexWrap: 'wrap'}}>
                    <Button variant="outlined" startIcon={<AddIcon/>} onClick={() => setAddMessageDialogOpen(true)}>
                        Add Message
                    </Button>
                    <Button
                        variant="outlined"
                        color="error"
                        startIcon={<DeleteSweepIcon/>}
                        disabled={messages.length === 0}
                        onClick={() => {
                            if (window.confirm(`Delete all ${messages.length} message(s)?`)) {
                                setMessages([])
                                setExpandedMessages([])
                                setMessagePage(1)
                            }
                        }}
                    >
                        Delete All
                    </Button>
                    <Button
                        variant="outlined"
                        startIcon={visibleIndices.length > 0 && visibleIndices.every(i => expandedMessages.includes(i)) ?
                            <UnfoldLessIcon/> : <UnfoldMoreIcon/>}
                        onClick={handleToggleAllMessages}
                        disabled={messages.length === 0}
                    >
                        {visibleIndices.length > 0 && visibleIndices.every(i => expandedMessages.includes(i)) ? 'Collapse All' : 'Expand All'}
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
                        variant="outlined"
                        startIcon={isImporting ? <CircularProgress size={20}/> : <UploadIcon/>}
                        onClick={() => jsonFileInputRef.current?.click()}
                        disabled={isImporting || !schemaId}
                    >
                        {isImporting ? `Importing... ${Math.round(importProgress)}%` : 'Import JSON'}
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
                        startIcon={<UploadFileIcon/>}
                        onClick={handleOpenPcapDialog}
                    >
                        Import from PCAP
                    </Button>
                    <Box sx={{flex: 1}}/>
                    <Button
                        variant="contained"
                        color="primary"
                        startIcon={<SendIcon/>}
                        disabled={!selectedSimulators.length || !selectedDestinationPort || messages.length === 0 || isSending || isLooping || hasValidationErrors}
                        onClick={handleSendMessages}
                    >
                        {isSending ? 'Sending...' : `Send Messages (${messages.length})`}
                    </Button>

                    <Button
                        variant="outlined"
                        color="secondary"
                        onClick={() => setLoopStatusDialogOpen(true)}
                        disabled={!isLooping}
                    >
                        Loop Status
                    </Button>

                    {!isLooping ? (
                        <Button
                            variant="contained"
                            color="secondary"
                            startIcon={<LoopIcon/>}
                            onClick={handleOpenLoopDialog}
                            disabled={!selectedSimulators.length || !selectedDestinationPort || messages.length === 0 || isSending || hasValidationErrors}
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
                        <Alert severity="info" sx={{marginTop: 2}}>
                            Note: Loop runs on the backend and will continue even if you close the browser.
                        </Alert>
                    </DialogContent>
                    <DialogActions>
                        <Button onClick={() => setLoopDialogOpen(false)}>Cancel</Button>
                        <Button onClick={handleStartLoop} variant="contained" color="secondary">
                            Start Loop
                        </Button>
                    </DialogActions>
                </Dialog>

                {/* Loop Status Dialog */}
                <Dialog open={loopStatusDialogOpen} onClose={() => setLoopStatusDialogOpen(false)} maxWidth="sm" fullWidth>
                    <DialogTitle>Loop Status</DialogTitle>
                    <DialogContent>
                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, marginTop: 2 }}>
                            <Box>
                                <Typography variant="subtitle2" color="textSecondary">Status</Typography>
                                <Typography variant="body1">{isLooping ? 'Running' : 'Stopped'}</Typography>
                            </Box>
                            <Box>
                                <Typography variant="subtitle2" color="textSecondary">Batches Sent</Typography>
                                <Typography variant="h4" color="primary">{batchesSent}</Typography>
                            </Box>
                            <Box>
                                <Typography variant="subtitle2" color="textSecondary">Failed Batches</Typography>
                                <Typography variant="h4" color={failedBatches > 0 ? "error" : "textSecondary"}>{failedBatches}</Typography>
                            </Box>
                            {lastError && (
                                <Box>
                                    <Typography variant="subtitle2" color="textSecondary">Last Error</Typography>
                                    <Alert severity="error" sx={{ marginTop: 1 }}>
                                        {lastError}
                                    </Alert>
                                </Box>
                            )}
                            <Box>
                                <Typography variant="subtitle2" color="textSecondary">Time Remaining</Typography>
                                <Typography variant="body1">{remainingSeconds} seconds</Typography>
                            </Box>
                            <Box>
                                <Typography variant="subtitle2" color="textSecondary">Target Simulator</Typography>
                                <Typography variant="body1">{selectedSimulators.length > 0 ? selectedSimulators[0] : 'N/A'}</Typography>
                            </Box>
                            <Alert severity="info">
                                Status updates every 10 seconds automatically.
                            </Alert>
                        </Box>
                    </DialogContent>
                    <DialogActions>
                        <Button onClick={() => setLoopStatusDialogOpen(false)}>Close</Button>
                    </DialogActions>
                </Dialog>

                {/* Attack-ID Configuration Dialog */}
                <IRPAttackIdConfigDialog
                    open={attackIdDialogOpen}
                    onClose={() => {
                        setAttackIdDialogOpen(false);
                        setPendingAction(null);
                    }}
                    simulators={selectedSimulators}
                    messages={messages}
                    onConfirm={handleAttackIdConfirm}
                />

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

                {/* Import Mode Dialog (Replace vs Add) */}
                <ImportModeDialog
                    open={importModeDialogOpen}
                    onClose={handleImportCancel}
                    onReplace={handleImportReplace}
                    onAdd={handleImportAdd}
                    itemCount={messages.length}
                    importCount={pendingImportRef.current?.items.length ?? 0}
                    itemLabel="message"
                />

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

            {/* Sending Progress Dialog */}
            <Dialog
                open={isSending}
                maxWidth="sm"
                fullWidth
                disableEscapeKeyDown
            >
                <DialogContent>
                    <Box sx={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3}}>
                        <CircularProgress size={60}/>
                        <Typography variant="h6">Sending Messages...</Typography>
                        {currentMessage > 0 && (
                            <Typography variant="h5" fontWeight="bold" color="primary">
                                {currentMessage}/{totalMessages}
                            </Typography>
                        )}
                        <Typography variant="body2" color="textSecondary">
                            This may take several minutes with pause delays.
                            Please wait...
                        </Typography>
                    </Box>
                </DialogContent>
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
                    <Box sx={{marginTop: 2}}>
                        {/* File Upload */}
                        <input
                            accept=".pcap,.pcapng"
                            style={{display: 'none'}}
                            id="pcap-file-input"
                            type="file"
                            onChange={handlePcapFileChange}
                        />
                        <label htmlFor="pcap-file-input">
                            <Button
                                variant="outlined"
                                component="span"
                                startIcon={<UploadFileIcon/>}
                                fullWidth
                                disabled={analyzingPcap}
                            >
                                {pcapFile ? pcapFile.name : 'Select PCAP File'}
                            </Button>
                        </label>

                        {/* Loading */}
                        {analyzingPcap && (
                            <Box sx={{display: 'flex', justifyContent: 'center', padding: 3}}>
                                <CircularProgress/>
                                <Typography sx={{marginLeft: 2}}>Analyzing PCAP...</Typography>
                            </Box>
                        )}

                        {/* Results */}
                        {pcapResults && pcapResults.messages.length > 0 && (
                            <Box sx={{marginTop: 3}}>
                                {/* Summary */}
                                <Alert severity="info" sx={{marginBottom: 2}}>
                                    Found {pcapResults.irp_packets} IRP packets
                                    with {pcapResults.messages.length} unique message types
                                </Alert>

                                {/* Select All Checkbox */}
                                <Box sx={{display: 'flex', alignItems: 'center', marginBottom: 1, paddingLeft: 1}}>
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
                                    <Typography variant="subtitle1" sx={{fontWeight: 'bold'}}>
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
                            <Alert severity="warning" sx={{marginTop: 3}}>
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

            {/* Hidden JSON File Input - Must be outside dialogs to always be available */}
            <input
                ref={jsonFileInputRef}
                type="file"
                accept=".json"
                style={{display: 'none'}}
                onChange={handleImportJSON}
            />
        </Layout>
    )
}


