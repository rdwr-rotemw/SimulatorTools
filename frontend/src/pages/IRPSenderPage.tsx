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
} from '@mui/material'
import SendIcon from '@mui/icons-material/Send'
import AddIcon from '@mui/icons-material/Add'
import SaveIcon from '@mui/icons-material/Save'
import DownloadIcon from '@mui/icons-material/Download'
import UploadIcon from '@mui/icons-material/Upload'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import ExpandLessIcon from '@mui/icons-material/ExpandLess'
import DeleteIcon from '@mui/icons-material/Delete'

import Layout from '../components/common/Layout'
import useCCStore from '../store/ccStore'
import { irpSchemaService, SchemaMessage } from '../api/services/irpSchema.service'
import IRPMessageForm from '../components/irp/IRPMessageForm'

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
  const [messages, setMessages] = useState<Array<{ messageType: string; messageName: string; data: Record<string, any>; schema: Record<string, any> }>>([])
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

  // Log render for debugging
  console.log('IRPSenderPage rendered')

  // Redirect if missing context
  useEffect(() => {
    if (!currentCC || !schemaId) {
      navigate('/cc/reporting/irp')
    }
  }, [currentCC, schemaId, navigate])

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
      setMessages((prev) => [...prev, {
        messageType,
        messageName,
        data: template.template,
        schema: template.schema,
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

      // Update page state with loaded template
      setMessages(template.messages)
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

      // Format messages for backend (remove schema, keep only data)
      const formattedMessages = messages.map((msg) => ({
        message: msg.messageName,
        ...msg.data,
      }))

      const payload = {
        mongo_id: schemaId!,
        message_data: {
          messages: formattedMessages,
        },
      }

      await irpSchemaService.sendMessages(currentCC!, selectedSimulator, payload)
      setSnackbar({ open: true, message: `Successfully sent ${messages.length} message(s)`, severity: 'success' })
    } catch (error: any) {
      console.error('Failed to send messages:', error)
      const errorMsg = error?.response?.data?.detail || error?.message || 'Failed to send messages'
      setSnackbar({ open: true, message: errorMsg, severity: 'error' })
    } finally {
      setIsLoading(false)
    }
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
            disabled={!selectedSimulator || !selectedDestinationPort || messages.length === 0 || isLoading}
            onClick={handleSendMessages}
          >
            {isLoading ? 'Sending...' : `Send Messages (${messages.length})`}
          </Button>
        </Box>

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
