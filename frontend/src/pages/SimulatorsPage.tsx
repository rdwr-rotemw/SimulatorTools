import React, {useEffect, useState} from 'react';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Snackbar,
  TextField,
  Typography
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import SearchIcon from '@mui/icons-material/Search';
import RefreshIcon from '@mui/icons-material/Refresh';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import StopIcon from '@mui/icons-material/Stop';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import ClearIcon from '@mui/icons-material/Clear';
import Layout from '../components/common/Layout';
import {SimulatorTable} from '../components/simulator/SimulatorTable';
import SimulatorFormDialog from '../components/simulator/SimulatorFormDialog';
import EditFieldsDialog from '../components/simulator/EditFieldsDialog';
import useSimulatorStore from '../store/simulatorStore';
import {Simulator, SimulatorCreate, SimulatorUpdate} from '../types/simulator.types';
import apiClient from '../api/client';
import activityTracker from '../utils/activityTracker';
import { simulatorService } from '../api/services/simulator.service';

interface SnackbarState {
  open: boolean;
  message: string;
  severity: 'success' | 'error';
}

export const SimulatorsPage: React.FC = () => {
  const [formOpen, setFormOpen] = useState(false);
  const [selectedSimulator, setSelectedSimulator] = useState<Simulator | null>(null);
  const [editFieldsOpen, setEditFieldsOpen] = useState(false);
  const [simulatorsToEditFields, setSimulatorsToEditFields] = useState<Simulator[]>([]);
  const [selectedIps, setSelectedIps] = useState<Set<string>>(new Set());
  const [bulkDeleteDialogOpen, setBulkDeleteDialogOpen] = useState(false);
  const [bulkActionLoading, setBulkActionLoading] = useState<'start' | 'stop' | 'delete' | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [simulatorToDelete, setSimulatorToDelete] = useState<string | null>(null);
  const [snackbar, setSnackbar] = useState<SnackbarState>({ open: false, message: '', severity: 'success' });
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState<'ip_address' | 'type' | 'version' | 'map' | 'status'>('ip_address');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const [startLoading, setStartLoading] = useState<string | null>(null);
  const [stopLoading, setStopLoading] = useState<string | null>(null);
  const [refreshLoading, setRefreshLoading] = useState(false);

  // Map management state
  const [mapDialogOpen, setMapDialogOpen] = useState(false);
  const [maps, setMaps] = useState<Array<{ name: string; status: string }>>([]);
  const [mapsLoading, setMapsLoading] = useState(false);
  const [mapStartLoading, setMapStartLoading] = useState<string | null>(null);
  const [mapStopLoading, setMapStopLoading] = useState<string | null>(null);
  const [createMapDialogOpen, setCreateMapDialogOpen] = useState(false);
  const [newMapName, setNewMapName] = useState('');
  const [createMapLoading, setCreateMapLoading] = useState(false);

  // Simulator creation progress state
  const [isCreating, setIsCreating] = useState(false);
  const [currentSimulator, setCurrentSimulator] = useState(0);
  const [totalSimulators, setTotalSimulators] = useState(0);

  const {
    simulators,
    isLoading,
    fetchSimulators,
    createSimulator,
    updateSimulator,
    deleteSimulator,
  } = useSimulatorStore();

  useEffect(() => {
    fetchSimulators();
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
    setSimulatorsToEditFields([sim]);
    setEditFieldsOpen(true);
  };

  const handleBulkEdit = () => {
    const selected = simulators.filter(s => selectedIps.has(s.ip_address));
    setSimulatorsToEditFields(selected);
    setEditFieldsOpen(true);
  };

  const handleBulkStart = async () => {
    const ipsParam = Array.from(selectedIps).join(',');
    setBulkActionLoading('start');
    activityTracker.pauseTracking();
    try {
      await apiClient.post(`/simulators/${ipsParam}/start`, {}, { timeout: 660000 });
      setSnackbar({ open: true, message: `Started ${selectedIps.size} simulator(s)`, severity: 'success' });
      setSelectedIps(new Set());
      await fetchSimulators();
    } catch (err: any) {
      setSnackbar({ open: true, message: err?.response?.data?.detail || 'Failed to start simulators', severity: 'error' });
    } finally {
      activityTracker.resumeTracking();
      setBulkActionLoading(null);
    }
  };

  const handleBulkStop = async () => {
    const ipsParam = Array.from(selectedIps).join(',');
    setBulkActionLoading('stop');
    activityTracker.pauseTracking();
    try {
      await apiClient.post(`/simulators/${ipsParam}/stop`, {}, { timeout: 660000 });
      setSnackbar({ open: true, message: `Stopped ${selectedIps.size} simulator(s)`, severity: 'success' });
      setSelectedIps(new Set());
      await fetchSimulators();
    } catch (err: any) {
      setSnackbar({ open: true, message: err?.response?.data?.detail || 'Failed to stop simulators', severity: 'error' });
    } finally {
      activityTracker.resumeTracking();
      setBulkActionLoading(null);
    }
  };

  const handleBulkDeleteConfirm = async () => {
    const ipsParam = Array.from(selectedIps).join(',');
    setBulkDeleteDialogOpen(false);
    setBulkActionLoading('delete');
    activityTracker.pauseTracking();
    try {
      await apiClient.delete(`/simulators/${ipsParam}`, { timeout: 660000 });
      setSnackbar({ open: true, message: `Deleted ${selectedIps.size} simulator(s)`, severity: 'success' });
      setSelectedIps(new Set());
      await fetchSimulators();
    } catch (err: any) {
      setSnackbar({ open: true, message: err?.response?.data?.detail || 'Failed to delete simulators', severity: 'error' });
    } finally {
      activityTracker.resumeTracking();
      setBulkActionLoading(null);
    }
  };

  const handleDeleteClick = (ip: string) => {
    setSimulatorToDelete(ip);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!simulatorToDelete) return;

    // Close dialog IMMEDIATELY to prevent flickering
    setDeleteDialogOpen(false);
    const ipToDelete = simulatorToDelete;
    setSimulatorToDelete(null);

    activityTracker.pauseTracking();
    try {
      await deleteSimulator(ipToDelete);
      setSnackbar({ open: true, message: 'Simulator deleted', severity: 'success' });
      // Refresh simulator list after deletion
      await fetchSimulators();
    } catch (err: any) {
      setSnackbar({
        open: true,
        message: err?.response?.data?.detail || err?.message || 'Failed to delete simulator',
        severity: 'error'
      });
    } finally {
      activityTracker.resumeTracking();
    }
  };

  const handleStart = async (ip: string) => {
    setStartLoading(ip);
    activityTracker.pauseTracking();
    try {
      await apiClient.post(`/simulators/${ip}/start`, {}, { timeout: 660000 });
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
      activityTracker.resumeTracking();
      setStartLoading(null);
    }
  };

  const handleStop = async (ip: string) => {
    setStopLoading(ip);
    activityTracker.pauseTracking();
    try {
      await apiClient.post(`/simulators/${ip}/stop`, {}, { timeout: 660000 });
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
      activityTracker.resumeTracking();
      setStopLoading(null);
    }
  };

  const handleMapStart = async (mapName: string) => {
    setMapStartLoading(mapName);
    activityTracker.pauseTracking();
    try {
      // Extended timeout: map lock can hold up to 10 min + map start operation
      await apiClient.post(`/maps/${mapName}/start`, {}, { timeout: 660000 });
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
      activityTracker.resumeTracking();
      setMapStartLoading(null);
    }
  };

  const handleMapStop = async (mapName: string) => {
    setMapStopLoading(mapName);
    activityTracker.pauseTracking();
    try {
      // Extended timeout: map lock can hold up to 10 min + map stop operation
      await apiClient.post(`/maps/${mapName}/stop`, {}, { timeout: 660000 });
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
      activityTracker.resumeTracking();
      setMapStopLoading(null);
    }
  };

  const handleCreateMap = async () => {
    if (!newMapName.trim()) {
      setSnackbar({ open: true, message: 'Map name is required', severity: 'error' });
      return;
    }

    setCreateMapLoading(true);
    try {
      await apiClient.post(`/maps?map_name=${encodeURIComponent(newMapName.trim())}`);
      setSnackbar({ open: true, message: `Map ${newMapName} created successfully`, severity: 'success' });
      setCreateMapDialogOpen(false);
      setNewMapName('');
      await fetchMaps();
    } catch (err: any) {
      console.error('Failed to create map:', err);
      setSnackbar({
        open: true,
        message: err?.response?.data?.detail || 'Failed to create map',
        severity: 'error'
      });
    } finally {
      setCreateMapLoading(false);
    }
  };

  const handleFormSubmit = async (data: SimulatorCreate | SimulatorUpdate) => {
    activityTracker.pauseTracking();
    try {
      if (selectedSimulator) {
        await updateSimulator(selectedSimulator.ip_address, data as SimulatorUpdate);
        setSnackbar({ open: true, message: 'Simulator updated successfully', severity: 'success' });
      } else {
        const createData = data as SimulatorCreate;
        // Check if IP is a range
        const isRange = createData.ip_address && createData.ip_address.includes('-');

        if (isRange) {
          // Use streaming for ranges
          setIsCreating(true);
          setCurrentSimulator(0);
          setTotalSimulators(0);

          await simulatorService.createSimulatorWithProgress(
            createData,
            (current, total, ip, status, message) => {
              setCurrentSimulator(current);
              setTotalSimulators(total);
            },
            (successCount, failedCount, totalCount) => {
              setIsCreating(false);
              if (failedCount === 0) {
                setSnackbar({
                  open: true,
                  message: `Successfully created all ${successCount} simulator(s)`,
                  severity: 'success'
                });
              } else if (successCount === 0) {
                setSnackbar({
                  open: true,
                  message: `Failed to create all ${failedCount} simulator(s)`,
                  severity: 'error'
                });
              } else {
                setSnackbar({
                  open: true,
                  message: `Created ${successCount} simulator(s), ${failedCount} failed`,
                  severity: 'success'
                });
              }
            },
            (error) => {
              setIsCreating(false);
              setSnackbar({
                open: true,
                message: `Error: ${error}`,
                severity: 'error'
              });
            }
          );
        } else {
          // Single IP - use regular creation
          await createSimulator(createData);
          setSnackbar({ open: true, message: 'Simulator created successfully', severity: 'success' });
        }
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
    } finally {
      activityTracker.resumeTracking();
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

  const handleRefresh = async () => {
    setRefreshLoading(true);
    try {
      await fetchSimulators();
      setSnackbar({ open: true, message: 'Simulators refreshed', severity: 'success' });
    } catch (err: any) {
      console.error('Failed to refresh simulators:', err);
      setSnackbar({
        open: true,
        message: 'Failed to refresh simulators',
        severity: 'error'
      });
    } finally {
      setRefreshLoading(false);
    }
  };

  return (
    <Layout>
      <Box sx={{ padding: 4 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 3 }}>
          <Typography variant="h4">Simulator Management</Typography>
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Button
              variant="outlined"
              startIcon={<RefreshIcon />}
              onClick={handleRefresh}
              disabled={refreshLoading || isLoading}
            >
              {refreshLoading ? 'Refreshing...' : 'Refresh'}
            </Button>
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

        {/* Bulk action toolbar */}
        {selectedIps.size > 0 && (
          <Box sx={{
            display: 'flex', alignItems: 'center', gap: 1, mb: 1, px: 2, py: 1,
            backgroundColor: 'primary.50', border: '1px solid', borderColor: 'primary.200',
            borderRadius: 1, flexWrap: 'wrap',
          }}>
            <Typography variant="body2" sx={{ fontWeight: 600, mr: 1 }}>
              {selectedIps.size} selected
            </Typography>
            <Button
              size="small"
              variant="contained"
              color="success"
              startIcon={bulkActionLoading === 'start' ? <CircularProgress size={14} color="inherit" /> : <PlayArrowIcon />}
              onClick={handleBulkStart}
              disabled={bulkActionLoading !== null}
            >
              Start
            </Button>
            <Button
              size="small"
              variant="contained"
              color="error"
              startIcon={bulkActionLoading === 'stop' ? <CircularProgress size={14} color="inherit" /> : <StopIcon />}
              onClick={handleBulkStop}
              disabled={bulkActionLoading !== null}
            >
              Stop
            </Button>
            <Button
              size="small"
              variant="contained"
              color="primary"
              startIcon={<EditIcon />}
              onClick={handleBulkEdit}
              disabled={bulkActionLoading !== null}
            >
              Edit Fields
            </Button>
            <Button
              size="small"
              variant="contained"
              color="error"
              startIcon={bulkActionLoading === 'delete' ? <CircularProgress size={14} color="inherit" /> : <DeleteIcon />}
              onClick={() => setBulkDeleteDialogOpen(true)}
              disabled={bulkActionLoading !== null}
            >
              Delete
            </Button>
            <Button
              size="small"
              variant="outlined"
              startIcon={<ClearIcon />}
              onClick={() => setSelectedIps(new Set())}
              sx={{ ml: 'auto' }}
            >
              Clear
            </Button>
          </Box>
        )}

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
          selectedIps={selectedIps}
          onSelectionChange={setSelectedIps}
        />

        <SimulatorFormDialog
          open={formOpen}
          simulator={selectedSimulator}
          simulators={simulators}
          onClose={handleFormClose}
          onSubmit={handleFormSubmit}
        />

        <EditFieldsDialog
          open={editFieldsOpen}
          simulators={simulatorsToEditFields}
          onClose={() => { setEditFieldsOpen(false); setSimulatorsToEditFields([]); }}
          onSuccess={() => {
            setSnackbar({ open: true, message: 'Simulator fields updated successfully', severity: 'success' });
            setSelectedIps(new Set());
            fetchSimulators();
          }}
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
          <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            Map Management
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => setCreateMapDialogOpen(true)}
            >
              Create Map
            </Button>
          </DialogTitle>
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

        {/* Create Map Dialog */}
        <Dialog open={createMapDialogOpen} onClose={() => setCreateMapDialogOpen(false)} maxWidth="sm" fullWidth>
          <DialogTitle>Create New Map</DialogTitle>
          <DialogContent>
            <Alert severity="info" sx={{ marginTop: 2, marginBottom: 2 }}>
              <Typography variant="body2">
                Map name should contain only letters, numbers, hyphens, and underscores.
                The map will be created in your current workspace.
              </Typography>
            </Alert>
            <TextField
              autoFocus
              margin="dense"
              label="Map Name"
              type="text"
              fullWidth
              value={newMapName}
              onChange={(e) => setNewMapName(e.target.value)}
              placeholder="e.g., MyNewMap"
              disabled={createMapLoading}
              helperText="Do not include .map extension"
            />
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setCreateMapDialogOpen(false)} disabled={createMapLoading}>
              Cancel
            </Button>
            <Button
              onClick={handleCreateMap}
              variant="contained"
              disabled={createMapLoading || !newMapName.trim()}
            >
              {createMapLoading ? <CircularProgress size={20} /> : 'Create'}
            </Button>
          </DialogActions>
        </Dialog>

        {/* Simulator Creation Progress Dialog */}
        <Dialog
          open={isCreating}
          maxWidth="sm"
          fullWidth
          disableEscapeKeyDown
        >
          <DialogContent>
            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3 }}>
              <CircularProgress size={60} />
              <Typography variant="h6">
                Creating Simulators...
              </Typography>
              {currentSimulator > 0 && (
                <Typography variant="h5" fontWeight="bold" color="primary">
                  {currentSimulator}/{totalSimulators}
                </Typography>
              )}
              <Typography variant="body2" color="textSecondary">
                Please wait while simulators are being created...
              </Typography>
            </Box>
          </DialogContent>
        </Dialog>

        {/* Bulk Delete Confirmation Dialog */}
        <Dialog open={bulkDeleteDialogOpen} onClose={() => setBulkDeleteDialogOpen(false)}>
          <DialogTitle>Confirm Bulk Delete</DialogTitle>
          <DialogContent>
            <DialogContentText>
              Are you sure you want to delete <strong>{selectedIps.size}</strong> simulator(s)?
              This action cannot be undone.
            </DialogContentText>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setBulkDeleteDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleBulkDeleteConfirm} color="error" variant="contained">Delete</Button>
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
