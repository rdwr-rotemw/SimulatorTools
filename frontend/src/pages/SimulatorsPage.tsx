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

  const handleFormSubmit = async (data: SimulatorCreate | SimulatorUpdate) => {
    try {
      if (selectedSimulator) {
        await updateSimulator(selectedSimulator.ip_address, data as SimulatorUpdate);
        setSnackbar({ open: true, message: 'Simulator updated', severity: 'success' });
      } else {
        await createSimulator(data as SimulatorCreate);
        setSnackbar({ open: true, message: 'Simulator created', severity: 'success' });
      }

      // Refresh simulator list from backend to reflect Sapro state
      await fetchSimulators();
    } catch (err: any) {
      setSnackbar({ open: true, message: err?.message || 'Operation failed', severity: 'error' });
    } finally {
      setFormOpen(false);
      setSelectedSimulator(null);
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

  return (
    <Layout>
      <Box sx={{ padding: 4 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 3 }}>
          <Typography variant="h4">Simulator Management</Typography>
          <Button variant="contained" startIcon={<AddIcon />} onClick={handleCreate}>Create Simulator</Button>
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
