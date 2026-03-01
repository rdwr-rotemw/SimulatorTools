import React from 'react';
import { Box, Checkbox, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper, IconButton, Typography, Skeleton, Fade, CircularProgress } from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import StopIcon from '@mui/icons-material/Stop';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import { Simulator } from '../../types/simulator.types';

interface SimulatorTableProps {
  simulators: Simulator[];
  onEdit: (simulator: Simulator) => void;
  onDelete: (ip: string) => void;
  onStart: (ip: string) => Promise<void>;
  onStop: (ip: string) => Promise<void>;
  isLoading: boolean;
  startLoading: string | null;
  stopLoading: string | null;
  sortBy: 'ip_address' | 'type' | 'version' | 'map' | 'status';
  sortOrder: 'asc' | 'desc';
  onSort: (column: 'ip_address' | 'type' | 'version' | 'map' | 'status') => void;
  selectedIps: Set<string>;
  onSelectionChange: (ips: Set<string>) => void;
}

export const SimulatorTable: React.FC<SimulatorTableProps> = ({
  simulators,
  onEdit,
  onDelete,
  onStart,
  onStop,
  isLoading,
  startLoading,
  stopLoading,
  sortBy,
  sortOrder,
  onSort,
  selectedIps,
  onSelectionChange,
}) => {
  const allSelected = simulators.length > 0 && simulators.every(s => selectedIps.has(s.ip_address));
  const someSelected = simulators.some(s => selectedIps.has(s.ip_address)) && !allSelected;

  const handleSelectAll = () => {
    if (allSelected) {
      onSelectionChange(new Set());
    } else {
      onSelectionChange(new Set(simulators.map(s => s.ip_address)));
    }
  };

  const handleRowSelect = (ip: string) => {
    const next = new Set(selectedIps);
    if (next.has(ip)) {
      next.delete(ip);
    } else {
      next.add(ip);
    }
    onSelectionChange(next);
  };

  const sortableHeader = (label: string, col: 'ip_address' | 'type' | 'version' | 'map' | 'status') => (
    <TableCell
      onClick={() => onSort(col)}
      sx={{ cursor: 'pointer', userSelect: 'none', '&:hover': { background: '#f5f5f5' } }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
        {label}
        {sortBy === col && (sortOrder === 'asc' ? <ArrowUpwardIcon fontSize="small" /> : <ArrowDownwardIcon fontSize="small" />)}
      </Box>
    </TableCell>
  );

  if (isLoading) {
    return (
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell padding="checkbox" />
              {sortableHeader('IP Address', 'ip_address')}
              {sortableHeader('Type', 'type')}
              {sortableHeader('Version', 'version')}
              {sortableHeader('Map', 'map')}
              {sortableHeader('Status', 'status')}
              <TableCell>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {[1, 2, 3, 4, 5].map((n) => (
              <TableRow key={n}>
                <TableCell padding="checkbox"><Skeleton variant="rectangular" width={18} height={18} /></TableCell>
                <TableCell><Skeleton variant="text" width={120} /></TableCell>
                <TableCell><Skeleton variant="text" width={100} /></TableCell>
                <TableCell><Skeleton variant="text" width={100} /></TableCell>
                <TableCell><Skeleton variant="text" width={80} /></TableCell>
                <TableCell><Skeleton variant="text" width={80} /></TableCell>
                <TableCell>
                  <Skeleton variant="circular" width={24} height={24} sx={{ display: 'inline-block', marginRight: 1 }} />
                  <Skeleton variant="circular" width={24} height={24} sx={{ display: 'inline-block' }} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    );
  }

  if (!isLoading && (!simulators || simulators.length === 0)) {
    return (
      <Box sx={{ minHeight: '200px', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
        <Typography>No simulators found</Typography>
      </Box>
    );
  }

  return (
    <Fade in={true} timeout={600}>
      <TableContainer component={Paper}>
        <Table stickyHeader>
          <TableHead>
            <TableRow>
              <TableCell padding="checkbox">
                <Checkbox
                  checked={allSelected}
                  indeterminate={someSelected}
                  onChange={handleSelectAll}
                  size="small"
                />
              </TableCell>
              {sortableHeader('IP Address', 'ip_address')}
              {sortableHeader('Type', 'type')}
              {sortableHeader('Version', 'version')}
              {sortableHeader('Map', 'map')}
              {sortableHeader('Status', 'status')}
              <TableCell>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {simulators.map((sim) => {
              const isStarting = startLoading === sim.ip_address;
              const isStopping = stopLoading === sim.ip_address;
              const isOperating = isStarting || isStopping;
              const statusLower = (sim.status || '').toLowerCase();
              const isRunning = statusLower === 'ok' || statusLower === 'running';
              const isStopped = statusLower === 'shutdown' || statusLower === 'stopped';
              const isSelected = selectedIps.has(sim.ip_address);

              return (
                <TableRow
                  key={sim.ip_address}
                  hover
                  selected={isSelected}
                  sx={{ cursor: 'pointer' }}
                >
                  <TableCell padding="checkbox" onClick={() => handleRowSelect(sim.ip_address)}>
                    <Checkbox checked={isSelected} size="small" />
                  </TableCell>
                  <TableCell>{sim.ip_address}</TableCell>
                  <TableCell>{sim.type || '—'}</TableCell>
                  <TableCell>{sim.version || '—'}</TableCell>
                  <TableCell>{sim.map || '—'}</TableCell>
                  <TableCell>{sim.status || '—'}</TableCell>
                  <TableCell>
                    {isRunning ? (
                      <IconButton
                        aria-label="stop"
                        color="error"
                        onClick={() => onStop(sim.ip_address)}
                        disabled={isOperating}
                        title="Stop simulator"
                      >
                        {isStopping ? <CircularProgress size={20} /> : <StopIcon />}
                      </IconButton>
                    ) : isStopped ? (
                      <IconButton
                        aria-label="start"
                        color="success"
                        onClick={() => onStart(sim.ip_address)}
                        disabled={isOperating}
                        title="Start simulator"
                      >
                        {isStarting ? <CircularProgress size={20} /> : <PlayArrowIcon />}
                      </IconButton>
                    ) : (
                      <IconButton aria-label="start-stop" disabled title="Status unknown">
                        <PlayArrowIcon />
                      </IconButton>
                    )}

                    <IconButton
                      aria-label="edit"
                      color="primary"
                      onClick={() => onEdit(sim)}
                      disabled={isOperating}
                      title="Edit simulator"
                    >
                      <EditIcon />
                    </IconButton>

                    <IconButton
                      aria-label="delete"
                      color="error"
                      onClick={() => onDelete(sim.ip_address)}
                      disabled={isOperating}
                      title="Delete simulator"
                    >
                      <DeleteIcon />
                    </IconButton>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
    </Fade>
  );
};
