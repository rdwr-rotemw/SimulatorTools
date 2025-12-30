import React, { useEffect, useState } from 'react';
import { Box, Typography, Button, Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions, Snackbar, Alert, TextField } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import SearchIcon from '@mui/icons-material/Search';
import Layout from '../components/common/Layout';
import { SimulatorTable } from '../components/simulator/SimulatorTable';
import SimulatorFormDialog from '../components/simulator/SimulatorFormDialog';
import useSimulatorStore from '../store/simulatorStore';
import { Simulator, SimulatorCreate, SimulatorUpdate } from '../types/simulator.types';
import apiClient from '../api/client';

interface SnackbarState {
  open: boolean;
  message: string;
  severity: 'success' | 'error';
}

export const SimulatorsPage: React.FC = () => {
  const [formOpen, setFormOpen] = useState(false);
  const [selectedSimulator, setSelectedSimulator] = useState<Simulator | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [simulatorToDelete, setSimulatorToDelete] = useState<string | null>(null);
  const [snackbar, setSnackbar] = useState<SnackbarState>({ open: false, message: '', severity: 'success' });
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState<'ip_address' | 'type' | 'version' | 'map' | 'status'>('ip_address');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const [startLoading, setStartLoading] = useState<string | null>(null);
  const [stopLoading, setStopLoading] = useState<string | null>(null);

  // Map management state
  const [mapDialogOpen, setMapDialogOpen] = useState(false);
  const [maps, setMaps] = useState<Array<{ name: string; status: string }>>([]);
  const [mapsLoading, setMapsLoading] = useState(false);
  const [mapStartLoading, setMapStartLoading] = useState<string | null>(null);
  const [mapStopLoading, setMapStopLoading] = useState<string | null>(null);

  const {
    simulators,
    isLoading,
    fetchSimulators,
    createSimulator,
    updateSimulator,
    deleteSimulator,
  } = useSimulatorStore();

  const [templates, setTemplates] = useState<Array<{ _id: string; name: string }>>([]);
  const templateMap = React.useMemo(() => {
    const m: Record<string, string> = {};
    templates.forEach((t) => (m[t._id] = t.name));
    return m;
  }, [templates]);

  useEffect(() => {
    fetchSimulators();

    // load templates for display
    let cancelled = false;
    const loadTemplates = async () => {
      try {
        const resp = await apiClient.get('/device-templates');
        if (!cancelled) setTemplates((resp.data || []).map((t: any) => ({ _id: t._id, name: t.name })));
      } catch (err) {
        console.error('Failed to load templates', err);
      }
    };
    loadTemplates();

    return () => { cancelled = true; };
  }, []);

  // Fetch maps for Map Management dialog
  const fetchMaps = async () => {
    setMapsLoading(true);
    try {
      const resp = await apiClient.get('/maps');
      setMaps(resp.data || []);
    } catch (err: any) {
      console.error('Failed to load maps:', err);
      setSnackbar({ open: true, message: 'Failed to load maps', severity: 'error' });
    } finally {
      setMapsLoading(false);
    }
  };

  const handleCreate = () => {
    setSelectedSimulator(null);
    setFormOpen(true);
  };

  const handleEdit = (sim: Simulator) => {
    setSelectedSimulator(sim);
    setFormOpen(true);
  };

  const handleDeleteClick = (ip: string) => {
    setSimulatorToDelete(ip);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!simulatorToDelete) return;
    try {
      await deleteSimulator(simulatorToDelete);
      setSnackbar({ open: true, message: 'Simulator deleted', severity: 'success' });

      // Refresh simulator list after deletion
      await fetchSimulators();
    } catch (err: any) {
      setSnackbar({ open: true, message: err?.message || 'Failed to delete simulator', severity: 'error' });
    } finally {
      setDeleteDialogOpen(false);
      setSimulatorToDelete(null);
    }
  };

  const handleStart = async (ip: string) => {
    setStartLoading(ip);
    try {
      await apiClient.post(`/simulators/${ip}/start`);
      setSnackbar({ open: true, message: `Simulator ${ip} started successfully`, severity: 'success' });
      // Refresh simulator list to update status
      await fetchSimulators();
    } catch (err: any) {
      console.error('Failed to start simulator:', err);
      setSnackbar({
        open: true,
        message: err?.response?.data?.detail || 'Failed to start simulator',
        severity: 'error'
      });
    } finally {
      setStartLoading(null);
    }
  };

  const handleStop = async (ip: string) => {
    setStopLoading(ip);
    try {
      await apiClient.post(`/simulators/${ip}/stop`);
      setSnackbar({ open: true, message: `Simulator ${ip} stopped successfully`, severity: 'success' });
      // Refresh simulator list to update status
      await fetchSimulators();
    } catch (err: any) {
      console.error('Failed to stop simulator:', err);
      setSnackbar({
        open: true,
        message: err?.response?.data?.detail || 'Failed to stop simulator',
        severity: 'error'
      });
    } finally {
      setStopLoading(null);
    }
  };

  const handleMapStart = async (mapName: string) => {
    setMapStartLoading(mapName);
    try {
      // Extended timeout for map start (5 minutes + buffer)
      await apiClient.post(`/maps/${mapName}/start`, {}, { timeout: 330000 }); // 5.5 minutes
      setSnackbar({ open: true, message: `Map ${mapName} started successfully`, severity: 'success' });
      await fetchMaps();
    } catch (err: any) {
      console.error('Failed to start map:', err);
      setSnackbar({
        open: true,
        message: err?.response?.data?.detail || 'Failed to start map',
        severity: 'error'
      });
    } finally {
      setMapStartLoading(null);
    }
  };

  const handleMapStop = async (mapName: string) => {
    setMapStopLoading(mapName);
    try {
      // Extended timeout for map stop (5 minutes + buffer)
      await apiClient.post(`/maps/${mapName}/stop`, {}, { timeout: 330000 }); // 5.5 minutes
      setSnackbar({ open: true, message: `Map ${mapName} stopped successfully`, severity: 'success' });
      await fetchMaps();
    } catch (err: any) {
      console.error('Failed to stop map:', err);
      setSnackbar({
        open: true,
        message: err?.response?.data?.detail || 'Failed to stop map',
        severity: 'error'
      });
    } finally {
      setMapStopLoading(null);
    }
  };

  const handleFormSubmit = async (data: SimulatorCreate | SimulatorUpdate) => {
    try {
      if (selectedSimulator) {
        await updateSimulator(selectedSimulator.ip_address, data as SimulatorUpdate);
        setSnackbar({ open: true, message: 'Simulator updated successfully', severity: 'success' });
      } else {
        await createSimulator(data as SimulatorCreate);
        setSnackbar({ open: true, message: 'Simulator created successfully', severity: 'success' });
      }

      // Refresh simulator list from backend to reflect Sapro state
      await fetchSimulators();

      // Close form on success
      setFormOpen(false);
      setSelectedSimulator(null);
    } catch (err: any) {
      // Extract error message from backend response
      const errorMessage = err?.response?.data?.detail || err?.message || 'Operation failed';

      console.error('Simulator operation failed:', err);
      setSnackbar({
        open: true,
        message: errorMessage,
        severity: 'error'
      });

      // DO NOT close form on error - let user retry or cancel
      // setFormOpen(false);  // ← Remove this
      // setSelectedSimulator(null);  // ← Remove this
    }
  };

  const handleFormClose = () => {
    setFormOpen(false);
    setSelectedSimulator(null);
  };

  const handleDeleteCancel = () => {
    setDeleteDialogOpen(false);
    setSimulatorToDelete(null);
  };

  const handleSnackbarClose = (_?: any, reason?: string) => {
    if (reason === 'clickaway') return;
    setSnackbar((s) => ({ ...s, open: false }));
  };

  const handleSort = (column: 'ip_address' | 'type' | 'version' | 'map' | 'status') => {
    if (sortBy === column) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(column);
      setSortOrder('asc');
    }
  };

  const filteredSimulators = simulators.filter(sim => {
    const search = searchTerm.toLowerCase();
    const ipMatch = sim.ip_address?.toLowerCase().includes(search) || false;
    const mapMatch = sim.map?.toLowerCase().includes(search) || false;
    const typeMatch = sim.type?.toLowerCase().includes(search) || false;
    const versionMatch = sim.version?.toLowerCase().includes(search) || false;
    const statusMatch = sim.status?.toLowerCase().includes(search) || false;
    return ipMatch || mapMatch || typeMatch || versionMatch || statusMatch;
  });

  const sortedSimulators = [...filteredSimulators].sort((a, b) => {
    let aValue: any = a[sortBy as keyof Simulator] as any;
    let bValue: any = b[sortBy as keyof Simulator] as any;

    // No special-case sorting required for current fields

    // Handle null/undefined values
    if (aValue == null) aValue = '';
    if (bValue == null) bValue = '';

    if (typeof aValue === 'string') aValue = aValue.toLowerCase();
    if (typeof bValue === 'string') bValue = bValue.toLowerCase();

    if (aValue < bValue) return sortOrder === 'asc' ? -1 : 1;
    if (aValue > bValue) return sortOrder === 'asc' ? 1 : -1;
    return 0;
  });

  const handleMapDialogOpen = () => {
    setMapDialogOpen(true);
    fetchMaps();
  };

  // New: close handler for Map Management dialog which also refreshes simulators
  const handleMapDialogClose = () => {
    setMapDialogOpen(false);
    // Refresh simulator list when closing map management
    fetchSimulators();
  };

  return (
    <Layout>
      <Box sx={{ padding: 4 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 3 }}>
          <Typography variant="h4">Simulator Management</Typography>
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Button variant="outlined" onClick={handleMapDialogOpen}>Map Management</Button>
            <Button variant="contained" startIcon={<AddIcon />} onClick={handleCreate}>Create Simulator</Button>
          </Box>
        </Box>

        <TextField
          placeholder="Search by IP, template name, or map..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          fullWidth
          sx={{ marginBottom: 3 }}
          InputProps={{
            startAdornment: <SearchIcon sx={{ color: '#999', marginRight: 1 }} />
          }}
        />

        <SimulatorTable
          simulators={sortedSimulators}
          onEdit={handleEdit}
          onDelete={handleDeleteClick}
          onStart={handleStart}
          onStop={handleStop}
          isLoading={isLoading}
          startLoading={startLoading}
          stopLoading={stopLoading}
          sortBy={sortBy}
          sortOrder={sortOrder}
          onSort={handleSort}
        />

        <SimulatorFormDialog
          open={formOpen}
          simulator={selectedSimulator}
          simulators={simulators}
          onClose={handleFormClose}
          onSubmit={handleFormSubmit}
        />

        <Dialog open={deleteDialogOpen} onClose={handleDeleteCancel}>
          <DialogTitle>Confirm Delete</DialogTitle>
          <DialogContent>
            <DialogContentText>Are you sure you want to delete this simulator?</DialogContentText>

            {simulatorToDelete !== null && simulators.find(s => s.ip_address === simulatorToDelete) && (
              <Box sx={{ marginTop: 2, padding: 2, background: '#FFF3E0', borderRadius: 1, border: '1px solid #FFB74D' }}>
                <Typography variant="body2" sx={{ fontWeight: 600, marginBottom: 1 }}>Simulator Details:</Typography>
                <Typography variant="body2">IP Address: <strong>{simulators.find(s => s.ip_address === simulatorToDelete)?.ip_address}</strong></Typography>
                <Typography variant="body2">Map: <strong>{simulators.find(s => s.ip_address === simulatorToDelete)?.map || 'Unknown'}</strong></Typography>
                <Typography variant="body2">Template: <strong>{templates.find(t => t._id === simulators.find(s => s.ip_address === simulatorToDelete)?.template_id)?.name || 'Unknown'}</strong></Typography>
              </Box>
            )}

            <Typography variant="body2" sx={{ marginTop: 2, color: '#d32f2f' }}>
              This action cannot be undone.
            </Typography>
          </DialogContent>
          <DialogActions>
            <Button onClick={handleDeleteCancel}>Cancel</Button>
            <Button onClick={handleDeleteConfirm} color="error" variant="contained">Delete</Button>
          </DialogActions>
        </Dialog>

        {/* Map Management Dialog */}
        <Dialog open={mapDialogOpen} onClose={handleMapDialogClose} maxWidth="md" fullWidth>
          <DialogTitle>Map Management</DialogTitle>
          <DialogContent>
            <Alert severity="info" sx={{ marginTop: 2, marginBottom: 2 }}>
              <Typography variant="body2" sx={{ fontWeight: 600, marginBottom: 0.5 }}>
                Map Operations Information
              </Typography>
              <Typography variant="body2">
                Starting and stopping maps may take several minutes to complete.
                Please be patient while the operation is in progress.
                Default timeout is 5 minutes.
              </Typography>
            </Alert>
            <Box sx={{ minHeight: 400 }}>
              {mapsLoading ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 400 }}>
                  <Typography>Loading maps...</Typography>
                </Box>
              ) : (
                <Box sx={{ marginTop: 2 }}>
                  {maps.length === 0 ? (
                    <Typography>No maps found</Typography>
                  ) : (
                    <Box>
                      {maps.map((map) => (
                        <Box
                          key={map.name}
                          sx={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            padding: 2,
                            marginBottom: 1,
                            border: '1px solid #e0e0e0',
                            borderRadius: 1,
                            backgroundColor: map.status === 'running' ? '#e8f5e9' : map.status === 'error' ? '#ffebee' : '#f5f5f5'
                          }}
                        >
                          <Box>
                            <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>{map.name}</Typography>
                            <Typography variant="body2" color="textSecondary">
                              Status: {map.status === 'running' ? 'Running' : map.status === 'error' ? 'Error' : 'Stopped'}
                            </Typography>
                          </Box>
                          <Box sx={{ display: 'flex', gap: 1 }}>
                            {map.status === 'running' ? (
                              <Button
                                variant="outlined"
                                color="error"
                                onClick={() => handleMapStop(map.name)}
                                disabled={mapStopLoading === map.name}
                              >
                                {mapStopLoading === map.name ? 'Stopping...' : 'Stop'}
                              </Button>
                            ) : (
                              <Button
                                variant="contained"
                                color="success"
                                onClick={() => handleMapStart(map.name)}
                                disabled={mapStartLoading === map.name}
                              >
                                {mapStartLoading === map.name ? 'Starting...' : 'Start'}
                              </Button>
                            )}
                          </Box>
                        </Box>
                      ))}
                    </Box>
                  )}
                </Box>
              )}
            </Box>
          </DialogContent>
          <DialogActions>
            <Button onClick={handleMapDialogClose}>Close</Button>
          </DialogActions>
        </Dialog>

        <Snackbar open={snackbar.open} autoHideDuration={6000} onClose={handleSnackbarClose}>
          <Alert onClose={handleSnackbarClose} severity={snackbar.severity} sx={{ width: '100%' }}>
            {snackbar.message}
          </Alert>
        </Snackbar>
      </Box>
    </Layout>
  );
};

export default SimulatorsPage;
