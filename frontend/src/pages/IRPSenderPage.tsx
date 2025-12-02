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

export const IRPSenderPage: React.FC = () => {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const schemaId = searchParams.get('schema_id')

  const { currentCC, devices, managementPorts } = useCCStore()

  const [schemaInfo, setSchemaInfo] = useState<{ name: string; version: string } | null>(null)
  const [selectedSimulator, setSelectedSimulator] = useState<string>('')
  const [selectedDestinationPort, setSelectedDestinationPort] = useState<string>('')
  const [messages, setMessages] = useState<Array<{ messageType: string; messageName: string; data: Record<string, any> }>>([])
  const [expandedMessages, setExpandedMessages] = useState<number[]>([])
  const [availableMessages, setAvailableMessages] = useState<SchemaMessage[]>([])
  const [addMessageDialogOpen, setAddMessageDialogOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' | 'info' }>({ open: false, message: '', severity: 'success' })

  // Redirect if missing context
  useEffect(() => {
    if (!currentCC || !schemaId) {
      navigate('/cc/reporting/irp')
    }
  }, [currentCC, schemaId, navigate])

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
    try {
      setIsLoading(true)
      const template = await irpSchemaService.getMessageTemplate(currentCC!, schemaId!, messageType)
      setMessages((prev) => [...prev, { messageType, messageName, data: template.template }])
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
    if (messages.length === 1) {
      setSnackbar({ open: true, message: 'Must have at least one message', severity: 'error' })
      return
    }
    setMessages((prev) => prev.filter((_, i) => i !== index))
    setExpandedMessages((prev) => prev.filter((i) => i !== index).map((i) => (i > index ? i - 1 : i)))
  }

  const toggleMessage = (index: number) => {
    setExpandedMessages((prev) => (prev.includes(index) ? prev.filter((i) => i !== index) : [...prev, index]))
  }

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const updateMessage = (index: number, data: Record<string, any>) => {
    setMessages((prev) => {
      const next = [...prev]
      next[index] = { ...next[index], data }
      return next
    })
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
                  <Typography variant="body2" color="textSecondary">
                    Message form builder coming next...
                  </Typography>
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
          <Button variant="outlined" startIcon={<SaveIcon />}>
            Save Template
          </Button>
          <Button variant="outlined" startIcon={<DownloadIcon />}>
            Download JSON
          </Button>
          <Button variant="outlined" startIcon={<UploadIcon />}>
            Load Template
          </Button>
          <Box sx={{ flex: 1 }} />
          <Button
            variant="contained"
            color="primary"
            startIcon={<SendIcon />}
            disabled={!selectedSimulator || !selectedDestinationPort || messages.length === 0}
          >
            Send Messages ({messages.length})
          </Button>
        </Box>
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

      <Snackbar open={snackbar.open} autoHideDuration={6000} onClose={() => setSnackbar((s) => ({ ...s, open: false }))}>
        <Alert severity={snackbar.severity}>{snackbar.message}</Alert>
      </Snackbar>
    </Layout>
  )
}

