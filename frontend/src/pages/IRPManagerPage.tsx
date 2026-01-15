import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Box,
  Typography,
  Button,
  Paper,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  TextField,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  IconButton,
  Divider,
  Snackbar,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Collapse,
  FormControlLabel,
  Checkbox,
} from '@mui/material'
import DownloadIcon from '@mui/icons-material/Download'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import DeleteIcon from '@mui/icons-material/Delete'
import UploadFileIcon from '@mui/icons-material/UploadFile'

import Layout from '../components/common/Layout'
import useCCStore from '../store/ccStore'
import { irpSchemaService, IRPSchema } from '../api/services/irpSchema.service'

export const IRPManagerPage: React.FC = () => {
  const navigate = useNavigate()
  const currentCC = useCCStore((state) => state.currentCC)
  const devices = useCCStore((state) => state.devices)

  const [selectedVersion, setSelectedVersion] = useState<string | ''>('')
  const [existingSchemas, setExistingSchemas] = useState<IRPSchema[]>([])
  const [isLoading, setIsLoading] = useState<boolean>(false)
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' | 'info' }>({
    open: false,
    message: '',
    severity: 'success'
  })

  // Credentials state with defaults
  const [useCustomCredentials, setUseCustomCredentials] = useState<boolean>(false)
  const [sshUsername, setSshUsername] = useState<string>('root')
  const [sshPassword, setSshPassword] = useState<string>('radware')

  // Upload custom XML state
  const [uploadXmlFile, setUploadXmlFile] = useState<File | null>(null)

  // Backup detection dialog state
  const [backupDialogOpen, setBackupDialogOpen] = useState(false)
  const [backupDialogData, setBackupDialogData] = useState<{
    version: string
    username: string
    password: string
  } | null>(null)

  useEffect(() => {
    if (!currentCC) {
      navigate('/cc/login')
    }
  }, [currentCC, navigate])

  const availableVersions: string[] = Array.from(
    new Set(devices.map((d) => d.version).filter(Boolean) as string[])
  )

  const fetchSchemas = async () => {
    try {
      setIsLoading(true)
      const schemas = await irpSchemaService.listSchemas(currentCC!)
      setExistingSchemas(schemas)
    } catch (error: any) {
      console.error('Failed to fetch schemas:', error)
      setSnackbar({ open: true, message: 'Failed to load schemas', severity: 'error' })
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (currentCC) {
      fetchSchemas()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentCC])

  const handleDownload = async (revertToOriginal: boolean = false) => {
    if (!selectedVersion) {
      setSnackbar({ open: true, message: 'Please select a version', severity: 'error' })
      return
    }
    if (!sshUsername || !sshPassword) {
      setSnackbar({ open: true, message: 'Please enter SSH credentials', severity: 'error' })
      return
    }

    setIsLoading(true)
    try {
      const result = await irpSchemaService.downloadSchema(currentCC!, {
        sim_version: selectedVersion,
        username: sshUsername,
        password: sshPassword,
        revert_to_original: revertToOriginal,
      })

      if (result.success) {
        // Check if backup exists (custom XML detected)
        if (result.backup_exists && !revertToOriginal) {
          // Show dialog asking user what to do
          setBackupDialogData({
            version: selectedVersion,
            username: sshUsername,
            password: sshPassword,
          })
          setBackupDialogOpen(true)
          setIsLoading(false)
          return
        }

        // Success - no backup or reverted successfully
        const message = revertToOriginal
          ? 'Original XML restored and downloaded successfully. Opening sender...'
          : 'Schema downloaded successfully. Opening sender...'

        setSnackbar({ open: true, message, severity: 'success' })

        // Navigate to sender page with the newly downloaded schema
        setTimeout(() => {
          navigate(`/cc/reporting/irp/send?schema_id=${result.mongo_id}`)
        }, 1000)
      } else {
        setSnackbar({ open: true, message: result.message, severity: 'error' })
      }
    } catch (error: any) {
      setSnackbar({ open: true, message: error.response?.data?.detail || 'Download failed', severity: 'error' })
    } finally {
      setIsLoading(false)
    }
  }

  const handleDelete = async (schemaId: string, templateName: string) => {
    if (!window.confirm(`Delete schema "${templateName}"?`)) return

    try {
      await irpSchemaService.deleteSchema(currentCC!, schemaId)
      setSnackbar({ open: true, message: 'Schema deleted successfully', severity: 'success' })
      await fetchSchemas()
    } catch (error: any) {
      setSnackbar({ open: true, message: 'Failed to delete schema', severity: 'error' })
    }
  }

  const handleUploadCustomXml = async () => {
    if (!selectedVersion) {
      setSnackbar({ open: true, message: 'Please select a version', severity: 'error' })
      return
    }
    if (!uploadXmlFile) {
      setSnackbar({ open: true, message: 'Please select an XML file', severity: 'error' })
      return
    }
    if (!sshUsername || !sshPassword) {
      setSnackbar({ open: true, message: 'Please enter SSH credentials', severity: 'error' })
      return
    }

    setIsLoading(true)
    try {
      const formData = new FormData()
      formData.append('file', uploadXmlFile)
      formData.append('sim_version', selectedVersion)  // Changed from simulator_ip to sim_version
      formData.append('username', sshUsername)
      formData.append('password', sshPassword)

      const response = await fetch(`${process.env.REACT_APP_API_BASE_URL}/cc/${currentCC}/irp/IdsDataFormat/upload`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${localStorage.getItem('token')}`,
        },
        body: formData,
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Upload failed')
      }

      const result = await response.json()

      if (result.success) {
        const message = result.backup_created
          ? 'Custom XML uploaded successfully (Original backed up). Opening sender...'
          : 'Custom XML uploaded successfully (Backup already exists). Opening sender...'

        setSnackbar({ open: true, message, severity: 'success' })

        // Navigate to sender page immediately (same as regular download)
        setTimeout(() => {
          navigate(`/cc/reporting/irp/send?schema_id=${result.mongo_id}`)
        }, 1000)
      } else {
        setSnackbar({ open: true, message: result.message, severity: 'error' })
      }
    } catch (error: any) {
      setSnackbar({ open: true, message: error.message || 'Upload failed', severity: 'error' })
    } finally {
      setIsLoading(false)
    }
  }

  const handleBackupDialogChoice = async (choice: 'custom' | 'original') => {
    setBackupDialogOpen(false)

    if (choice === 'original') {
      // Revert to original and download
      await handleDownload(true)
    } else {
      // Continue with custom XML (already downloaded)
      if (backupDialogData) {
        // Re-download custom (it was already downloaded, but we need the result)
        setIsLoading(true)
        try {
          const result = await irpSchemaService.downloadSchema(currentCC!, {
            sim_version: backupDialogData.version,
            username: backupDialogData.username,
            password: backupDialogData.password,
            revert_to_original: false,
          })

          if (result.success) {
            setSnackbar({ open: true, message: 'Using custom XML. Opening sender...', severity: 'info' })
            setTimeout(() => {
              navigate(`/cc/reporting/irp/send?schema_id=${result.mongo_id}`)
            }, 1000)
          }
        } catch (error: any) {
          setSnackbar({ open: true, message: 'Failed to load custom XML', severity: 'error' })
        } finally {
          setIsLoading(false)
        }
      }
    }

    setBackupDialogData(null)
  }

  return (
    <Layout>
      <Box p={4} sx={{ maxWidth: 1400, margin: '0 auto' }}>
        <Typography variant="h4" sx={{ mb: 1 }}>IRP Message Configuration</Typography>
        <Typography variant="body2" color="textSecondary" sx={{ mb: 4 }}>
          Manage IdsDataFormat schemas for IRP message sending
        </Typography>

        {/* Existing Schemas Table */}
        <Paper sx={{ mb: 4, p: 3 }}>
          <Typography variant="h6" sx={{ mb: 2 }}>Existing Schemas in Database</Typography>

          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Template Name</TableCell>
                <TableCell>Version</TableCell>
                <TableCell>Created Date</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {existingSchemas.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4} align="center" sx={{ color: '#666', padding: 4 }}>
                    No schemas found. Download one below.
                  </TableCell>
                </TableRow>
              ) : (
                existingSchemas.map((schema) => (
                  <TableRow key={schema.mongo_id}>
                    <TableCell>{schema.template_name}</TableCell>
                    <TableCell>{schema.version}</TableCell>
                    <TableCell>{schema.created_at ? new Date(schema.created_at).toLocaleString() : '-'}</TableCell>
                    <TableCell align="right">
                      <IconButton
                        color="primary"
                        title="Use this schema"
                        onClick={() => navigate(`/cc/reporting/irp/send?schema_id=${schema.mongo_id}`)}
                      >
                        <CheckCircleIcon />
                      </IconButton>
                      <IconButton
                        color="error"
                        onClick={() => handleDelete(schema.mongo_id, schema.template_name)}
                        title="Delete schema"
                      >
                        <DeleteIcon />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </Paper>

        {/* Two-Column Layout: Download + Upload */}
        <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
          {/* LEFT COLUMN: Download from CC */}
          <Box sx={{ flex: '1 1 calc(50% - 12px)', minWidth: 300 }}>
            <Paper sx={{ p: 3, height: '100%' }}>
              <Typography variant="h6" sx={{ mb: 2 }}>Download from CyberController</Typography>

              <Typography variant="body2" color="textSecondary" sx={{ mb: 3 }}>
                Download official IdsDataFormat schema from CyberController
              </Typography>

              <FormControl fullWidth sx={{ mb: 2 }}>
                <InputLabel id="sim-version-label">Simulator Version</InputLabel>
                <Select
                  labelId="sim-version-label"
                  value={selectedVersion}
                  label="Simulator Version"
                  onChange={(e) => setSelectedVersion(e.target.value as string)}
                >
                  {availableVersions.length === 0 ? (
                    <MenuItem value="">No available versions</MenuItem>
                  ) : (
                    availableVersions.map((v) => (
                      <MenuItem key={v} value={v}>
                        {v}
                      </MenuItem>
                    ))
                  )}
                </Select>
              </FormControl>

              {/* Custom Credentials Toggle */}
              <Box sx={{ mb: 2 }}>
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={useCustomCredentials}
                      onChange={(e) => {
                        setUseCustomCredentials(e.target.checked)
                        if (!e.target.checked) {
                          setSshUsername('root')
                          setSshPassword('radware')
                        }
                      }}
                    />
                  }
                  label="Use custom SSH credentials"
                />
              </Box>

              {/* Credentials Fields (shown when custom enabled) */}
              <Collapse in={useCustomCredentials}>
                <TextField
                  fullWidth
                  label="SSH Username"
                  sx={{ mb: 2 }}
                  value={sshUsername}
                  onChange={(e) => setSshUsername(e.target.value)}
                />

                <TextField
                  fullWidth
                  label="SSH Password"
                  type="password"
                  sx={{ mb: 2 }}
                  value={sshPassword}
                  onChange={(e) => setSshPassword(e.target.value)}
                />
              </Collapse>

              {!useCustomCredentials && (
                <Alert severity="info" sx={{ mb: 2 }}>
                  Using default credentials: root / radware
                </Alert>
              )}

              <Button
                variant="contained"
                startIcon={<DownloadIcon />}
                fullWidth
                onClick={() => handleDownload(false)}
                disabled={isLoading || !selectedVersion}
              >
                {isLoading ? 'Downloading...' : 'Download Schema'}
              </Button>
            </Paper>
          </Box>

          {/* RIGHT COLUMN: Upload Custom XML */}
          <Box sx={{ flex: '1 1 calc(50% - 12px)', minWidth: 300 }}>
            <Paper sx={{ p: 3, height: '100%' }}>
              <Typography variant="h6" sx={{ mb: 2 }}>Upload Custom XML</Typography>

              <Alert severity="warning" sx={{ mb: 3 }}>
                <Typography variant="body2" sx={{ fontWeight: 600, mb: 0.5 }}>
                  ⚠️ DEVELOPMENT USE ONLY
                </Typography>
                <Typography variant="body2">
                  This feature replaces the production IdsDataFormat XML used by CyberController for the selected simulator version.
                  Only use this for development and testing purposes. The original XML will be automatically backed up.
                </Typography>
              </Alert>

              <FormControl fullWidth sx={{ mb: 2 }}>
                <InputLabel id="upload-version-label">Simulator Version</InputLabel>
                <Select
                  labelId="upload-version-label"
                  value={selectedVersion}
                  label="Simulator Version"
                  onChange={(e) => setSelectedVersion(e.target.value as string)}
                >
                  {availableVersions.length === 0 ? (
                    <MenuItem value="">No available versions</MenuItem>
                  ) : (
                    availableVersions.map((v) => (
                      <MenuItem key={v} value={v}>
                        {v}
                      </MenuItem>
                    ))
                  )}
                </Select>
              </FormControl>

              <Box sx={{ mb: 2 }}>
                <input
                  accept=".xml"
                  style={{ display: 'none' }}
                  id="upload-xml-file"
                  type="file"
                  onChange={(e) => {
                    const file = e.target.files?.[0]
                    if (file) {
                      if (!file.name.toLowerCase().endsWith('.xml')) {
                        setSnackbar({ open: true, message: 'Please select an XML file', severity: 'error' })
                        return
                      }
                      setUploadXmlFile(file)
                    }
                  }}
                />
                <label htmlFor="upload-xml-file">
                  <Button
                    variant="outlined"
                    component="span"
                    fullWidth
                    startIcon={<UploadFileIcon />}
                  >
                    {uploadXmlFile ? uploadXmlFile.name : 'Select XML File'}
                  </Button>
                </label>
              </Box>

              {!useCustomCredentials && (
                <Alert severity="info" sx={{ mb: 2 }}>
                  Using default credentials: root / radware
                </Alert>
              )}

              <Button
                variant="contained"
                color="warning"
                startIcon={<UploadFileIcon />}
                fullWidth
                onClick={handleUploadCustomXml}
                disabled={isLoading || !selectedVersion || !uploadXmlFile}
              >
                {isLoading ? 'Uploading...' : 'Upload Custom XML'}
              </Button>
            </Paper>
          </Box>
        </Box>
      </Box>

      {/* Backup Detection Dialog */}
      <Dialog
        open={backupDialogOpen}
        onClose={() => {
          setBackupDialogOpen(false)
          setBackupDialogData(null)
        }}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Custom XML Detected</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            <Typography variant="body2" sx={{ fontWeight: 600, mb: 1 }}>
              A custom IdsDataFormat XML is currently active for this version
            </Typography>
            <Typography variant="body2">
              The original XML has been backed up. Would you like to:
            </Typography>
          </Alert>

          <Box sx={{ mt: 3 }}>
            <Typography variant="body2" sx={{ fontWeight: 600, mb: 1 }}>
              • Use Custom XML: Download and use the currently active custom XML
            </Typography>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>
              • Revert to Original: Restore and use the original production XML
            </Typography>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => {
              setBackupDialogOpen(false)
              setBackupDialogData(null)
            }}
          >
            Cancel
          </Button>
          <Button
            onClick={() => handleBackupDialogChoice('custom')}
            variant="outlined"
            color="warning"
          >
            Use Custom XML
          </Button>
          <Button
            onClick={() => handleBackupDialogChoice('original')}
            variant="contained"
            color="primary"
          >
            Revert to Original
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar open={snackbar.open} autoHideDuration={6000} onClose={() => setSnackbar(s => ({ ...s, open: false }))}>
        <Alert onClose={() => setSnackbar(s => ({ ...s, open: false }))} severity={snackbar.severity}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Layout>
  )
}
