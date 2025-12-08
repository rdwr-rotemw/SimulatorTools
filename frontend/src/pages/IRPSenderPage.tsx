import React, { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  Box,
  Typography,
  Button,
  Paper,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Alert,
  CircularProgress,
  Snackbar,
  IconButton,
  Collapse,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  List,
  ListItemButton,
  ListItemText,
  ListItem,
  TextField,
  Tooltip,
} from '@mui/material'
import SendIcon from '@mui/icons-material/Send'
import AddIcon from '@mui/icons-material/Add'
import SaveIcon from '@mui/icons-material/Save'
import DownloadIcon from '@mui/icons-material/Download'
import UploadIcon from '@mui/icons-material/Upload'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import ExpandLessIcon from '@mui/icons-material/ExpandLess'
import DeleteIcon from '@mui/icons-material/Delete'
import CasinoIcon from '@mui/icons-material/Casino'
import LoopIcon from '@mui/icons-material/Loop'
import StopIcon from '@mui/icons-material/Stop'

import Layout from '../components/common/Layout'
import useCCStore from '../store/ccStore'
import { irpSchemaService, SchemaMessage } from '../api/services/irpSchema.service'
import IRPMessageForm from '../components/irp/IRPMessageForm'

// Utility function to generate random data based on schema
// Schema-driven recursion: Uses schema to understand and randomize all nested types
function generateRandomData(schema: Record<string, any>, currentData?: Record<string, any>): Record<string, any> {
  const randomizeValue = (fieldSchema: any, currentValue?: any, fieldKey?: string): any => {
    if (!fieldSchema) return currentValue ?? ''

    const fieldType = fieldSchema?.fieldType || fieldSchema?.type || 'string'

    // Special case: policy-name field should be pol1 to pol30
    if (fieldKey === 'policy-name' && fieldType === 'string') {
      const policyNumber = Math.floor(Math.random() * 30) + 1 // 1-30
      return `pol${policyNumber}`
    }

    // Special case: attack-id field should NOT be randomized by general randomize
    // Keep current value unchanged
    if (fieldKey === 'attack-id' && fieldType === 'string') {
      return currentValue ?? `0-${Math.floor(Date.now() / 1000)}`
    }

    // Primitive types - return early
    if (fieldType === 'integer') {
      const min = fieldSchema?.min ?? 0
      const max = fieldSchema?.max ?? 1000
      return Math.floor(Math.random() * (max - min + 1)) + min
    }
    if (fieldType === 'float') return Math.random() * 1000
    if (fieldType === 'boolean') return Math.random() > 0.5
    if (fieldType === 'enum' && Array.isArray(fieldSchema?.options)) {
      return fieldSchema.options[Math.floor(Math.random() * fieldSchema.options.length)]
    }
    if (fieldType === 'ipv4') {
      return `${Math.floor(Math.random() * 256)}.${Math.floor(Math.random() * 256)}.${Math.floor(Math.random() * 256)}.${Math.floor(Math.random() * 256)}`
    }
    if (fieldType === 'ipv6') {
      return Array.from({ length: 8 }, () => Math.floor(Math.random() * 0xffff).toString(16)).join(':')
    }
    if (fieldType === 'string') {
      return Math.random().toString(36).substring(2, 12)
    }

    // Array - preserve iterations, recursively randomize each item using itemSchema
    if (fieldType === 'array' || fieldType === 'fixed-array') {
      const itemSchema = fieldSchema?.itemSchema
      const existingArray = Array.isArray(currentValue) ? currentValue : []
      if (existingArray.length > 0) {
        return existingArray.map((item: any) => {
          if (itemSchema?.fieldType === 'switch' && itemSchema?.options && typeof item === 'object' && item !== null) {
            const selectedOption = Object.keys(item)[0]
            if (selectedOption && itemSchema.options[selectedOption]) {
              const optionSchema = itemSchema.options[selectedOption]?.schema || itemSchema.options[selectedOption]
              const currentOptionValue = item[selectedOption]
              return { [selectedOption]: randomizeValue(optionSchema, currentOptionValue, selectedOption) }
            }
            return item
          }
          if (itemSchema?.fieldType && itemSchema.fieldType !== 'object' && itemSchema.fieldType !== 'clone' && itemSchema.fieldType !== 'switch') {
            return randomizeValue(itemSchema, item, fieldKey)
          }
          const result: Record<string, any> = {}
          Object.keys(itemSchema || {}).forEach((key) => {
            if (['type', 'fieldType', 'default', 'required'].includes(key)) return
            const fieldDef = itemSchema[key]
            const currentFieldValue = (typeof item === 'object' && item !== null) ? item[key] : undefined
            result[key] = randomizeValue(fieldDef, currentFieldValue, key)
          })
          return result
        })
      }
      const arraySize = Math.floor(Math.random() * 2) + 1
      return Array.from({ length: arraySize }, () => {
        if (itemSchema?.fieldType && itemSchema.fieldType !== 'object' && itemSchema.fieldType !== 'clone' && itemSchema.fieldType !== 'switch') {
          return randomizeValue(itemSchema, undefined, fieldKey)
        }
        const result: Record<string, any> = {}
        Object.keys(itemSchema || {}).forEach((key) => {
          if (['type', 'fieldType', 'default', 'required'].includes(key)) return
          result[key] = randomizeValue(itemSchema[key], undefined, key)
        })
        return result
      })
    }

    if (fieldSchema?.fields && typeof fieldSchema.fields === 'object') {
      const result: Record<string, any> = {}
      Object.keys(fieldSchema.fields).forEach((key) => {
        const nestedValue = (typeof currentValue === 'object' && currentValue !== null) ? currentValue[key] : undefined
        result[key] = randomizeValue(fieldSchema.fields[key], nestedValue, key)
      })
      return result
    }

    if ((fieldType === 'clone' || fieldSchema?.type === 'clone') && fieldSchema?.fields) {
      const result: Record<string, any> = {}
      Object.keys(fieldSchema.fields).forEach((optionKey) => {
        const optionValue = (typeof currentValue === 'object' && currentValue !== null) ? currentValue[optionKey] : undefined
        result[optionKey] = randomizeValue(fieldSchema.fields[optionKey], optionValue, optionKey)
      })
      return result
    }

    if (typeof currentValue === 'object' && currentValue !== null && !Array.isArray(currentValue)) {
      const result: Record<string, any> = {}
      Object.keys(currentValue).forEach((key) => {
        const propValue = currentValue[key]
        result[key] = randomizeValue({}, propValue, key)
      })
      return result
    }

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
    return data.map((item, idx) => {
      const itemSchema = schema?.itemSchema || schema
      return transformToAttackId(item, itemSchema)
    })
  }

  const result: any = {}
  const hasTimeAndCnt = 'time' in data && 'cnt' in data &&
                        schema?.time && schema?.cnt

  if (hasTimeAndCnt) {
    // Merge time and cnt into attack-id
    result['attack-id'] = `${data.cnt}-${data.time}`

    // Copy all other fields except time and cnt
    Object.keys(data).forEach(key => {
      if (key !== 'time' && key !== 'cnt') {
        const fieldSchema = schema?.[key] || schema?.fields?.[key]
        result[key] = transformToAttackId(data[key], fieldSchema)
      }
    })
  } else {
    // No time/cnt pair, process normally
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
    return data.map((item, idx) => {
      const itemSchema = originalSchema?.itemSchema || originalSchema
      return transformFromAttackId(item, itemSchema)
    })
  }

  const result: any = {}
  const hasAttackId = 'attack-id' in data
  const schemaHasTimeAndCnt = originalSchema?.time && originalSchema?.cnt

  if (hasAttackId && schemaHasTimeAndCnt) {
    // Split attack-id back into time and cnt
    const attackId = data['attack-id'] || ''
    const parts = attackId.toString().split('-')

    if (parts.length === 2) {
      result.cnt = parseInt(parts[0]) || 0
      result.time = parseInt(parts[1]) || 0
    } else {
      result.cnt = 0
      result.time = 0
    }

    // Copy all other fields except attack-id
    Object.keys(data).forEach(key => {
      if (key !== 'attack-id') {
        const fieldSchema = originalSchema?.[key] || originalSchema?.fields?.[key]
        result[key] = transformFromAttackId(data[key], fieldSchema)
      }
    })
  } else {
    // No attack-id, process normally
    Object.keys(data).forEach(key => {
      const fieldSchema = originalSchema?.[key] || originalSchema?.fields?.[key]
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

    // Add attack-id field
    result['attack-id'] = {
      type: 'string',
      fieldType: 'string',
      default: `${schema.cnt.default || 0}-${schema.time.default || 0}`,
      required: true
    }

    // Copy all other fields except time and cnt
    Object.keys(schema).forEach(key => {
      if (key !== 'time' && key !== 'cnt') {
        result[key] = transformSchemaForAttackId(schema[key])
      }
    })

    return result
  }

  // Handle nested structures
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

  // If this looks like a field definition (has fieldType), return as-is
  // Don't recurse into field metadata like options, min, max, etc.
  if (schema.fieldType) {
    return schema
  }

  // Handle object with nested field definitions
  // Only recurse if this looks like a container of field definitions
  const result: any = {}
  let hasFieldDefinitions = false

  Object.keys(schema).forEach(key => {
    const value = schema[key]
    // Check if this value looks like a field definition (has type or fieldType)
    if (value && typeof value === 'object' && (value.type || value.fieldType || value.fields || value.itemSchema)) {
      hasFieldDefinitions = true
      result[key] = transformSchemaForAttackId(value)
    } else {
      result[key] = value
    }
  })

  // If we found field definitions, return the transformed result
  // Otherwise, return the original schema unchanged
  return result
}

// Generate random attack-id in cnt-time format
export function generateAttackId(): string {
  const cnt = Math.floor(Math.random() * 10000) // Random cnt 0-9999
  const time = Math.floor(Date.now() / 1000) // Current epoch time in seconds
  return `${cnt}-${time}`
}

export const IRPSenderPage: React.FC = () => {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const schemaId = searchParams.get('schema_id')

  const currentCC = useCCStore((state) => state.currentCC)
  const devices = useCCStore((state) => state.devices)
  const managementPorts = useCCStore((state) => state.managementPorts)

  const [schemaInfo, setSchemaInfo] = useState<{ name: string; version: string } | null>(null)
  const [selectedSimulator, setSelectedSimulator] = useState<string>('')
  const [selectedDestinationPort, setSelectedDestinationPort] = useState<string>('')
  const [messages, setMessages] = useState<Array<{
    messageType: string;
    messageName: string;
    data: Record<string, any>;
    schema: Record<string, any>;
    originalSchema: Record<string, any>; // Store original schema for transformation back
  }>>([])
  const [expandedMessages, setExpandedMessages] = useState<number[]>([])
  const [availableMessages, setAvailableMessages] = useState<SchemaMessage[]>([])
  const [addMessageDialogOpen, setAddMessageDialogOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' | 'info' }>({ open: false, message: '', severity: 'success' })

  // Template management state
  const [saveDialogOpen, setSaveDialogOpen] = useState(false)
  const [loadDialogOpen, setLoadDialogOpen] = useState(false)
  const [templateName, setTemplateName] = useState('')
  const [savedTemplates, setSavedTemplates] = useState<any[]>([])
  const [loadingTemplates, setLoadingTemplates] = useState(false)

  // Loop functionality state
  const [loopDialogOpen, setLoopDialogOpen] = useState(false)
  const [loopDelay, setLoopDelay] = useState<number>(15) // seconds - default 15s
  const [loopTimeout, setLoopTimeout] = useState<number>(600) // seconds - default 10 minutes, mandatory
  const [isLooping, setIsLooping] = useState(false)
  const loopIntervalRef = React.useRef<NodeJS.Timeout | null>(null)
  const loopTimeoutRef = React.useRef<NodeJS.Timeout | null>(null)

  // Log render for debugging
  console.log('IRPSenderPage rendered')

  // Redirect if missing context
  useEffect(() => {
    if (!currentCC || !schemaId) {
      navigate('/cc/reporting/irp')
    }
  }, [currentCC, schemaId, navigate])

  // Cleanup loop on unmount
  useEffect(() => {
    return () => {
      if (loopIntervalRef.current) clearInterval(loopIntervalRef.current)
      if (loopTimeoutRef.current) clearTimeout(loopTimeoutRef.current)
    }
  }, [])

  const compatibleSimulators = devices.filter((d) => d.version === schemaInfo?.version)

  // Fetch schema info and available messages
  useEffect(() => {
    console.log('Schema fetch effect running')
    if (currentCC && schemaId) {
      const fetchData = async () => {
        try {
          setIsLoading(true)
          const schemas = await irpSchemaService.listSchemas(currentCC)
          const schema = schemas.find((s) => s.mongo_id === schemaId)
          if (schema) {
            setSchemaInfo({ name: schema.template_name, version: schema.version })
          }
          const msgs = await irpSchemaService.listMessages(currentCC, schemaId)
          setAvailableMessages(msgs)
        } catch (error) {
          setSnackbar({ open: true, message: 'Failed to load schema data', severity: 'error' })
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
      // Prefer G2, then G1, then first available
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
    console.log('=== addMessage called ===', messageType, messageName, Date.now())
    try {
      setIsLoading(true)
      console.log('About to call getMessageTemplate')
      const template = await irpSchemaService.getMessageTemplate(currentCC!, schemaId!, messageType)
      console.log('getMessageTemplate returned:', template)

      // Transform time+cnt to attack-id for UI
      const transformedData = transformToAttackId(template.template, template.schema)
      const transformedSchema = transformSchemaForAttackId(template.schema)

      setMessages((prev) => [...prev, {
        messageType,
        messageName,
        data: transformedData,
        schema: transformedSchema,
        originalSchema: template.schema, // Store original schema for transformation back
      }])
      setExpandedMessages((prev) => [...prev, messages.length])
      setAddMessageDialogOpen(false)
      setSnackbar({ open: true, message: `Added ${messageName}`, severity: 'success' })
    } catch (error: any) {
      setSnackbar({ open: true, message: 'Failed to load message template', severity: 'error' })
    } finally {
      setIsLoading(false)
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
      next[index] = { ...next[index], data }
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
      console.error('Failed to save template:', error)
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
      console.error('Failed to load templates:', error)
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

      // Fetch schemas for each message and transform
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
            // If we can't get the schema, keep the message as-is with empty schemas
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
      alert('Template loaded successfully')
    } catch (error) {
      console.error('Failed to load template:', error)
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
      // Refresh list
      const result = await irpSchemaService.listTemplates(currentCC!)
      setSavedTemplates(result.templates)
    } catch (error) {
      console.error('Failed to delete template:', error)
      alert('Failed to delete template')
    }
  }

  // Download JSON
  const handleDownloadJSON = () => {
    // Export only the data needed for sending - no schema metadata
    const messagesForExport = messages.map((msg) => ({
      message: msg.messageName,
      ...msg.data,
    }))

    const dataToDownload = {
      messages: messagesForExport,
    }

    const blob = new Blob([JSON.stringify(dataToDownload, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `irp-messages-${new Date().toISOString().slice(0, 10)}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  // Send Messages
  const handleSendMessages = async () => {
    if (!selectedSimulator || !selectedDestinationPort || messages.length === 0) {
      setSnackbar({ open: true, message: 'Please select simulator, port, and add messages', severity: 'error' })
      return
    }

    try {
      setIsLoading(true)

      // Format messages for backend - transform attack-id back to time+cnt
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
      setSnackbar({ open: true, message: `Successfully sent ${messages.length} message(s)`, severity: 'success' })
    } catch (error: any) {
      console.error('Failed to send messages:', error)
      const errorMsg = error?.response?.data?.detail || error?.message || 'Failed to send messages'
      setSnackbar({ open: true, message: errorMsg, severity: 'error' })
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
      // Transform attack-id back to time+cnt before sending
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
      setSnackbar({ open: true, message: errorMsg, severity: 'error' })
      return false
    }
  }

  const handleStartLoop = () => {
    if (!selectedSimulator) {
      setSnackbar({ open: true, message: 'Please select a simulator', severity: 'error' })
      return
    }

    if (!selectedDestinationPort) {
      setSnackbar({ open: true, message: 'Please select a destination port', severity: 'error' })
      return
    }

    if (messages.length === 0) {
      setSnackbar({ open: true, message: 'Please add at least one message', severity: 'error' })
      return
    }

    if (loopDelay < 1) {
      setSnackbar({ open: true, message: 'Loop delay must be at least 1 second', severity: 'error' })
      return
    }

    if (loopTimeout < 1) {
      setSnackbar({ open: true, message: 'Timeout must be at least 1 second', severity: 'error' })
      return
    }

    setLoopDialogOpen(false)
    setIsLooping(true)

    let messagesSentCount = 0
    const startTime = Date.now()

    // Send first batch immediately
    sendMessagesOnce().then(success => {
      if (success) {
        messagesSentCount++
        setSnackbar({ open: true, message: `Loop started - Sent batch #${messagesSentCount}`, severity: 'info' })
      }
    })

    // Set up interval for subsequent sends (convert seconds to milliseconds)
    loopIntervalRef.current = setInterval(async () => {
      const success = await sendMessagesOnce()
      if (success) {
        messagesSentCount++
        setSnackbar({ open: true, message: `Loop running - Sent batch #${messagesSentCount}`, severity: 'info' })
      }
    }, loopDelay * 1000)

    // Set up timeout - always runs since timeout is mandatory
    loopTimeoutRef.current = setTimeout(() => {
      handleStopLoop()
      const elapsedSeconds = Math.floor((Date.now() - startTime) / 1000)
      setSnackbar({
        open: true,
        message: `Loop stopped after ${elapsedSeconds}s - Sent ${messagesSentCount} batch(es)`,
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
    setIsLooping(false)
  }

  const handleOpenLoopDialog = () => {
    setLoopDialogOpen(true)
  }

  return (
    <Layout>
      <Box sx={{ height: 'calc(100vh - 64px)', display: 'flex', flexDirection: 'column' }}>
        {/* Fixed Header */}
        <Box sx={{ padding: 3, borderBottom: '1px solid #E0E0E0' }}>
          <Typography variant="h4" sx={{ marginBottom: 1 }}>
            IRP Message Sender
          </Typography>
          {schemaInfo && (
            <Alert severity="info" sx={{ marginBottom: 2 }}>
              Using schema: {schemaInfo.name} (Version: {schemaInfo.version})
            </Alert>
          )}

          <FormControl fullWidth>
            <InputLabel>Target Simulator</InputLabel>
            <Select value={selectedSimulator} onChange={(e) => setSelectedSimulator(e.target.value as string)} label="Target Simulator">
              {compatibleSimulators.map((device) => (
                <MenuItem key={device.management_ip} value={device.management_ip}>
                  {device.name || device.management_ip} ({device.management_ip})
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControl fullWidth sx={{ marginTop: 2 }}>
            <InputLabel>Destination Port</InputLabel>
            <Select value={selectedDestinationPort} onChange={(e) => setSelectedDestinationPort(e.target.value as string)} label="Destination Port">
              {managementPorts.map((port) => (
                <MenuItem key={port.interface} value={port.address}>
                  {port.interface}: {port.address}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Box>

        {/* Scrollable Message List */}
        <Box sx={{ flex: 1, overflow: 'auto', padding: 3 }}>
          {isLoading ? (
            <Box display="flex" alignItems="center" gap={2}>
              <CircularProgress size={20} />
              <Typography>Loading...</Typography>
            </Box>
          ) : messages.length === 0 ? (
            <Typography color="textSecondary">No messages. Use "Add Message" to add one from the schema.</Typography>
          ) : (
            messages.map((msg, index) => (
              <Paper key={index} sx={{ marginBottom: 2, padding: 2 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 2 }}>
                  <Typography variant="h6">{msg.messageName}</Typography>
                  <Box>
                    <IconButton onClick={() => toggleMessage(index)}>
                      {expandedMessages.includes(index) ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                    </IconButton>
                    <Tooltip title="Generate random values">
                      <IconButton
                        onClick={() => {
                          const randomData = generateRandomData(msg.schema, msg.data)
                          updateMessage(index, randomData)
                        }}
                        size="small"
                      >
                        <CasinoIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <IconButton onClick={() => deleteMessage(index)} color="error">
                      <DeleteIcon />
                    </IconButton>
                  </Box>
                </Box>
                <Collapse in={expandedMessages.includes(index)}>
                  <IRPMessageForm
                    messageData={msg.data}
                    schema={msg.schema}
                    onChange={(data) => updateMessage(index, data)}
                  />
                </Collapse>
              </Paper>
            ))
          )}
        </Box>

        {/* Fixed Footer */}
        <Box sx={{ padding: 3, borderTop: '1px solid #E0E0E0', display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          <Button variant="outlined" startIcon={<AddIcon />} onClick={() => setAddMessageDialogOpen(true)}>
            Add Message
          </Button>
          <Button
            variant="contained"
            color="secondary"
            onClick={() => setSaveDialogOpen(true)}
            disabled={messages.length === 0}
          >
            Save Template
          </Button>
          <Button
            variant="contained"
            color="secondary"
            onClick={handleDownloadJSON}
            disabled={messages.length === 0}
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
          <Box sx={{ flex: 1 }} />
          <Button
            variant="contained"
            color="primary"
            startIcon={<SendIcon />}
            disabled={!selectedSimulator || !selectedDestinationPort || messages.length === 0 || isLoading || isLooping}
            onClick={handleSendMessages}
          >
            {isLoading ? 'Sending...' : `Send Messages (${messages.length})`}
          </Button>

          {!isLooping ? (
            <Button
              variant="contained"
              color="secondary"
              startIcon={<LoopIcon />}
              onClick={handleOpenLoopDialog}
              disabled={!selectedSimulator || !selectedDestinationPort || messages.length === 0 || isLoading}
            >
              Send Loop
            </Button>
          ) : (
            <Button
              variant="contained"
              color="error"
              startIcon={<StopIcon />}
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
              inputProps={{ min: 1, step: 1 }}
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
              inputProps={{ min: 1, step: 1 }}
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
              <Box sx={{ display: 'flex', justifyContent: 'center', padding: 3 }}>
                <CircularProgress />
              </Box>
            ) : savedTemplates.length === 0 ? (
              <Typography color="textSecondary">No saved templates</Typography>
            ) : (
              <List>
                {savedTemplates.map((template) => (
                  <ListItem key={template.id} secondaryAction={
                    <IconButton edge="end" onClick={() => handleDeleteTemplate(template.id)}>
                      <DeleteIcon />
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
                <ListItemText primary={msg.name} secondary={`ID: ${msg.id}`} />
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
        onClose={() => setSnackbar((s) => ({ ...s, open: false }))}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
      >
        <Alert severity={snackbar.severity}>{snackbar.message}</Alert>
      </Snackbar>
    </Layout>
  )
}
