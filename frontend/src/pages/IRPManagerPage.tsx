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
} from '@mui/material'
import DownloadIcon from '@mui/icons-material/Download'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import DeleteIcon from '@mui/icons-material/Delete'

import Layout from '../components/common/Layout'
import useCCStore from '../store/ccStore'
import { irpSchemaService, IRPSchema } from '../api/services/irpSchema.service'

export const IRPManagerPage: React.FC = () => {
  const navigate = useNavigate()
  const { currentCC, devices } = useCCStore()

  const [selectedVersion, setSelectedVersion] = useState<string | ''>('')
  const [sshUsername, setSshUsername] = useState<string>('')
  const [sshPassword, setSshPassword] = useState<string>('')
  const [existingSchemas, setExistingSchemas] = useState<IRPSchema[]>([])
  const [isLoading, setIsLoading] = useState<boolean>(false)
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' | 'info' }>({ open: false, message: '', severity: 'success' })

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

  const handleDownload = async () => {
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
      })

      if (result.success) {
        setSnackbar({ open: true, message: 'Schema downloaded successfully. Opening sender...', severity: 'success' })
        // Navigate to sender page with the newly downloaded schema
        setTimeout(() => {
          navigate(`/cc/reporting/irp/send?schema_id=${result.mongo_id}`)
        }, 1000) // Small delay to show success message
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
    if (!confirm(`Delete schema "${templateName}"?`)) return

    try {
      await irpSchemaService.deleteSchema(currentCC!, schemaId)
      setSnackbar({ open: true, message: 'Schema deleted successfully', severity: 'success' })
      fetchSchemas()
    } catch (error: any) {
      setSnackbar({ open: true, message: 'Failed to delete schema', severity: 'error' })
    }
  }

  return (
    <Layout>
      <Box p={4}>
        <Typography variant="h4">IRP Message Configuration</Typography>
        <Typography variant="body2" sx={{ mt: 1 }}>
          Manage IdsDataFormat schemas for IRP message sending
        </Typography>

        <Paper sx={{ mt: 4, p: 3 }}>
          <Typography variant="h6">Existing Schemas in Database</Typography>

          <Table sx={{ mt: 2 }}>
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
                    <TableCell>
                      <IconButton color="primary" title="Use this schema" onClick={() => navigate(`/cc/reporting/irp/send?schema_id=${schema.mongo_id}`)}>
                        <CheckCircleIcon />
                      </IconButton>
                      <IconButton color="error" onClick={() => handleDelete(schema.mongo_id, schema.template_name)} title="Delete schema">
                        <DeleteIcon />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </Paper>

        <Divider sx={{ my: 4 }} />

        <Paper sx={{ p: 3 }}>
          <Typography variant="h6">Download New IdsDataFormat Schema</Typography>

          <FormControl fullWidth sx={{ mt: 2 }}>
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

          <TextField
            fullWidth
            label="SSH Username"
            sx={{ mt: 2 }}
            value={sshUsername}
            onChange={(e) => setSshUsername(e.target.value)}
          />

          <TextField
            fullWidth
            label="SSH Password"
            type="password"
            sx={{ mt: 2 }}
            value={sshPassword}
            onChange={(e) => setSshPassword(e.target.value)}
          />

          <Button
            variant="contained"
            startIcon={<DownloadIcon />}
            sx={{ mt: 3 }}
            onClick={handleDownload}
            disabled={isLoading || !selectedVersion}
          >
            {isLoading ? 'Downloading...' : 'Download Schema'}
          </Button>
        </Paper>
      </Box>

      <Snackbar open={snackbar.open} autoHideDuration={6000} onClose={() => setSnackbar(s => ({ ...s, open: false }))}>
        <Alert onClose={() => setSnackbar(s => ({ ...s, open: false }))} severity={snackbar.severity}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Layout>
  )
}
